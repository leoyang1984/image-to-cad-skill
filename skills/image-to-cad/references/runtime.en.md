# Runtime and layout schemas

[中文运行说明](runtime.md)

## Install and verify

Give the entire `skills/image-to-cad/` directory to the agent. It contains the conversion scripts and Python requirements. Run the commands below from the repository root. You can also use an existing compatible Python environment.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r skills/image-to-cad/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python skills/image-to-cad/scripts/convert.py --help
.venv/bin/python examples/smoke.py
.venv/bin/python examples/section_smoke.py
```

`examples/smoke.py` checks the original exporters. `examples/section_smoke.py` exercises section reconstruction and clean line extraction.

The verified environment is macOS arm64 with Python 3.11. On Windows, the interpreter path is `.venv\Scripts\python.exe`. Verify dependencies and conversion on the target machine. The command help lists `prepare`, `building`, `landscape`, `section`, and `pen`.

The direct dependencies are NumPy, OpenCV Headless, Shapely, ezdxf, Pillow, pypdfium2, and PyMuPDF. Install the versions in [requirements.txt](../requirements.txt). pip resolves their transitive dependencies. PyMuPDF renders the perspective PNG from DXF readback. Its distribution lists AGPL 3.0 or an Artifex commercial license.

For offline installation, download wheels on a connected machine with the same OS, architecture, and Python version. Copy `wheelhouse/` to the target machine.

```bash
# Connected machine
.venv/bin/python -m pip download --only-binary=:all: -r skills/image-to-cad/requirements.txt -d wheelhouse
# Target machine
.venv/bin/python -m pip install --no-index --find-links=wheelhouse -r skills/image-to-cad/requirements.txt
```

## Load the skill

Codex users can create a project-level link from the repository root, then invoke `$image-to-cad` in that project. If a link already exists, check its target. Restart Codex if the skill does not appear. [OpenAI Skill documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)

```bash
mkdir -p .agents/skills
ln -s ../../skills/image-to-cad .agents/skills/image-to-cad
```

For an agent that reads workspace files on request, point it to `skills/image-to-cad/SKILL.md` and have it run the commands from the repository root. Generating simplifications requires ImageGen in the agent environment. Python dependencies handle DXF compilation, export, and readback. Architectural plans, sections and landscape layouts can be interpreted directly from the source. The perspective exporter can use an already approved pen drawing.

## Prepare a source image

Use the pixel centers of the normalized source or PDF page. X increases to the right and Y increases downward. When you need to specify a PDF page, DPI, or EXIF orientation, prepare a reference PNG and build the layout against that image. Use a fresh output directory for each revision.

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py prepare drawing.pdf --page 1 --dpi 200 --output reference.png
```

## Without an image-generation tool

Plans can be built from the source without a simplification. The perspective route needs an
approved drawing: generate and compare it yourself when the environment can, or hand the source
and a prompt to the user, who generates the image with any image tool and saves it as
`simplified.png`. The handoff steps, prompt template and acceptance checklist are in
[scope and handoff](scope.md).

`--simplified` is re-encoded the same way `prepare` does it. When its size differs from the
source, the review page stretches it to the source frame as a visual aid only, and the report
sets `simplified_frame_match` to `false`.

## Architectural plan

Set `crop_xyxy: [0, 0, width, height]` for the whole frame. Each wall has an `id`, two endpoints in `axis: [[x1, y1], [x2, y2]]`, and a pixel `width`. Each opening has an `id`, a host wall ID in `wall`, its distance from the start of the wall axis in `offset`, a `length`, a `kind`, and a `certainty` value. Opening kinds are `door`, `window`, `garage`, `passage`, and `unresolved`. A confirmed swing door also needs `hinge: start|end` and `side: -1|1`. If the swing is unclear, use `unresolved` and set `certainty` to `needs_confirmation`. Record regularization and omissions in the top-level arrays `regularization` and `omitted`.

Check openings and circulation against the source. Preserve editable boundaries for unidentified objects. The full example is [examples/apartment.json](../../../examples/apartment.json); [examples/smoke.py](../../../examples/smoke.py) is a minimal synthetic layout.

An optional `stairs` array draws stair runs: each entry has an `id`, a
`rect: [x1, y1, x2, y2]`, a `treads` count and a `direction` (`north`, `south`, `east` or
`west`, the direction of ascent). Treads and an ascent arrow are drawn on the A-STAIR layer,
visible by default; walls and openings still come from `walls` and `openings`.

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py building --source reference.png --layout layout.json --output building-v1
```

## Landscape plan

Recommend a scope and explain which objects can be represented reliably. The user can add specific objects or areas. Interpret the paths against the source, keeping the site outline, both sides of paths, entrance gaps, and the main forms within structures. Record areas of uncertain use by their visible boundaries. Keep outlines open where the image crops them, and follow the agreed scope for paving marks, dots, and textures.

The layout has `frame: [0, 0, width, height]` and a `paths` array. Each path has a unique `id`, a `layer`, and a `d` string. Separate commands and coordinates with spaces. Use absolute `M x y`, `L x y`, `C x1 y1 x2 y2 x y`, and a final `Z` to close a path. Supported layers are `L-SITE-EDGE`, `L-WALK`, `L-ZONE`, `L-PAVILION`, `L-FORM`, `L-AUX`, and `L-STAIR`. The full example is [examples/garden.json](../../../examples/garden.json); [examples/smoke.py](../../../examples/smoke.py) includes a minimal path.

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py landscape --source reference.png --layout layout.json --output landscape-v1
```

If an architectural or landscape plan uses an approved simplification, add `--simplified approved.png --approved` to its command. The review page displays the simplification in the source frame for visual comparison. Use the source to verify critical relationships and allow justified regularization.

## Architectural sections

Use `section --intent reconstruct --source reference.png --layout section.json --output section-v1`.
See the [section schema](section.md) for component IDs, hosted openings, directed ramp connections,
regularization and the readback report. With already clean line art, `section --source clean.png
--input-route linework --output lines-v1` extracts unclassified editable lines. Use
`--simplified approved.png --approved` for a confirmed intermediate and optionally pin its SHA-256.

## Perspective pen drawing

Describe what to retain for each kind of object. For existing perspective line art, preserve panel divisions, main silhouettes, and key openings while reducing texture and background detail. For renderings, preserve the framing, perspective, depth of openings, and distant structures, then decide how to represent reflections, materials, people, and plants. Use continuous strokes and varied line weights. Prefer an opaque PNG with a white background for the approved drawing.

```bash
.venv/bin/python skills/image-to-cad/scripts/convert.py pen --simplified approved.png --approved --output pen-v1
```

The DXF uses four shades of solid HATCH to preserve the pen drawing's appearance. If users need to edit individual architectural components, redraw them as components. Check that circular ornaments, glazing gaps, and other white areas remain open after DXF readback. For a zoomable comparison, display SVG paths derived from the saved DXF.

## Outputs

Each workflow writes `redrawn.dxf`, `cad-preview.png`, `layout.json`, `report.json`, and `review.html`. Plan workflows retain their original review page names as well. The perspective workflow also writes `cad-vector.svg` and records the hatch rings in its layout. Use optional `pen --source original.png` to compare an original image. An approved simplification is exported as `cleaned.png` and its original SHA-256 is recorded in the report.
