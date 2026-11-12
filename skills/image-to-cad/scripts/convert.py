#!/usr/bin/env python3
"""Generate audited CAD from a structured plan or an approved pen drawing."""
import argparse
import json
import shutil
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


def export_drawing(args, out):
    import cv2
    from review_page import write_overlay_page
    from building import compile_layout
    from landscape import LAYERS, write_landscape_dxf

    model = json.loads(args.layout.read_text(encoding='utf-8')) if args.layout else None
    with TemporaryDirectory() as scratch:
        source = Path(scratch) / 'source.png'
        metadata = prepare_image(args.source, source)
        width, height = metadata['width'], metadata['height']
        frame = [0, 0, width, height]
        simplified = simplified_meta = None
        if args.simplified:
            simplified = out / 'cleaned.png'
            simplified_meta = prepare_image(args.simplified, simplified)
        extraction = None
        report, views = {}, {}
        if args.mode == 'section':
            from section import LAYERS as SECTION_LAYERS, compile_section

            if model is None:
                from linework import extract_linework

                model, extraction = extract_linework(cv2.imread(str(source)), frame)
            if not isinstance(model, dict) or not isinstance(model.get('source_image', {}), dict):
                raise ValueError('Section layout and source_image must be objects')
            prior_hash = model.get('source_image', {}).get('sha256')
            if prior_hash and prior_hash != metadata['source_sha256']:
                raise ValueError('The section layout source hash differs from the supplied source')
            model, report = compile_section(model, frame, out / 'redrawn.dxf')
            model.update(source_image={
                'name': args.source.name, 'sha256': metadata['source_sha256'],
                'coordinate_system': metadata['coordinate_system'],
            }, input_route=args.input_route)
            if model.get('focus'):
                x1, y1, x2, y2 = model['focus']
                views['section-focus'] = ('放大剖面', f'{x1} {y1} {x2 - x1} {y2 - y1}')
            labels = {layer: label for layer, label, _ in SECTION_LAYERS.values()}
            title = '建筑剖面叠合查看'
        elif args.mode == 'building':
            if model['crop_xyxy'] != frame:
                raise ValueError('The layout frame must match the source image')
            model.update(source=str(source), colored_components=True, symbol_blocks=True)
            compile_layout(model, out)
            labels = {
                'A-WALL': '墙体', 'A-DOOR': '平开门', 'A-WINDOW': '窗',
                'A-GARAGE-DOOR': '车库门', 'A-OPENING-REVIEW': '待确认开口', 'A-STAIR': '楼梯',
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
        filename = 'review.html' if args.mode == 'section' else f'{args.output.name}-review.html'
        saved = write_overlay_page(
            out, frame, source_path=source, simplified_path=simplified,
            dxf=out / 'redrawn.dxf', labels=labels, title=title, views=views, filename=filename,
            focus=model.get('focus') if args.mode == 'section' else None,
        )
        if not len(saved.modelspace()) or cv2.imread(str(out / 'cad-preview.png')) is None:
            raise ValueError('The readback has no previewable entities')
        audit = saved.audit()
        if audit.errors or audit.fixes:
            raise ValueError('DXF audit requires repair')
        report_file = out / 'report.json'
        if args.mode == 'section':
            from section import audit_section

            audit_section(saved, model, report)
            if extraction:
                report['linework_extraction'] = extraction
                report['limitations'].append('Raster extraction produces unclassified linework; building semantics require interpretation.')
        elif report_file.exists():
            report = json.loads(report_file.read_text())
        if filename != 'review.html':
            shutil.copyfile(out / filename, out / 'review.html')
        types = {entity.dxftype() for entity in saved.modelspace()}
        report.setdefault('relationship', {
            'status': 'needs_review' if report.get('needs_confirmation') else (
                'pass' if report.get('opening_checks') else 'not_assessed'
            ),
            'hosted_openings': report.get('opening_checks', []),
        })
        report.setdefault('geometry', {'status': 'pass', 'dxf_audit_errors': len(audit.errors)})
        report.setdefault('editability', {
            'status': 'pass', 'entity_types': sorted(types), 'geometry_is_layered': True,
        })
        report.setdefault('cleanliness', {
            'status': 'pass', 'has_hatch': 'HATCH' in types, 'has_text': bool(types & {'TEXT', 'MTEXT'}),
            'visual_review_required': True,
        })
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
            model['simplified'] = args.simplified_name
        (out / 'layout.json').write_text(json.dumps(model, ensure_ascii=False, indent=2) + '\n')
        return report


def drawing_arguments(parser, args):
    if args.mode == 'prepare':
        return
    expected = 'trace' if args.mode == 'pen' else 'reconstruct'
    if args.intent and args.intent != expected:
        parser.error(f'{args.mode} supports --intent {expected}')
    args.intent = expected
    if args.simplified and not args.approved:
        parser.error('Obtain explicit user approval before exporting this simplified image')
    if args.approved_sha256 and not args.simplified:
        parser.error('--approved-sha256 requires --simplified')
    if args.source and args.source.suffix.lower() == '.pdf':
        parser.error('Run prepare with the desired PDF page and DPI, then use its PNG as --source')
    args.input_route = args.input_route or ('simplified' if args.simplified else 'direct')
    if (args.input_route == 'simplified') != bool(args.simplified):
        parser.error('Use --simplified together with the simplified input route')
    if args.mode == 'section' and args.input_route != 'linework' and not args.layout:
        parser.error('Provide --layout, or select --input-route linework for automatic extraction')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    prepare = commands.add_parser('prepare', help='Normalize an image or render one PDF page to PNG')
    prepare.add_argument('source', type=Path)
    prepare.add_argument('--page', type=int, default=1)
    prepare.add_argument('--dpi', type=int, default=200)
    prepare.add_argument('--output', type=Path, required=True)
    for mode in ('building', 'landscape', 'section', 'pen'):
        command = commands.add_parser(mode)
        command.add_argument('--source', type=Path, required=mode != 'pen')
        if mode != 'pen':
            command.add_argument('--layout', type=Path, required=mode != 'section')
        if mode == 'section':
            command.add_argument('--input-route', choices=('direct', 'simplified', 'linework'))
        else:
            command.set_defaults(input_route=None)
        command.add_argument('--intent', choices=('reconstruct', 'trace'))
        command.add_argument('--simplified', type=Path, required=mode == 'pen')
        command.add_argument('--approved', action='store_true',
                             help='The user explicitly approved this exact simplified image')
        command.add_argument('--approved-sha256',
                             help='Optionally pin the approved image bytes to a SHA-256 digest')
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    drawing_arguments(parser, args)
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
        approved_hash = None
        if args.simplified:
            args.simplified_name = args.simplified.name
            snapshot = Path(scratch) / ('approved' + args.simplified.suffix)
            shutil.copyfile(args.simplified, snapshot)
            approved_hash = sha256(snapshot.read_bytes()).hexdigest()
            if args.approved_sha256 and approved_hash != args.approved_sha256.lower():
                parser.error('The simplification does not match --approved-sha256')
            args.simplified = snapshot
        if args.mode == 'pen':
            from pen_dxf import convert_pen
            from review_page import write_trace_review

            cleaned = out / 'cleaned.png'
            report = convert_pen(args.simplified, out)
            prepare_image(args.simplified, cleaned)
            model_file = out / 'layout.json'
            model = json.loads(model_file.read_text(encoding='utf-8'))
            model['approved_image'] = {'name': args.simplified_name, 'sha256': approved_hash}
            original = cleaned
            if args.source:
                original = Path(scratch) / 'source.png'
                metadata = prepare_image(args.source, original)
                report['source_frame_match'] = report['frame_px'] == [metadata['width'], metadata['height']]
                report['source_sha256'] = metadata['source_sha256']
            write_trace_review(out, model['frame'], source_path=original,
                               simplified_path=cleaned if args.source else None,
                               dxf=out / 'redrawn.dxf', hatches=model['hatches'])
            model_file.write_text(json.dumps(model, ensure_ascii=False, separators=(',', ':')) + '\n',
                                  encoding='utf-8')
            report.update(
                review_page='review.html', relationship={'status': 'not_assessed'},
                geometry={'status': 'pass', 'valid_hatch_boundaries': report['entities']},
                editability={'status': 'pass', 'entity_types': ['HATCH'], 'geometry_is_layered': True},
                cleanliness={'status': 'needs_review', 'visual_review_required': True},
            )
        else:
            report = export_drawing(args, out)
        if approved_hash:
            report['approved_image_sha256'] = approved_hash
        report.update(mode=args.mode, intent=args.intent, input_route=args.input_route,
                      units='uncalibrated raster pixels')
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        if args.output.exists():
            parser.error(f'Output already exists: {args.output}')
        out.rename(args.output)
    print(args.output.resolve())


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(f'error: {error}') from None
