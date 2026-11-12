"""Compile an interpreted section into editable, identified DXF entities."""
from collections import Counter, defaultdict
from itertools import pairwise
from math import dist, isfinite

import ezdxf
from shapely import LineString, Point, Polygon, STRtree, union_all

from regularize import (clean_linework, clean_vertices, segment_quality, straighten_axis,
                        straighten_outline, tolerances)

LAYERS = {
    'wall': ('S-WALL', '墙体', (39, 48, 58)),
    'slab': ('S-SLAB', '楼板', (31, 88, 116)),
    'beam': ('S-BEAM', '梁', (77, 72, 104)),
    'column': ('S-COLUMN', '柱', (55, 95, 79)),
    'door': ('S-DOOR', '门及门洞', (155, 82, 45)),
    'window': ('S-WINDOW', '窗及窗洞', (30, 120, 145)),
    'stair': ('S-STAIR', '楼梯', (137, 85, 135)),
    'ramp': ('S-RAMP', '坡道', (193, 74, 44)),
    'foundation': ('S-FOUNDATION', '基础', (95, 106, 118)),
    'unresolved': ('S-REVIEW', '待确认', (181, 115, 28)),
    'linework': ('S-LINEWORK', '未分类线稿', (34, 34, 34)),
}
SOLIDS = {'wall', 'slab', 'beam', 'column', 'foundation'}
OPENINGS = {'door', 'window', 'unresolved'}
CERTAINTIES = {'clear', 'needs_confirmation'}
INTERPRETATIONS = {'agent', 'human', 'model_assisted', 'automatic_linework', 'unspecified'}
APP_ID = 'I2CAD_SECTION'
EPSILON = 1e-7


def point(value, frame):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (float, int) or not isfinite(v) for v in value)):
        raise ValueError('Expected a finite [x, y] point')
    if not (-.5 <= value[0] <= frame[2] - .5 and -.5 <= value[1] <= frame[3] - .5):
        raise ValueError('Geometry falls outside the declared source frame')
    return tuple(value)


def points(value, frame, minimum):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f'Expected at least {minimum} points')
    return [point(p, frame) for p in value]


def polygon(coords):
    shape = Polygon(coords)
    if not shape.is_valid or shape.area <= EPSILON:
        raise ValueError('Outline must enclose a valid, nonzero area')
    return shape


def parse_component(raw, frame):
    if not isinstance(raw, dict):
        raise ValueError('Each component must be an object')
    item = dict(raw)
    name, kind = item.get('id'), item.get('kind')
    if not isinstance(name, str) or not name.strip() or len(name) > 100 or any(
        ord(c) < 32 or ord(c) == 127 for c in name
    ):
        raise ValueError('Component ID must be a nonempty string of up to 100 characters')
    if not isinstance(kind, str) or kind not in LAYERS:
        raise ValueError(f'{name}: unsupported component kind')
    if kind == 'unresolved':
        item['certainty'] = 'needs_confirmation'
    else:
        item.setdefault('certainty', 'clear')
    if item['certainty'] not in tuple(CERTAINTIES):
        raise ValueError(f'{name}: invalid certainty')
    if kind in {'door', 'window'} and 'host' not in item:
        raise ValueError(f'{name}: a door/window requires a wall host (use unresolved if unknown)')
    if 'host' in item and (kind not in OPENINGS or not isinstance(item['host'], str) or 'outline' not in item):
        raise ValueError(f'{name}: a hosted opening needs a wall ID and outline')
    if 'outline' in item:
        item['outline'] = points(item['outline'], frame, 3)
        polygon(item['outline'])
    if 'axis' in item:
        item['axis'] = points(item['axis'], frame, 2)
        if any(a == b for a, b in pairwise(item['axis'])) or not LineString(item['axis']).is_simple:
            raise ValueError(f'{name}: invalid axis')
        if kind == 'ramp' and item['axis'][0] == item['axis'][-1]:
            raise ValueError(f'{name}: a ramp requires distinct directed ends')
    if 'paths' in item:
        if not isinstance(item['paths'], list) or not item['paths']:
            raise ValueError(f'{name}: paths must be an array')
        item['paths'] = [points(path, frame, 2) for path in item['paths']]
        if kind in {'stair', 'ramp'} and any(a == b for path in item['paths'] for a, b in pairwise(path)):
            raise ValueError(f'{name}: zero-length stair or ramp segment')
    if 'thickness' in item:
        thickness = item['thickness']
        if type(thickness) not in (float, int) or not isfinite(thickness) or not 0 < thickness <= min(frame[2:]):
            raise ValueError(f'{name}: invalid thickness')
    if kind in SOLIDS and 'outline' not in item and not {'axis', 'thickness'} <= item.keys():
        raise ValueError(f'{name}: structural solids require an outline or axis with thickness')
    if kind == 'ramp' and 'axis' not in item:
        raise ValueError(f'{name}: a ramp requires a directed axis')
    if not ('outline' in item or 'axis' in item or item.get('paths')):
        raise ValueError(f'{name}: missing geometry')
    return item


def parse_relations(raw, items):
    if not isinstance(raw, list):
        raise ValueError('relationships must be an array')
    relations, seen = [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError('Each relationship must be an object')
        relation = dict(entry)
        a, b, role = (relation.get(key) for key in ('from', 'to', 'type'))
        if not isinstance(a, str) or not isinstance(b, str) or a == b or a not in items or b not in items:
            raise ValueError('Relationship must reference two different component IDs')
        if role not in ('connects', 'ramp_start', 'ramp_end'):
            raise ValueError('Unknown relationship type')
        relation.setdefault('certainty', 'clear')
        if relation['certainty'] not in tuple(CERTAINTIES):
            raise ValueError('Invalid relationship certainty')
        if role != 'connects' and (items[a]['kind'] != 'ramp' or items[b]['kind'] != 'slab'):
            raise ValueError('A ramp endpoint must reference a ramp and a slab')
        key = (role, *sorted((a, b))) if role == 'connects' else (role, a)
        if key in seen:
            raise ValueError(f'Duplicate relationship: {a} {role} {b}')
        seen.add(key)
        relations.append(relation)
    return relations


def apply_regularization(items, relations, barriers, settings, frame):
    fixed = {relation[key] for relation in relations for key in ('from', 'to')}
    fixed.update(item['host'] for item in items.values() if 'host' in item)
    # Also protect existing or potential contacts that were not explicitly declared.
    names = list(items)
    shapes = [component_shape(items[name]) for name in names]
    index = STRtree(shapes)
    for i, name in enumerate(names):
        if items[name]['kind'] not in SOLIDS:
            continue
        shape = shapes[i]
        envelope = shape.buffer(2 * settings['tolerance']).envelope
        if any(j != i and shape.distance(shapes[j]) <= 2 * settings['tolerance']
               for j in index.query(envelope)):
            fixed.add(name)
        if any(shape.distance(barrier) <= 2 * settings['tolerance'] for barrier in barriers):
            fixed.add(name)
    operations = []
    for name, item in items.items():
        for key in ('outline', 'axis', 'paths'):
            if key not in item:
                continue
            original = item[key]
            if key == 'paths':
                # Stair treads and projected ramp geometry retain their authored segmentation.
                if item['kind'] in {'stair', 'ramp'}:
                    continue
                can_join = (item['kind'] == 'linework' and item['certainty'] == 'clear' and name not in fixed)
                revised = clean_linework(original, settings['gap'], protected=barriers) if can_join else [
                    clean_vertices(path) for path in original
                ]
                if not revised or any(len(path) < 2 for path in revised):
                    raise ValueError(f'{name}: degenerate paths')
            else:
                revised = clean_vertices(original, closed=key == 'outline')
                movable = (item['kind'] in SOLIDS and item['certainty'] == 'clear' and
                           name not in fixed and item.get('rectify', True))
                if movable:
                    straighten = straighten_outline if key == 'outline' else straighten_axis
                    revised = straighten(revised, settings['tolerance'])
                if key == 'outline':
                    polygon(revised)
                for p in revised:
                    point(p, frame)
            if revised != original:
                item[key] = revised
                operations.append({'component': name, 'field': key, 'before': original, 'after': revised})
    return operations


def component_shape(item):
    if 'outline' in item:
        return polygon(item['outline'])
    if 'axis' in item:
        axis = LineString(item['axis'])
        if item['kind'] in SOLIDS:
            return axis.buffer(item['thickness'] / 2, cap_style='flat', join_style='mitre')
        return axis
    return union_all([LineString(path) for path in item['paths']])


def apply_openings(items, shapes):
    cutters = defaultdict(list)
    checks = []
    for name, item in items.items():
        host = item.get('host')
        if host is None:
            continue
        if host not in items or items[host]['kind'] != 'wall':
            raise ValueError(f'{name}: unknown wall host {host}')
        host_shape, opening = shapes[host], shapes[name]
        cut = host_shape.intersection(opening)
        if cut.area <= EPSILON:
            raise ValueError(f'{name}: opening does not intersect its wall')
        if any(cut.intersection(other).area > EPSILON for other in cutters[host]):
            raise ValueError(f'{name}: opening overlaps another opening in {host}')
        cutters[host].append(cut)
        checks.append({'opening': name, 'host': host, 'cut_area_px2': round(cut.area, 6),
                       'certainty': item['certainty']})
    for host, cuts in cutters.items():
        remaining = shapes[host].difference(union_all(cuts))
        if remaining.area <= EPSILON:
            raise ValueError(f'{host}: openings removed the whole wall')
        shapes[host] = remaining
    return checks


def relationship_report(items, shapes, relations, openings, tolerance):
    checked = []
    for relation in relations:
        a, b, role = (relation[key] for key in ('from', 'to', 'type'))
        origin = shapes[a]
        if role != 'connects':
            endpoint = 0 if role == 'ramp_start' else -1
            origin = Point(items[a]['axis'][endpoint])
        distance = origin.distance(shapes[b])
        status = 'needs_confirmation' if relation['certainty'] == 'needs_confirmation' else (
            'pass' if distance <= tolerance + EPSILON else 'disconnected'
        )
        checked.append(relation | {'distance_px': round(distance, 6), 'status': status})
    ramps = {name: item for name, item in items.items() if item['kind'] == 'ramp'}
    ramp_ends = {(r['from'], r['type']) for r in checked}
    missing = [{'component': name, 'missing': role} for name in ramps
               for role in ('ramp_start', 'ramp_end') if (name, role) not in ramp_ends]
    unresolved = [name for name, item in items.items() if item['certainty'] == 'needs_confirmation']
    return {
        'connections': checked, 'hosted_openings': openings, 'unresolved_components': unresolved,
        'ramps': {name: {'start': item['axis'][0], 'end': item['axis'][-1],
                         'elevation_change_px': item['axis'][0][1] - item['axis'][-1][1]}
                  for name, item in ramps.items()},
        'undeclared_ramp_endpoints': missing,
        'distance_tolerance_px': tolerance,
        'status': 'fail' if any(r['status'] == 'disconnected' for r in checked) else (
            'needs_review' if missing or unresolved or any(r['status'] != 'pass' for r in checked) else
            'pass' if checked or openings else 'not_assessed'
        ),
    }


def rings(shape):
    if shape.geom_type == 'Polygon':
        for ring in (shape.exterior, *shape.interiors):
            yield list(ring.coords)[:-1]
    elif shape.geom_type == 'MultiPolygon':
        for part in shape.geoms:
            yield from rings(part)
    else:
        raise ValueError('Section structural geometry must remain polygonal')


def same_layer_overlaps(items, shapes):
    groups = defaultdict(list)
    for name, item in items.items():
        if item['kind'] in SOLIDS:
            groups[item['kind']].append(name)
    results = []
    for group in groups.values():
        polygons = [shapes[name] for name in group]
        index = STRtree(polygons)
        for i, shape in enumerate(polygons):
            for j in sorted(index.query(shape, predicate='intersects')):
                if j > i and shape.intersection(polygons[j]).area > EPSILON:
                    results.append([group[i], group[j]])
    return results


def opening_symbol(item):
    # The cutter is a layout datum. A supplied symbol can represent projected glass or a jamb.
    if item.get('paths'):
        return []
    shape = polygon(item['outline'])
    corners = list(shape.minimum_rotated_rectangle.exterior.coords)[:-1]
    edges = [(a, b) for a, b in pairwise([*corners, corners[0]])]
    short = min(range(len(edges)), key=lambda i: dist(*edges[i]))
    if item['kind'] == 'door':
        return [list(edges[short])]
    return [[tuple((x + y) / 2 for x, y in zip(a, b))
             for a, b in (edges[short], edges[(short + 2) % 4])]]


def draw(items, shapes, frame, path, *, focus=None):
    doc = ezdxf.new('R2010')
    doc.units = 0
    width, height = frame[2:]
    if focus:
        x1, y1, x2, y2 = focus
        doc.set_modelspace_vport(y2 - y1, center=((x1 + x2) / 2, height - 1 - (y1 + y2) / 2))
    else:
        doc.set_modelspace_vport(height, center=(width / 2, height / 2))
    doc.appids.new(APP_ID)
    for layer, _, rgb in LAYERS.values():
        doc.layers.new(layer).rgb = rgb
    msp = doc.modelspace()
    quality_paths = []
    for name, item in items.items():
        layer = LAYERS[item['kind']][0]
        outlines = (list(rings(shapes[name])) if item['kind'] in SOLIDS else
                    [item['outline']] if 'outline' in item else [])
        paths = list(item.get('paths', []))
        if item['kind'] in {'door', 'window'}:
            outlines = []
            paths.extend(opening_symbol(item))
        if 'axis' in item and item['kind'] not in SOLIDS:
            paths.insert(0, item['axis'])
        native_paths = [(ring, True) for ring in outlines]
        for stroke in paths:
            loop = len(stroke) >= 4 and stroke[0] == stroke[-1]
            closed = loop and Polygon(stroke).is_valid and Polygon(stroke).area > EPSILON
            native_paths.append((stroke[:-1] if closed else stroke, closed))
        for points, closed in native_paths:
            if len(points) < 2 or any(a == b for a, b in pairwise(points)):
                raise ValueError(f'{name}: zero-length output segment')
            coords = [(x, height - 1 - y) for x, y in points]
            attrs = {'layer': layer}
            if len(coords) == 2 and not closed:
                entity = msp.add_line(*coords, dxfattribs=attrs)
            else:
                entity = msp.add_lwpolyline(coords, close=closed, dxfattribs=attrs)
            entity.set_xdata(APP_ID, [(1000, name)])
            quality_paths.append((layer, points, closed))
    if not quality_paths:
        raise ValueError('Section has no editable geometry')
    doc.saveas(path)
    return quality_paths


def compile_section(model, frame, path):
    if not isinstance(model, dict) or model.get('schema_version') != 1 or model.get('frame') != frame:
        raise ValueError('Section needs schema_version 1 and a frame matching the source image')
    if model.get('intent', 'reconstruct') != 'reconstruct':
        raise ValueError('Section layout must have reconstruct intent')
    interpretation = model.get('interpretation', 'unspecified')
    if interpretation not in tuple(INTERPRETATIONS):
        raise ValueError('Invalid section interpretation provenance')
    for key in ('regularization', 'omitted', 'unresolved_questions', 'protected_openings'):
        if not isinstance(model.get(key, []), list):
            raise ValueError(f'{key} must be an array')
    raw = model.get('components')
    if not isinstance(raw, list) or not raw:
        raise ValueError('Section needs at least one component')
    items = {}
    for component in raw:
        item = parse_component(component, frame)
        if item['id'] in items:
            raise ValueError(f"Duplicate component ID: {item['id']}")
        items[item['id']] = item
    relations = parse_relations(model.get('relationships', []), items)
    settings = tolerances(frame, model.get('tolerances', {}))
    barriers = [polygon(points(ring, frame, 3)) for ring in model.get('protected_openings', [])]
    barriers.extend(polygon(item['outline']) for item in items.values()
                    if item['kind'] in OPENINGS and 'outline' in item)
    operations = apply_regularization(items, relations, barriers, settings, frame)
    shapes = {name: component_shape(item) for name, item in items.items()}
    openings = apply_openings(items, shapes)
    relationships = relationship_report(items, shapes, relations, openings, settings['relationship'])
    focus = model.get('focus')
    if focus is not None:
        if not isinstance(focus, list) or len(focus) != 4:
            raise ValueError('focus must be [x1, y1, x2, y2]')
        a, b = point(focus[:2], frame), point(focus[2:], frame)
        if not a[0] < b[0] or not a[1] < b[1]:
            raise ValueError('focus must have positive area')
    paths = draw(items, shapes, frame, path, focus=focus)
    model = model | {'components': list(items.values()), 'relationships': relations,
                     'interpretation': interpretation, 'intent': 'reconstruct'}
    geometry = segment_quality(paths, settings['tolerance'])
    overlaps = same_layer_overlaps(items, shapes)
    geometry.update(invalid_closed_outlines=0, closed_outlines=sum(closed for _, _, closed in paths),
                    overlapping_solids_on_same_layer=overlaps, applied_operations=len(operations))
    geometry['status'] = 'needs_review' if any(
        (overlaps, geometry['duplicate_edges_on_same_layer'], geometry['short_segments'])
    ) else 'pass'
    return model, {
        'component_counts': dict(sorted(Counter(item['kind'] for item in items.values()).items())),
        'relationship': relationships, 'geometry': geometry, 'regularization_px': settings,
        'regularization_changes': operations, 'out_of_scope': model.get('omitted', []),
        'unresolved_questions': model.get('unresolved_questions', []),
        'interpretation': interpretation,
        'limitations': [
            'Connections are checked only where declared. Source fidelity and full spatial continuity need visual review.',
            'Coordinates use uncalibrated raster pixels. No survey dimensions are inferred.',
        ],
    }


def audit_section(doc, model, report):
    entities = list(doc.modelspace())
    expected = {item['id']: LAYERS[item['kind']][0] for item in model['components']}
    ids = set()
    per_component = defaultdict(list)
    height = model['frame'][3]
    for entity in entities:
        data = entity.get_xdata(APP_ID)
        if len(data) != 1 or data[0].value not in expected or expected[data[0].value] != entity.dxf.layer:
            raise ValueError('Invalid component ID or layer in DXF readback')
        name = data[0].value
        ids.add(name)
        if entity.dxftype() == 'LINE':
            points_px = [(p.x, height - 1 - p.y) for p in (entity.dxf.start, entity.dxf.end)]
        elif entity.dxftype() == 'LWPOLYLINE':
            points_px = [(x, height - 1 - y) for x, y in entity.get_points('xy')]
            if entity.closed:
                polygon(points_px)
                points_px.append(points_px[0])
        else:
            raise ValueError('Unexpected section DXF entity')
        per_component[name].append(LineString(points_px))
    for item in model['components']:
        if 'host' in item:
            interior = polygon(item['outline']).buffer(-EPSILON)
            if any(line.intersects(interior) for line in per_component[item['host']]):
                raise ValueError(f"{item['id']}: saved wall crosses a protected opening")
        if item['kind'] == 'ramp':
            saved_axis = per_component[item['id']][int('outline' in item)]
            if not saved_axis.equals_exact(LineString(item['axis']), EPSILON):
                raise ValueError(f"{item['id']}: saved ramp direction or geometry changed")
    types = Counter(entity.dxftype() for entity in entities)
    if ids != set(expected) or set(types) - {'LINE', 'LWPOLYLINE'}:
        raise ValueError('Unexpected types or missing components in section DXF readback')
    report['editability'] = {'status': 'pass', 'component_ids': len(ids), 'editable_entity_ratio': 1.0,
                             'entity_types': dict(types), 'layers': dict(Counter(e.dxf.layer for e in entities))}
    report['cleanliness'] = {
        'status': 'needs_review' if 'S-LINEWORK' in expected.values() else 'pass',
        'hatch_entities': 0, 'text_entities': 0, 'unclassified_linework': 'S-LINEWORK' in expected.values(),
        'visual_review_required': True,
    }
