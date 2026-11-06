"""Compile landscape paths into layered polylines and splines."""
import ezdxf


LAYERS = {
    "L-SITE-EDGE": ("场地外缘", (68, 72, 78)),
    "L-WALK": ("步道与广场", (32, 104, 166)),
    "L-ZONE": ("场地分区边界", (25, 133, 103)),
    "L-PAVILION": ("主体构筑物与入口", (153, 61, 67)),
    "L-FORM": ("主体内部造型", (135, 75, 163)),
    "L-AUX": ("附属构筑物", (153, 98, 41)),
    "L-STAIR": ("楼梯踏步与平台", (183, 72, 13)),
}

def add_outline(modelspace, outline, height):
    tokens = iter(outline["d"].split())

    def point():
        return float(next(tokens)), height - 1 - float(next(tokens))

    if next(tokens) != "M":
        raise ValueError("An outline must begin with M")
    start = current = point()
    segments = []
    closed = False
    for command in tokens:
        if command == "L":
            end = point()
            segments.append((current, end))
        elif command == "C":
            handle1, handle2, end = point(), point(), point()
            segments.append((current, handle1, handle2, end))
        elif command == "Z":
            closed = True
            if current != start:
                segments.append((current, start))
            if next(tokens, None) is not None:
                raise ValueError("Z must end the outline")
            break
        else:
            raise ValueError(f"Unsupported outline command {command}")
        current = end
    if not segments:
        raise ValueError("An outline requires at least one segment")

    attrs = {"layer": outline["layer"]}
    if all(len(segment) == 2 for segment in segments):
        vertices = [start, *(segment[-1] for segment in segments)]
        if closed:
            vertices.pop()
        entity = modelspace.add_lwpolyline(vertices, close=closed, dxfattribs=attrs)
    else:
        # A cubic spline with triple internal knots can represent consecutive
        # Bezier curves, including the sharp changes at entrance jambs.
        controls = [start]
        for segment in segments:
            if len(segment) == 2:
                a, b = segment
                h1 = tuple((2*x+y)/3 for x, y in zip(a, b))
                h2 = tuple((x+2*y)/3 for x, y in zip(a, b))
                controls.extend((h1, h2, b))
            else:
                controls.extend(segment[1:])
        count = len(segments)
        knots = [0]*4 + [k for k in range(1, count) for _ in range(3)] + [count]*4
        entity = modelspace.add_open_spline(controls, degree=3, knots=knots, dxfattribs=attrs)
        entity.closed = closed
    entity.set_xdata("LANDSCAPE", [(1000, outline["id"])])

def write_landscape_dxf(model, dxf):
    """Compile the agreed landscape paths in the original image frame."""
    height = model["frame"][3]
    doc = ezdxf.new("R2010")
    doc.units = 0
    doc.appids.new("LANDSCAPE")
    used_layers = {outline["layer"] for outline in model["paths"]}
    for layer, (_, rgb) in LAYERS.items():
        if layer in used_layers:
            doc.layers.new(layer).rgb = rgb
    modelspace = doc.modelspace()
    for outline in model["paths"]:
        if outline["layer"] not in LAYERS:
            raise ValueError(f"Unknown layer {outline['layer']}")
        add_outline(modelspace, outline, height)
    doc.saveas(dxf)
    return used_layers
