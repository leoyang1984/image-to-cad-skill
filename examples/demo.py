"""Render the three demo cases and write the images used by the README.

The layouts in this directory are hand-authored for this repository. Nothing is
traced from a third-party drawing, so the results can be published. Run from the
repository root:

    .venv/bin/python examples/demo.py
"""
import json
import shutil
from pathlib import Path
from subprocess import run
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CONVERT = ROOT / 'skills/image-to-cad/scripts/convert.py'
CASES = ROOT / 'docs/cases'


def blank_source(path, size=(960, 640)):
    """A plain sheet: plan geometry comes from the layout, not from this raster."""
    image = Image.new('RGB', size, 'white')
    ImageDraw.Draw(image).rectangle((8, 8, size[0] - 9, size[1] - 9), outline=(214, 214, 214))
    image.save(path)
    return path


def pen_sketch(path, size=(1200, 800)):
    """A synthetic pen study with tonal washes so the four DXF tones separate."""
    width, height = size
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    ink, mid, light = (26, 26, 26), (96, 96, 96), (188, 188, 188)

    draw.line((60, 650, 1140, 650), fill=ink, width=3)
    draw.line((60, 668, 1140, 668), fill=light, width=1)

    # Facade with a shaded pilaster and an eave shadow.
    draw.polygon([(280, 240), (600, 108), (920, 240)], outline=ink, width=3)
    draw.rectangle((300, 240, 900, 650), outline=ink, width=3)
    draw.rectangle((300, 240, 900, 272), fill=(196, 196, 196))
    draw.rectangle((300, 272, 372, 650), fill=(160, 160, 160))

    # Window band: pale glazing, mid-tone mullions, a darker pane run.
    draw.rectangle((380, 296, 868, 456), fill=(206, 206, 206))
    for x in range(380, 869, 68):
        draw.line((x, 296, x, 456), fill=mid, width=2)
    for y in (296, 350, 403, 456):
        draw.line((380, y, 868, y), fill=mid, width=2)
    draw.rectangle((380, 403, 652, 456), fill=(150, 150, 150))

    # Entrance: deep arch, recessed door, a dark threshold strip.
    draw.arc((520, 470, 680, 640), start=180, end=360, fill=ink, width=3)
    draw.line((520, 555, 520, 650), fill=ink, width=3)
    draw.line((680, 555, 680, 650), fill=ink, width=3)
    draw.rectangle((520, 555, 680, 650), fill=(120, 120, 120))
    draw.rectangle((536, 596, 664, 640), fill=(62, 62, 62))
    draw.rectangle((536, 630, 664, 640), fill=(30, 30, 30))

    for cx in (150, 1020):
        draw.line((cx, 590, cx, 650), fill=ink, width=2)
        draw.ellipse((cx - 46, 480, cx + 46, 572), outline=mid, width=2)
        draw.chord((cx - 40, 486, cx + 40, 566), start=200, end=340, fill=(176, 176, 176))

    for x in range(90, 1140, 26):
        draw.line((x, 690, x + 12, 702), fill=light, width=1)

    image.save(path)
    return path


def export(mode, arguments, work):
    result = work / mode
    run([sys.executable, str(CONVERT), mode, *arguments, '--output', str(result)], check=True)
    preview = result / 'cad-preview.png'
    if not preview.is_file():
        raise RuntimeError(f'{mode} produced no preview')
    target = CASES / f'demo-{mode}.png'
    shutil.copyfile(preview, target)
    return target


def main():
    CASES.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as scratch:
        work = Path(scratch)
        source = blank_source(work / 'source.png')
        sketch = pen_sketch(work / 'pen.png')
        written = [
            export('building', ['--source', str(source), '--layout', str(ROOT / 'examples/apartment.json')], work),
            export('landscape', ['--source', str(source), '--layout', str(ROOT / 'examples/garden.json')], work),
            export('pen', ['--simplified', str(sketch), '--approved'], work),
        ]
    for path in written:
        print(path.relative_to(ROOT))


if __name__ == '__main__':
    main()
