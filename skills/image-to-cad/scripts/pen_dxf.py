"""Trace approved pen strokes as graded DXF fills and render a DXF readback."""
from collections import Counter
import re
from xml.etree import ElementTree as ET

import cv2
import ezdxf
import pymupdf
from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, svg
from ezdxf.math import BoundingBox2d
from shapely import make_valid, union_all
from shapely.geometry import Polygon


def convert_pen(source, out):
    gray = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError('Cannot read the approved pen image')
    height, width = gray.shape
    scale = 3
    enlarged = cv2.resize(gray, (width * scale, height * scale), interpolation=cv2.INTER_LINEAR)
    tones = [(222, 199), (169, 131), (110, 62), (61, 18)]

    doc = ezdxf.new('R2010')
    doc.units = 0
    doc.set_modelspace_vport(height, center=(width / 2, height / 2))
    space = doc.modelspace()
    def ring(contour):
        points = cv2.approxPolyDP(contour, 0.78, True).reshape(-1, 2)
        return [(float((x + .5) / scale - .5), float(height - .5 - (y + .5) / scale))
                for x, y in points]
    def surfaces(geometry):
        if geometry.geom_type == 'Polygon':
            if geometry.area >= .42:
                yield geometry
        elif geometry.geom_type in ('MultiPolygon', 'GeometryCollection'):
            for part in geometry.geoms:
                yield from surfaces(part)


    for number, (cutoff, shade) in enumerate(tones, 1):
        name = f'P-PEN-{number:02}'
        rgb = (shade,) * 3
        doc.layers.new(name).rgb = rgb
        mask = (enlarged < cutoff).astype('uint8')
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        for index, contour in enumerate(contours):
            if hierarchy[0, index, 3] >= 0 or cv2.contourArea(contour) < 4:
                continue
            outer = ring(contour)
            if len(outer) < 3:
                continue
            holes = []
            child = hierarchy[0, index, 2]
            while child >= 0:
                if cv2.contourArea(contours[child]) >= 7:
                    points = ring(contours[child])
                    if len(points) >= 3:
                        holes.extend(surfaces(make_valid(Polygon(points))))
                child = hierarchy[0, child, 0]
            # Subtract cutouts independently so even an intersecting ring cannot become ink.
            exterior = make_valid(Polygon(outer))
            for shape in surfaces(exterior.difference(union_all(holes))):
                hatch = space.add_hatch(dxfattribs={'layer': name})
                hatch.set_solid_fill(style=0, rgb=rgb)
                hatch.paths.add_polyline_path(list(shape.exterior.coords)[:-1], flags=1)
                for hole in shape.interiors:
                    hatch.paths.add_polyline_path(list(hole.coords)[:-1], flags=16)

    space.set_redraw_order((entity.dxf.handle, entity.dxf.handle) for entity in space)
    dxf_path = out / 'redrawn.dxf'
    doc.saveas(dxf_path)
    saved = ezdxf.readfile(dxf_path)
    audit = saved.audit()
    if audit.errors or audit.fixes:
        raise ValueError('DXF audit requires repair')
    entities = list(saved.modelspace())
    if not entities or any(entity.dxftype() != 'HATCH' or not entity.dxf.solid_fill for entity in entities):
        raise ValueError('The image must contain pen strokes that can be exported as solid hatches')
    for entity in entities:
        loops = entity.paths.paths
        if not loops or any(not loop.is_closed or len(loop.vertices) < 3 for loop in loops):
            raise ValueError('Invalid hatch boundary after DXF readback')
        if not Polygon(loops[0].vertices, [hole.vertices for hole in loops[1:]]).is_valid:
            raise ValueError('Invalid hatch topology after DXF readback')

    renderer = svg.SVGBackend()
    settings = config.Configuration(background_policy=config.BackgroundPolicy.WHITE)
    Frontend(RenderContext(saved), renderer, settings).draw_layout(saved.modelspace(), finalize=True)
    drawing = renderer.get_xml_root_element(
        layout.Page(width, height, units=layout.Units.px),
        render_box=BoundingBox2d([(-.5, -.5), (width - .5, height - .5)]),
    )
    # Put style values directly on paths for MuPDF's SVG renderer.
    css = ' '.join(element.text for element in drawing.findall('.//{*}style'))
    fills = {name: re.search(r'(?<!-)fill: ([^;]+);', declaration).group(1)
             for name, declaration in re.findall(r'\.([\w-]+)\s*\{([^}]+)\}', css)}
    paths = drawing.findall('.//{*}path')
    if len(paths) != len(entities):
        raise ValueError('The DXF preview dropped hatch entities')
    for path in paths:
        path.set('fill', fills[path.attrib.pop('class')])
        path.set('fill-rule', 'evenodd')
    vector_preview = ET.tostring(drawing)
    (out / 'cad-vector.svg').write_bytes(vector_preview)
    with pymupdf.open(stream=vector_preview, filetype='svg') as render:
        page = render[0]
        page.get_pixmap(matrix=pymupdf.Matrix(width / page.rect.width, height / page.rect.height),
                        alpha=False).save(out / 'cad-preview.png')
    return {
        'entities': len(entities),
        'layers': dict(Counter(entity.dxf.layer for entity in entities)),
        'holes': sum(len(entity.paths.paths) - 1 for entity in entities),
        'frame_px': [width, height],
    }
