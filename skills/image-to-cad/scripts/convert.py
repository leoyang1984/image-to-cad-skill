#!/usr/bin/env python3
"""Generate audited CAD from a structured plan or an approved pen drawing."""
import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

def prepare_image(source, target, page=1, dpi=200):
    import cv2
    from image_input import load_image

    image, metadata = load_image(source, page=page, dpi=dpi)
    if not cv2.imwrite(str(target), image):
        raise OSError(f'Could not write {target}')
    return metadata


def export_plan(args, out):
    import cv2
    from review_page import write_overlay_page
    from building import compile_layout
    from landscape import LAYERS, write_landscape_dxf

    model = json.loads(args.layout.read_text(encoding='utf-8'))
    with TemporaryDirectory() as scratch:
        source = Path(scratch) / 'source.png'
        metadata = prepare_image(args.source, source)
        width, height = metadata['width'], metadata['height']
        frame = [0, 0, width, height]
        simplified = simplified_meta = None
        if args.simplified:
            simplified = Path(scratch) / 'simplified.png'
            simplified_meta = prepare_image(args.simplified, simplified)
        if args.mode == 'building':
            if model['crop_xyxy'] != frame:
                raise ValueError('The layout frame must match the source image')
            model.update(source=str(source), colored_components=True, symbol_blocks=True)
            compile_layout(model, out)
            labels = {
                'A-WALL': '墙体', 'A-DOOR': '平开门', 'A-WINDOW': '窗',
                'A-GARAGE-DOOR': '车库门', 'A-OPENING-REVIEW': '待确认开口',
            }
            title = '建筑平面图叠合查看'
        else:
            if model['frame'] != frame:
                raise ValueError('The layout frame must match the source image')
            ids = [path['id'] for path in model['paths']]
            if not ids or len(ids) != len(set(ids)):
                raise ValueError('Landscape paths need unique IDs and cannot be empty')
            write_landscape_dxf(model, out / 'redrawn.dxf')
            labels = {layer: label for layer, (label, _) in LAYERS.items()}
            title = '景观平面图叠合查看'
        filename = f'{args.output.name}-review.html'
        saved = write_overlay_page(
            out, frame, source_path=source, simplified_path=simplified,
            dxf=out / 'redrawn.dxf', labels=labels, title=title, views={}, filename=filename,
        )
        if not len(saved.modelspace()) or cv2.imread(str(out / 'cad-preview.png')) is None:
            raise ValueError('The readback has no previewable entities')
        audit = saved.audit()
        if audit.errors or audit.fixes:
            raise ValueError('DXF audit requires repair')
        report_file = out / 'report.json'
        report = json.loads(report_file.read_text()) if report_file.exists() else {}
        report.update(entities=len(saved.modelspace()), source_sha256=metadata['source_sha256'],
                      review_page=filename)
        if simplified_meta:
            size = [simplified_meta['width'], simplified_meta['height']]
            report['simplified_size_px'] = size
            report['simplified_frame_match'] = size == [width, height]
            if not report['simplified_frame_match']:
                print('warning: the simplified image differs in size from the source; '
                      'the review page stretches it to the source frame', file=sys.stderr)
        model['source'] = args.source.name
        if args.simplified:
            model['simplified'] = args.simplified.name
        (out / 'layout.json').write_text(json.dumps(model, ensure_ascii=False, indent=2) + '\n')
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    prepare = commands.add_parser('prepare', help='Normalize an image or render one PDF page to PNG')
    prepare.add_argument('source', type=Path)
    prepare.add_argument('--page', type=int, default=1)
    prepare.add_argument('--dpi', type=int, default=200)
    prepare.add_argument('--output', type=Path, required=True)
    for mode in ('building', 'landscape', 'pen'):
        command = commands.add_parser(mode)
        if mode != 'pen':
            command.add_argument('--source', type=Path, required=True)
            command.add_argument('--layout', type=Path, required=True)
        command.add_argument('--simplified', type=Path, required=mode == 'pen')
        command.add_argument('--approved', action='store_true',
                             help='The user explicitly approved this exact simplified image')
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    if args.mode != 'prepare' and args.simplified and not args.approved:
        parser.error('Obtain explicit user approval before exporting this simplified image')
    if args.mode in ('building', 'landscape') and args.source.suffix.lower() == '.pdf':
        parser.error('Run prepare with the desired PDF page and DPI, then use its PNG as --source')
    if args.output.exists():
        parser.error(f'Output already exists: {args.output}')
    if args.mode == 'prepare':
        if args.output.suffix.lower() != '.png' or args.dpi <= 0:
            parser.error('Use a .png output and a positive DPI')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps(prepare_image(args.source, args.output, args.page, args.dpi), ensure_ascii=False))
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.output.parent) as scratch:
        out = Path(scratch) / 'deliverables'
        out.mkdir()
        if args.mode == 'pen':
            from pen_dxf import convert_pen

            report = convert_pen(args.simplified, out)
        else:
            report = export_plan(args, out)
        if args.simplified:
            report['approved_image_sha256'] = sha256(args.simplified.read_bytes()).hexdigest()
        report.update(mode=args.mode, units='uncalibrated raster pixels')
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        if args.output.exists():
            parser.error(f'Output already exists: {args.output}')
        out.rename(args.output)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
