"""Regression cases for interpreted sections and clean line extraction."""
import copy
import hashlib
import json
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory

import ezdxf
from PIL import Image, ImageDraw
from shapely import LineString, Polygon

from smoke import CONVERT

FRAME = [0, 0, 600, 400]


def rect(kind, name, x1, y1, x2, y2, **data):
    return {'kind': kind, 'id': name, 'outline': [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], **data}


def relation(a, b, role='connects'):
    return {'from': a, 'to': b, 'type': role}


def execute(work, name, components=None, relationships=(), *, source='source.png', extra=(), **data):
    result = work / name
    args = [sys.executable, str(CONVERT), 'section', '--intent', 'reconstruct',
            '--source', str(work / source), '--output', str(result), *extra]
    if components is not None:
        layout = work / f'{name}.json'
        layout.write_text(json.dumps({'schema_version': 1, 'frame': FRAME, 'interpretation': 'human',
                                      'components': components, 'relationships': list(relationships), **data}))
        args += ['--layout', str(layout)]
    finished = run(args, text=True, capture_output=True)
    return result, finished


def read_result(result, finished, *, cleaned=False):
    assert not finished.returncode, finished.stderr
    expected = {'redrawn.dxf', 'cad-preview.png', 'layout.json', 'report.json', 'review.html'}
    assert {p.name for p in result.iterdir()} == expected | ({'cleaned.png'} if cleaned else set())
    dxf = ezdxf.readfile(result / 'redrawn.dxf')
    audit = dxf.audit()
    assert not audit.errors and not audit.fixes and dxf.units == 0
    assert len(dxf.modelspace()) and {e.dxftype() for e in dxf.modelspace()} <= {'LINE', 'LWPOLYLINE'}
    with Image.open(result / 'cad-preview.png') as preview:
        assert preview.convert('L').getextrema()[0] < 200
    return (dxf, json.loads((result / 'report.json').read_text()),
            json.loads((result / 'layout.json').read_text()))


def entities(doc):
    grouped = {}
    for entity in doc.modelspace():
        name = entity.get_xdata('I2CAD_SECTION')[0].value
        if entity.dxftype() == 'LINE':
            a, b = entity.dxf.start, entity.dxf.end
            pts, closed = [(a.x, 399 - a.y), (b.x, 399 - b.y)], False
        else:
            pts = [(x, 399 - y) for x, y in entity.get_points('xy')]
            closed = entity.closed
        grouped.setdefault(name, []).append((entity.dxf.layer, closed, pts))
    return grouped


def simple(work):
    parts = [
        rect('wall', 'wall', 45, 75, 60, 345),
        rect('slab', 'floor', 60, 330, 470, 345),
        {'id': 'independent-beam', 'kind': 'beam', 'axis': [[100, 105], [400, 105.3]], 'thickness': 12},
        {'id': 'pier', 'kind': 'column', 'outline': [[510, 80], [530, 80.2], [530.2, 290], [510, 290]]},
    ]
    links = [relation('wall', 'floor')]
    dxf, report, model = read_result(*execute(work, 'simple', parts, links))
    assert report['relationship']['status'] == 'pass'
    assert len(report['regularization_changes']) == 2
    assert model['components'][2]['axis'][0][1] == model['components'][2]['axis'][1][1]
    assert len({point[0] for point in model['components'][3]['outline']}) == 2
    again, _, _ = read_result(*execute(work, 'simple-repeat', parts, links))
    assert entities(again) == entities(dxf)
    replay, _, _ = read_result(*execute(work, 'simple-replay', model['components'], model['relationships'],
                                         source_image=model['source_image']))
    assert entities(replay) == entities(dxf)


def multi_level(work):
    parts = [rect('column', 'column', 90, 40, 110, 355),
             rect('foundation', 'base', 70, 355, 130, 375)]
    links = [relation('column', 'base')]
    for index, y in enumerate((90, 195, 330), 1):
        parts.append(rect('slab', f'level-{index}', 110, y, 490, y + 16))
        links.append(relation('column', f'level-{index}'))
    parts.append(rect('beam', 'upper-beam', 130, 106, 470, 120))
    links.append(relation('upper-beam', 'level-1'))
    _, report, _ = read_result(*execute(work, 'multi-level', parts, links))
    assert report['component_counts']['slab'] == 3
    assert report['relationship']['status'] == 'pass'
    assert all(r['status'] == 'pass' for r in report['relationship']['connections'])
    moved = copy.deepcopy(parts)
    moved[-1] = rect('beam', 'upper-beam', 130, 122, 470, 140)
    _, bad_report, _ = read_result(*execute(work, 'disconnected', moved, links))
    assert bad_report['relationship']['status'] == 'fail'
    assert bad_report['relationship']['connections'][-1]['status'] == 'disconnected'


def circulation(work):
    parts = [
        rect('wall', 'wall', 60, 50, 75, 330),
        rect('door', 'door', 57, 255, 78, 330, host='wall'),
        rect('window', 'window', 57, 135, 78, 190, host='wall'),
        rect('unresolved', 'unknown', 57, 80, 78, 100, host='wall'),
        rect('slab', 'lower', 75, 330, 170, 345),
        rect('slab', 'upper', 400, 220, 550, 235),
        {'id': 'ramp', 'kind': 'ramp', 'axis': [[170, 330], [290, 271], [400, 220]]},
        {'id': 'stair', 'kind': 'stair', 'paths': [[[405, 218], [405, 205], [418, 205],
                                                 [418, 192], [431, 192], [431, 179]]]},
        {'id': 'spans', 'kind': 'linework',
         'paths': [[[19, 160], [54, 160]], [[80, 160], [110, 160]],
                   [[100, 360], [130, 360]], [[131, 360], [180, 360]],
                   [[220, 360], [250, 360]], [[240, 360], [270, 360]],
                   [[250, 360], [220, 360]], [[300, 360], [320, 360]], [[325, 360], [345, 360]]]},
    ]
    links = [relation('ramp', 'lower', 'ramp_start'), relation('ramp', 'upper', 'ramp_end')]
    barrier = [[321, 353], [324, 353], [324, 367], [321, 367]]
    dxf, report, layout = read_result(*execute(work, 'circulation', parts, links, protected_openings=[barrier],
                                                 tolerances={'gap_ratio': .02}))
    assert report['relationship']['status'] == 'needs_review'
    assert report['relationship']['ramps']['ramp']['elevation_change_px'] == 110
    assert len(report['relationship']['hosted_openings']) == 3
    drawn = entities(dxf)
    for _, closed, pts in drawn['wall']:
        assert closed and Polygon(pts).is_valid
        for item in parts[1:4]:
            opening = Polygon(item['outline']).buffer(-.001)
            assert not LineString([*pts, pts[0]]).intersects(opening)
    assert drawn['stair'][0][2] == [tuple(p) for p in parts[7]['paths'][0]]
    spans = {tuple(path) for _, _, path in drawn['spans']}
    assert ((100, 360), (180, 360)) in spans
    assert ((220, 360), (270, 360)) in spans
    assert ((300, 360), (320, 360)) in spans and ((325, 360), (345, 360)) in spans
    assert len(spans) == 6
    assert layout['source_image']['sha256'] == hashlib.sha256((work / 'source.png').read_bytes()).hexdigest()
    malformed = copy.deepcopy(parts)
    malformed[1]['host'] = 'missing'
    bad, process = execute(work, 'invalid-host', malformed, links)
    assert process.returncode and 'unknown wall host' in process.stderr and not bad.exists()


def routes(work):
    drawing = Image.new('RGB', tuple(FRAME[2:]), 'white')
    draw = ImageDraw.Draw(drawing)
    draw.line([(20, 100), (180, 100)], fill='black', width=7)
    draw.line([(200, 100), (330, 100)], fill='black', width=7)
    draw.line([(250, 100), (250, 160)], fill='black', width=5)
    draw.rectangle((380, 160, 550, 330), outline='black', width=5)
    drawing.save(work / 'clean-line.png')
    dxf, report, layout = read_result(*execute(work, 'linework', source='clean-line.png',
                                                 extra=['--input-route', 'linework']))
    assert report['interpretation'] == 'automatic_linework'
    assert report['relationship']['status'] == 'not_assessed'
    assert report['cleanliness']['unclassified_linework']
    strokes = entities(dxf)['raster-linework']
    assert {layer for layer, _, _ in strokes} == {'S-LINEWORK'}
    assert any(closed for _, closed, _ in strokes), 'rectangle loop was lost'
    left = [pts for _, _, pts in strokes if max(x for x, _ in pts) < 190]
    assert len(left) == 1 and all(abs(y - 100) < 2 for _, y in left[0])
    assert all(not (min(x for x, _ in pts) < 190 < max(x for x, _ in pts)) for _, _, pts in strokes)
    assert layout['input_route'] == 'linework'
    part = [rect('wall', 'wall', 80, 70, 100, 300)]
    clean = work / 'clean-line.png'
    digest = hashlib.sha256(clean.read_bytes()).hexdigest()
    common = ['--input-route', 'simplified', '--simplified', str(clean)]
    result, denied = execute(work, 'unapproved', part, extra=common)
    assert denied.returncode and not result.exists()
    result, wrong_hash = execute(work, 'wrong-hash', part, extra=[*common, '--approved', '--approved-sha256', '0'*64])
    assert wrong_hash.returncode and not result.exists()
    _, report, _ = read_result(*execute(work, 'approved', part,
                                          extra=[*common, '--approved', '--approved-sha256', digest]),
                                 cleaned=True)
    assert report['approved_image_sha256'] == digest and report['simplified_frame_match']


def main():
    with TemporaryDirectory() as directory:
        work = Path(directory)
        image = Image.new('RGB', tuple(FRAME[2:]), 'white')
        ImageDraw.Draw(image).rectangle((50, 60, 500, 345), outline='black')
        image.save(work / 'source.png')
        for case in (simple, multi_level, circulation, routes):
            case(work)
            print(f'{case.__name__}: passed')


if __name__ == '__main__':
    main()
