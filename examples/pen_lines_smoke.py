"""Verify native perspective strokes, reference provenance and approval gates."""
import hashlib
import json
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import ezdxf
from PIL import Image

from smoke import CONVERT


def main():
    with TemporaryDirectory() as scratch:
        work = Path(scratch)
        source = work / 'source.png'
        Image.new('RGB', (200, 140), 'white').save(source)
        simplified = work / 'clean.png'
        Image.new('RGB', (100, 70), 'white').save(simplified)
        layout = work / 'strokes.json'
        model = {
            'schema_version': 1, 'frame': [0, 0, 200, 140], 'interpretation': 'human',
            'paths': [
                {'id': 'eave', 'layer': 'P-OUTLINE', 'd': 'M 20 50 C 65 10 125 15 180 52'},
                {'id': 'panel', 'layer': 'P-PANEL', 'd': 'M 62 60 L 87 58 L 84 75 L 58 76 Z'},
                {'id': 'edge', 'layer': 'P-DETAIL', 'd': 'M 37 68 L 28 113'},
            ],
        }
        layout.write_text(json.dumps(model), encoding='utf-8')
        command = [sys.executable, str(CONVERT), 'pen',
                   '--source', str(source), '--layout', str(layout)]

        def convert(name, *extra, success=True):
            result = work / name
            finished = run([*command, '--output', str(result), *extra], text=True, capture_output=True)
            if (finished.returncode == 0) != success:
                raise RuntimeError(f'{name}: {finished.stderr}')
            if not success and result.exists():
                raise RuntimeError(f'{name}: failed conversion published an output')
            return result, finished

        direct, _ = convert('direct')
        doc = ezdxf.readfile(direct / 'redrawn.dxf')
        audit = doc.audit()
        assert not audit.errors and not audit.fixes and doc.units == 0
        expected = {'eave': ('SPLINE', 'P-OUTLINE', 35), 'panel': ('LWPOLYLINE', 'P-PANEL', 25),
                    'edge': ('LINE', 'P-DETAIL', 13)}
        actual = {}
        for entity in doc.modelspace():
            name = entity.get_xdata('I2CAD_PEN_LINE')[0].value
            layer = entity.dxf.layer
            actual[name] = (entity.dxftype(), layer, doc.layers.get(layer).dxf.lineweight)
            if name == 'edge':
                assert entity.dxf.start.isclose((37, 71, 0)) and entity.dxf.end.isclose((28, 26, 0))
            if name == 'panel':
                assert entity.closed and len(entity) == 4
        assert actual == expected and len(doc.modelspace()) == len(expected)
        svg = ElementTree.parse(direct / 'cad-vector.svg')
        assert all(p.get('fill') == 'none' for p in svg.findall('.//{*}path'))
        assert len(svg.findall('.//{*}path')) == 3
        assert (direct / 'review.html').is_file() and not (direct / 'cleaned.png').exists()
        report = json.loads((direct / 'report.json').read_text())
        assert report['representation'] == 'lines' and report['editability']['editable_entity_ratio'] == 1
        assert report['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()

        clean_hash = hashlib.sha256(simplified.read_bytes()).hexdigest()
        _, denied = convert('unapproved', '--simplified', str(simplified), success=False)
        assert 'approval' in denied.stderr
        approved, _ = convert('approved', '--simplified', str(simplified), '--approved',
                              '--approved-sha256', clean_hash)
        report = json.loads((approved / 'report.json').read_text())
        assert report['approved_image_sha256'] == clean_hash and not report['simplified_frame_match']
        assert (approved / 'cleaned.png').is_file()

        model['paths'].append({'id': 'reverse-edge', 'layer': 'P-DETAIL', 'd': 'M 28 113 L 37 68'})
        layout.write_text(json.dumps(model), encoding='utf-8')
        _, duplicate = convert('duplicate', success=False)
        assert 'duplicate stroke' in duplicate.stderr
        print('Pen lines: native editable strokes, preview, approval gate and duplicate checks passed.')


if __name__ == '__main__':
    main()
