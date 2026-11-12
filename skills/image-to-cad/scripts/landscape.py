"""Compile landscape paths into layered polylines and splines."""
import ezdxf

from path_geometry import add_native_path, parse_path


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
    segments, closed = parse_path(outline["d"], height)
    entity = add_native_path(modelspace, segments, closed, {"layer": outline["layer"]})
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
