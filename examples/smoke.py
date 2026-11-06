"""Run all three exporters with generated drawings in a temporary directory."""
import json
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory

import ezdxf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CONVERT = ROOT / 'skills/image-to-cad/scripts/convert.py'


def check(mode, arguments, work, expected):
    result = work / mode
    run([sys.executable, str(CONVERT), mode, *arguments, '--output', str(result)], check=True)
    drawing = ezdxf.readfile(result / 'redrawn.dxf')
    audit = drawing.audit()
    if audit.errors or audit.fixes or not expected <= {entity.dxftype() for entity in drawing.modelspace()}:
        raise RuntimeError(f'{mode} DXF failed readback')
    if not (result / 'cad-preview.png').is_file():
        raise RuntimeError(f'{mode} preview is missing')


def main():
    with TemporaryDirectory() as scratch:
        work = Path(scratch)
        source = work / 'source.png'
        image = Image.new('RGB', (200, 140), 'white')
        ImageDraw.Draw(image).rectangle((20, 20, 180, 120), outline='black', width=3)
        image.save(source)

        building = work / 'building.json'
        building.write_text(json.dumps({
            'crop_xyxy': [0, 0, 200, 140],
            'walls': [{'id': 'wall', 'axis': [[20, 20], [180, 20]], 'width': 8}],
            'openings': [{'id': 'window', 'wall': 'wall', 'offset': 70,
                          'length': 20, 'kind': 'window', 'certainty': 'clear'}],
            'regularization': [], 'omitted': [],
        }))
        landscape = work / 'landscape.json'
        landscape.write_text(json.dumps({
            'frame': [0, 0, 200, 140],
            'paths': [{'id': 'bed', 'layer': 'L-ZONE',
                       'd': 'M 20 20 L 180 20 C 170 100 30 100 20 20 Z'}],
        }))
        check('building', ['--source', str(source), '--layout', str(building)], work, {'INSERT'})
        check('landscape', ['--source', str(source), '--layout', str(landscape)], work, {'SPLINE'})
        check('pen', ['--simplified', str(source), '--approved'], work, {'HATCH'})
        print('All three exporters passed.')


if __name__ == '__main__':
    main()
