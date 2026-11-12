"""Build the offline, single-canvas plan review page."""
import base64
import html
import json

import cv2
import numpy as np

from building import read_native
from preview_primitives import paths_svg, render


def data_uri(path, media_type):
    return f"data:{media_type};base64," + base64.b64encode(path.read_bytes()).decode()

def write_overlay_page(out, frame, *, source_path, simplified_path, dxf, labels, title,
                       views, filename, download_name=None, focus=None):
    left, top, right, bottom = frame
    width, height = right-left, bottom-top
    doc, paths = read_native(dxf, (left, top), bottom)
    groups = {}
    for path in paths:
        groups.setdefault(path['layer'], []).append(path)
    svg_parts = []
    legend = []
    if focus:
        x1, y1, x2, y2 = focus
        xmin, ymin, xmax, ymax = int(x1), int(y1), int(x2 + 1), int(y2 + 1)
    else:
        xmin, ymin, xmax, ymax = 0, 0, width, height
    preview_size = [xmax - xmin, ymax - ymin]
    # Keep large input sheets inexpensive. SVG keeps the full-resolution vectors.
    zoom = 2 if preview_size[0] * preview_size[1] <= 2_500_000 else 1
    preview = render([], preview_size, zoom=zoom)
    for layer, objects in groups.items():
        rgb = tuple(doc.layers.get(layer).rgb or (34, 34, 34))
        color = '#{:02x}{:02x}{:02x}'.format(*rgb)
        layer_name = html.escape(layer, quote=True)
        svg_parts.append(f'<g data-layer="{layer_name}">{paths_svg(objects, color)}</g>')
        legend.append(f'<label style="color:{color}"><input type="checkbox" data-toggle="{layer_name}" checked> {labels[layer]}</label>')
        # Use the rendered DXF paths as an antialiased coverage mask.
        local = [obj | {'coordinates': [(x - xmin, y - ymin) for x, y in obj['coordinates']]}
                 for obj in objects]
        ink = render(local, preview_size, zoom=zoom, stroke=zoom)[:, :, 0]
        mask = ink < 255
        coverage = ((255 - ink[mask]) / np.float32(235))[:, None]
        preview[mask] = preview[mask] * (1 - coverage) + coverage * np.asarray(rgb[::-1])
    if not cv2.imwrite(str(out/'cad-preview.png'), preview):
        raise OSError('Could not write DXF readback preview')
    write_review_page(out, frame, source_path=source_path, simplified_path=simplified_path, dxf=dxf,
                      title=title, views=views, filename=filename, download_name=download_name,
                      focus=focus, svg_parts=svg_parts, legend=legend)
    return doc


def write_trace_review(out, frame, *, source_path, simplified_path, dxf, hatches):
    groups = {}
    for hatch in hatches:
        groups.setdefault(hatch['layer'], []).append(hatch)
    svg_parts, legend = [], []
    for layer, entries in groups.items():
        color = '#{:02x}{:02x}{:02x}'.format(*entries[0]['rgb'])
        shapes = []
        for hatch in entries:
            data = ' '.join('M' + ' L'.join(f'{x:.8f},{y:.8f}' for x, y in ring) + ' Z'
                            for ring in hatch['rings'])
            shapes.append(f'<path d="{data}" fill="{color}" fill-rule="evenodd"/>')
        svg_parts.append(f'<g data-layer="{layer}">{"".join(shapes)}</g>')
        legend.append(f'<label style="color:{color}"><input type="checkbox" data-toggle="{layer}" checked> {layer}</label>')
    write_review_page(out, frame, source_path=source_path, simplified_path=simplified_path, dxf=dxf,
                      title='钢笔线稿描摹查看', views={}, filename='review.html',
                      svg_parts=svg_parts, legend=legend,
                      source_label='原图' if simplified_path else '确认稿')


def write_review_page(out, frame, *, source_path, simplified_path, dxf, title, views, filename,
                      svg_parts, legend, focus=None, download_name=None, source_label='原图'):
    left, top, right, bottom = frame
    width, height = right - left, bottom - top
    source_type = 'image/jpeg' if source_path.suffix.lower() in ('.jpg', '.jpeg') else 'image/png'
    source = data_uri(source_path, source_type)
    dxf_uri = data_uri(dxf, 'application/dxf')
    view_box = f'-.5 -.5 {width} {height}'
    source_image = f'<image href="{source}" x="-.5" y="-.5" width="{width}" height="{height}" preserveAspectRatio="none"/>'
    generated_image = ''
    simplified_toggle = ''
    if simplified_path is not None:
        generated_type = 'image/jpeg' if simplified_path.suffix.lower() in ('.jpg', '.jpeg') else 'image/png'
        generated = data_uri(simplified_path, generated_type)
        generated_image = f'<image href="{generated}" x="-.5" y="-.5" width="{width}" height="{height}" preserveAspectRatio="none"/>'
        simplified_toggle = '<label><input id="show-simplified" type="checkbox" checked> 已确认简化图</label>'
    page = """<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PAGE_TITLE</title>
<style>
body{margin:0;background:#f3f4f0;color:#25362e;font:16px system-ui}
header,main{padding:18px 24px}h1{margin:0 0 8px;font-size:24px}
button{font:inherit;padding:6px 10px;margin-right:8px;background:white;border:1px solid #aab8af;border-radius:5px}
a{color:#155648}nav{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
fieldset{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:10px 0;padding:6px 10px 9px;border:1px solid #d1d9d0;border-radius:5px}
legend{font-weight:600}
main{padding-top:0}
svg{width:100%;height:clamp(360px,68vh,950px);display:block;background:white;border:1px solid #d1d9d0;border-radius:7px;cursor:grab;touch-action:none;user-select:none}
svg.dragging{cursor:grabbing}
svg path{stroke-width:1.35}
</style>
<header><h1>PAGE_TITLE</h1>
<p>切换底图和构件图层查看差异。需要调整时，在对话里指出位置和想改的内容。</p>
<fieldset><legend>文件</legend>
<label><input id="show-source" type="checkbox" checked> SOURCE_LABEL</label>
SIMPLIFIED_TOGGLE
<label><input id="show-dxf" type="checkbox" checked> DXF</label>
</fieldset>
<fieldset><legend>DXF 图层</legend>LAYER_LEGEND</fieldset>
<nav><button id="zoom-in" aria-label="放大">＋</button><button id="zoom-out" aria-label="缩小">−</button>
<button id="full">恢复全图</button>VIEW_BUTTONS
<a href="DXF_URI" download="DXF_NAME">下载 DXF</a></nav></header>
<main>
<svg id="drawing" viewBox="INITIAL_BOX" aria-label="原图、简化图与 DXF 的叠合画布">
<g id="source">SOURCE_IMAGE</g>
<g id="simplified">GENERATED_IMAGE</g>
<g id="dxf">CAD_PATHS</g>
</svg>
<p>在图上滚动缩放，按住拖动平移。坐标以原图像素计，比例未校准。</p></main>
<script>
const drawing = document.getElementById("drawing");
const views = VIEW_MAP;
const fullWidth = Number(views.full.split(" ")[2]);
function currentBox() {
  const {x, y, width, height} = drawing.viewBox.baseVal;
  return {x, y, width, height};
}
function setBox(x, y, width, height) {
  drawing.setAttribute("viewBox", [x, y, width, height].join(" "));
}
function zoom(factor, anchor) {
  const {x, y, width, height} = currentBox();
  const targetWidth = Math.max(fullWidth / 16, Math.min(fullWidth * 2, width * factor));
  const ratio = targetWidth / width;
  const {x: cx, y: cy} = anchor ?? {x: x + width / 2, y: y + height / 2};
  setBox(cx + (x - cx) * ratio, cy + (y - cy) * ratio, targetWidth, height * ratio);
}
for (const [id, box] of Object.entries(views)) {
  document.getElementById(id).onclick = () => drawing.setAttribute("viewBox", box);
}
document.getElementById("zoom-in").onclick = () => zoom(1 / 1.25);
document.getElementById("zoom-out").onclick = () => zoom(1.25);
drawing.addEventListener("wheel", event => {
  if (!event.deltaY) return;
  const matrix = drawing.getScreenCTM();
  if (!matrix) return;
  event.preventDefault();
  const cursor = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  zoom(event.deltaY < 0 ? 1 / 1.12 : 1.12, cursor);
}, {passive: false});
let drag;
drawing.addEventListener("pointerdown", event => {
  if (event.button !== 0 || drag) return;
  const matrix = drawing.getScreenCTM();
  if (!matrix) return;
  const inverse = matrix.inverse();
  const start = new DOMPoint(event.clientX, event.clientY).matrixTransform(inverse);
  drag = {id: event.pointerId, inverse, start, box: currentBox()};
  drawing.setPointerCapture(event.pointerId);
  drawing.classList.add("dragging");
});
drawing.addEventListener("pointermove", event => {
  if (drag?.id !== event.pointerId) return;
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(drag.inverse);
  const {x, y, width, height} = drag.box;
  setBox(x + drag.start.x - point.x, y + drag.start.y - point.y, width, height);
});
drawing.addEventListener("lostpointercapture", event => {
  if (drag?.id !== event.pointerId) return;
  drag = undefined;
  drawing.classList.remove("dragging");
});
const files = ["source", "simplified", "dxf"].filter(id => document.getElementById("show-" + id));
function updateFiles() {
  const visible = files.filter(id => document.getElementById("show-" + id).checked);
  for (const id of files) {
    const group = document.getElementById(id);
    group.setAttribute("visibility", visible.includes(id) ? "visible" : "hidden");
    group.setAttribute("opacity", id !== "dxf" && visible.length > 1 ? ".45" : "1");
  }
}
for (const id of files) document.getElementById("show-" + id).onchange = updateFiles;
updateFiles();
for (const toggle of document.querySelectorAll("[data-toggle]")) {
  toggle.onchange = () => document.querySelector('[data-layer="' + toggle.dataset.toggle + '"]')
    .setAttribute("display", toggle.checked ? "inline" : "none");
}
</script></html>"""
    for token, value in {
        'DXF_URI': dxf_uri, 'INITIAL_BOX': (
            f'{focus[0]} {focus[1]} {focus[2] - focus[0]} {focus[3] - focus[1]}' if focus else view_box
        ), 'SOURCE_IMAGE': source_image,
        'GENERATED_IMAGE': generated_image, 'CAD_PATHS': ''.join(svg_parts),
        'SOURCE_LABEL': source_label,
        'SIMPLIFIED_TOGGLE': simplified_toggle,
        'LAYER_LEGEND': '　'.join(legend),
        'PAGE_TITLE': html.escape(title), 'DXF_NAME': html.escape(download_name or dxf.name, quote=True),
        'VIEW_BUTTONS': ''.join(
            f'<button id="{html.escape(key, quote=True)}">{html.escape(label)}</button>'
            for key, (label, _) in views.items()
        ),
        'VIEW_MAP': json.dumps({'full': view_box, **{key: box for key, (_, box) in views.items()}}),
    }.items():
        page = page.replace(token, value)
    (out/filename).write_text(page, encoding='utf-8')
