"""Export individually editable perspective strokes from an interpreted layout."""
from collections import Counter
from math import isfinite

import ezdxf

from path_geometry import add_native_path, parse_path

# Description, CAD plot lineweight (hundredths of mm), RGB, screen width in source pixels.
LAYERS = {
    'P-CONTEXT': ('环境轮廓', 9, (145, 145, 145), .65),
    'P-DETAIL': ('分格与细节', 13, (92, 92, 92), .8),
    'P-FRAME': ('主要结构线', 18, (50, 50, 50), 1.0),
    'P-PANEL': ('翘板与开口边缘', 25, (35, 35, 35), 1.15),
    'P-ENTRANCE': ('入口与场地构件', 25, (42, 42, 42), 1.2),
    'P-OUTLINE': ('建筑主轮廓', 35, (24, 24, 24), 1.6),
}
APP_ID = 'I2CAD_PEN_LINE'


def compile_lines(model, frame, dxf):
    if not isinstance(model, dict) or model.get('schema_version') != 1 or model.get('frame') != frame:
        raise ValueError('Pen lines require schema_version 1 and a frame matching the reference image')
    strokes = model.get('paths')
    if not isinstance(strokes, list) or not strokes:
        raise ValueError('Pen lines require a nonempty paths array')
    width, height = frame[2:]
    focus = model.get('focus')
    if focus is not None:
        if (not isinstance(focus, list) or len(focus) != 4
                or any(type(v) not in (int, float) or not isfinite(v) for v in focus)):
            raise ValueError('Invalid pen focus rectangle')
        left, top, right, bottom = focus
        if not (0 <= left < right < width and 0 <= top < bottom < height):
            raise ValueError('Pen focus rectangle must be inside the reference image')
    doc = ezdxf.new('R2010')
    doc.units = 0
    doc.header['$LWDISPLAY'] = True
    if focus:
        doc.set_modelspace_vport(bottom - top, center=((left + right) / 2, height - 1 - (top + bottom) / 2))
    else:
        doc.set_modelspace_vport(height, center=(width / 2, height / 2))
    doc.appids.new(APP_ID)
    for layer, (_, weight, rgb, _) in LAYERS.items():
        doc.layers.new(layer, dxfattribs={'lineweight': weight}).rgb = rgb
    msp = doc.modelspace()
    expected = {}
    geometry = set()
    for item in strokes:
        if not isinstance(item, dict):
            raise ValueError('Each pen stroke must be an object')
        name, layer = item.get('id'), item.get('layer')
        if (not isinstance(name, str) or not name.strip() or len(name.encode('utf-8')) > 100
                or any(ord(c) < 32 or ord(c) == 127 for c in name) or name in expected):
            raise ValueError('Pen stroke IDs must be unique strings of up to 100 UTF-8 bytes')
        if not isinstance(layer, str) or layer not in LAYERS:
            raise ValueError(f'{name}: unknown pen layer')
        try:
            segments, closed = parse_path(item.get('d'), height, width=width)
        except ValueError as error:
            raise ValueError(f'{name}: {error}') from error
        if any(len(set(segment)) == 1 for segment in segments):
            raise ValueError(f'{name}: zero-length stroke segment')
        if closed and all(len(s) == 2 for s in segments) and len({s[0] for s in segments}) < 3:
            raise ValueError(f'{name}: a closed polyline needs at least three distinct vertices')
        forward = tuple(segments)
        reverse = tuple(tuple(reversed(segment)) for segment in reversed(segments))
        key = layer, closed, min(forward, reverse)
        if key in geometry:
            raise ValueError(f'{name}: duplicate stroke on the same layer')
        geometry.add(key)
        entity = add_native_path(msp, segments, closed, {'layer': layer}, single_line=True)
        entity.set_xdata(APP_ID, [(1000, name)])
        expected[name] = (layer, entity.dxftype())
    doc.saveas(dxf)
    return expected


def audit_lines(doc, expected):
    audit = doc.audit()
    if audit.errors or audit.fixes or doc.units != 0:
        raise ValueError('Pen DXF failed the native geometry audit')
    found = {}
    for entity in doc.modelspace():
        metadata = entity.get_xdata(APP_ID)
        if len(metadata) != 1 or metadata[0].value in found:
            raise ValueError('Pen DXF has missing or repeated stroke IDs')
        layer = entity.dxf.layer
        if (layer not in LAYERS or entity.dxf.lineweight != -1
                or doc.layers.get(layer).dxf.lineweight != LAYERS[layer][1]):
            raise ValueError('Pen DXF lost a stroke layer or its lineweight')
        found[metadata[0].value] = layer, entity.dxftype()
    if found != expected:
        raise ValueError('Pen DXF lost stroke geometry, IDs or layers')
    types = Counter(kind for _, kind in found.values())
    return {
        'representation': 'lines', 'entities': len(found),
        'layers': dict(Counter(layer for layer, _ in found.values())),
        'relationship': {'status': 'not_assessed'},
        'geometry': {'status': 'pass', 'dxf_audit_errors': 0},
        'editability': {'status': 'pass', 'editable_entity_ratio': 1.0, 'entity_types': dict(types)},
        'cleanliness': {'has_hatch': False, 'visual_review_required': True},
        'review_page': 'review.html',
    }
