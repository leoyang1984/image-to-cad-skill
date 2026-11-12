"""Conservative, scale-aware operations on editable paths."""
from collections import Counter
from itertools import pairwise
from math import atan2, cos, dist, isfinite, pi, sin

from shapely import LineString, Point, Polygon, STRtree, box, line_merge
from shapely.ops import unary_union

DEFAULTS = {'tolerance_ratio': 0.001, 'gap_ratio': 0.0, 'relationship_ratio': 0.002}


def tolerances(frame, options):
    if not isinstance(options, dict) or options.keys() - DEFAULTS.keys():
        raise ValueError('Unknown regularization settings')
    ratios = DEFAULTS | options
    for name, value in ratios.items():
        if type(value) not in (float, int) or not isfinite(value) or not 0 <= value <= .02:
            raise ValueError(f'{name} must be a ratio in [0, .02]')
    scale = min(frame[2:])
    return {name.removesuffix('_ratio'): scale * value for name, value in ratios.items()}


def canonical_edge(a, b):
    return tuple(sorted((tuple(a), tuple(b))))


def clean_vertices(points, *, closed=False):
    """Drop repeated vertices and redundant collinear points, including a closing duplicate."""
    kept = []
    for p in points:
        if kept and p == kept[-1]:
            continue
        kept.append(p)
        while len(kept) >= 3 and between(*kept[-3:]):
            del kept[-2]
    if closed and len(kept) > 1 and kept[0] == kept[-1]:
        kept.pop()
    if closed and len(kept) > 3 and between(kept[-1], kept[0], kept[1]):
        del kept[0]
    if closed and len(kept) > 3 and between(kept[-2], kept[-1], kept[0]):
        kept.pop()
    return kept


def between(a, b, c):
    # Only exact collinearity (within floating point noise) preserves authored corners.
    ab, bc = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    return abs(ab[0] * bc[1] - ab[1] * bc[0]) <= 1e-9 and sum(
        x * y for x, y in zip(ab, bc)
    ) >= 0


def straighten_axis(points, tolerance):
    if len(points) != 2:
        return points
    a, b = points
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    minor = 1 if dx >= dy else 0
    limit = min(tolerance, .03 * dist(a, b))
    if 0 < min(dx, dy) <= limit:
        center = (a[minor] + b[minor]) / 2
        return [tuple(center if i == minor else p[i] for i in range(2)) for p in points]
    return points


def straighten_outline(points, tolerance):
    """Regularize near rectangular boundaries within both image and local thickness limits."""
    if len(points) != 4 or not tolerance:
        return points
    shape = Polygon(points)
    if not shape.is_valid or not shape.area:
        return points
    rectangle = shape.minimum_rotated_rectangle
    corners = list(rectangle.exterior.coords)
    thickness = min(dist(a, b) for a, b in pairwise(corners))
    limit = min(tolerance, .08 * thickness)
    for candidate in (box(*shape.bounds), rectangle):
        if shape.equals(candidate):
            return points
        if shape.hausdorff_distance(candidate) <= limit:
            return [tuple(p) for p in candidate.exterior.coords[:-1]]
    return points


def direction_key(a, b):
    """Canonical infinite line, rounded only to suppress floating point noise."""
    angle = atan2(b[1] - a[1], b[0] - a[0]) % pi
    # 0 and pi describe the same horizontal line.
    if abs(angle - pi) < 1e-12:
        angle = 0
    return round(angle, 12), round(a[1] * cos(angle) - a[0] * sin(angle), 9)


def merge_collinear(paths, *, protected=()):
    """Union overlapping/touching collinear segments, leaving separate lines and gaps alone."""
    groups = {}
    preserved = []
    tree = STRtree(protected) if len(protected) else None
    for path in paths:
        line = LineString(path)
        if len(path) != 2 or (tree is not None and len(tree.query(line, predicate='intersects'))):
            preserved.append(path)
            continue
        a, b = canonical_edge(*path)
        groups.setdefault(direction_key(a, b), []).append((a, b))
    for segments in groups.values():
        if len(segments) == 1:
            preserved.append(list(segments[0]))
            continue
        merged = unary_union([LineString(seg) for seg in segments])
        if merged.geom_type != 'LineString':
            merged = line_merge(merged)
        lines = merged.geoms if merged.geom_type == 'MultiLineString' else [merged]
        preserved.extend(clean_vertices(list(line.coords)) for line in lines)
    return preserved


def snap_endpoints(paths, gap, *, protected=()):
    """Join only mutually unambiguous open endpoints moving toward one another."""
    if not gap:
        return paths
    ends = [(i, end, path[end], path[1 if end == 0 else -2])
            for i, path in enumerate(paths) if path[0] != path[-1] for end in (0, -1)]
    tree = STRtree([Point(p) for _, _, p, _ in ends])
    barriers = STRtree(protected) if len(protected) else None
    choices = {}
    for i, (path_i, _, a, inward) in enumerate(ends):
        nearby = []
        for j in tree.query(Point(a).buffer(gap).envelope):
            path_j, _, b, other_inward = ends[j]
            if path_i == path_j or a == b or dist(a, b) > min(
                gap, .15 * dist(a, inward), .15 * dist(b, other_inward)
            ):
                continue
            if not (toward(inward, a, b) and toward(other_inward, b, a)):
                continue
            if barriers is not None:
                changed = LineString([inward, a, b, other_inward]).buffer(gap)
                if len(barriers.query(changed, predicate='intersects')):
                    continue
            nearby.append(j)
        if len(nearby) == 1:
            choices[i] = nearby[0]
    result = [list(path) for path in paths]
    for i, j in choices.items():
        if i < j and choices.get(j) == i:
            p, e, a, _ = ends[i]
            q, f, b, _ = ends[j]
            middle = tuple((x + y) / 2 for x, y in zip(a, b))
            result[p][e] = result[q][f] = middle
    return result


def toward(start, end, target):
    dot = sum((b - a) * (c - b) for a, b, c in zip(start, end, target))
    return dot >= .94 * dist(start, end) * dist(end, target)


def clean_linework(paths, gap, *, protected=()):
    unique = {}
    for path in paths:
        cleaned = clean_vertices(path)
        if len(cleaned) >= 2:
            canonical = min(tuple(cleaned), tuple(reversed(cleaned)))
            unique.setdefault(canonical, cleaned)
    snapped = snap_endpoints(list(unique.values()), gap, protected=protected)
    return merge_collinear(snapped, protected=protected)


def segment_quality(paths, minimum):
    edges = Counter()
    short = 0
    for layer, points, closed in paths:
        sequence = [*points, points[0]] if closed else points
        for a, b in pairwise(sequence):
            edges[(layer, canonical_edge(a, b))] += 1
            short += dist(a, b) < minimum
    return {
        'segments': sum(edges.values()),
        'duplicate_edges_on_same_layer': sum(count - 1 for count in edges.values()),
        'short_segments': short,
        'short_threshold_px': minimum,
    }
