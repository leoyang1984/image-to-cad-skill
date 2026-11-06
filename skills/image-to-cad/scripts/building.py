"""Compile visually interpreted walls and openings into editable CAD."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import cv2
import ezdxf
import numpy as np
from shapely import union_all
from shapely.geometry import LineString, Polygon, box

from preview_primitives import render


COMPONENT_STYLES = {
    'A-WALL': (7, None),
    'A-DOOR': (3, (25, 128, 91)),
    'A-WINDOW': (5, (23, 103, 167)),
    'A-GARAGE-DOOR': (6, (144, 65, 157)),
    'A-OPENING-REVIEW': (30, (181, 93, 28)),
}

def wall_frame(wall):
    a,b=np.array(wall['axis'],float);delta=b-a;length=float(np.linalg.norm(delta))
    if length<=0 or wall['width']<=0:raise ValueError('Invalid wall')
    u=delta/length;n=np.array([-u[1],u[0]])
    return a,u,n,length

def read_native(path,origin,height):
    """Preview geometry comes from actual DXF, including native ARC sampling."""
    doc=ezdxf.readfile(path);objects=[]
    entities = (
        (entity, part)
        for entity in doc.modelspace()
        for part in (entity.virtual_entities() if entity.dxftype() == 'INSERT' else [entity])
    )
    for parent, ent in entities:
        kind=ent.dxftype()
        if kind=='LINE':points=[ent.dxf.start,ent.dxf.end];closed=False
        elif kind=='LWPOLYLINE':points=ent.get_points('xy');closed=bool(ent.closed)
        elif kind=='SPLINE':
            points=list(ent.flattening(0.25));closed=bool(ent.closed)
        elif kind=='ARC':
            start=ent.dxf.start_angle;angle=(ent.dxf.end_angle-start)%360
            theta=np.deg2rad(np.linspace(start,start+angle,max(3,int(angle)+1)))
            points=np.array([ent.dxf.center.x+ent.dxf.radius*np.cos(theta),ent.dxf.center.y+ent.dxf.radius*np.sin(theta)]).T;closed=False
        else:raise ValueError(f'Unexpected native entity {kind}')
        local=[[float(p[0]-origin[0]),float(height-1-p[1]-origin[1])] for p in points]
        objects.append({'id':parent.dxf.handle,'coordinates':local,'closed':closed,'layer':parent.dxf.layer,'native_type':kind})
    return doc,objects

def compile_layout(model,out):
    source=Path(model['source']);image=cv2.imread(str(source))
    if image is None:raise ValueError('Source missing')
    left,top,right,bottom=model['crop_xyxy'];fh,fw=image.shape[:2];w,h=right-left,bottom-top
    if not 0<=left<right<=fw or not 0<=top<bottom<=fh:raise ValueError('Invalid crop')
    crop=image[top:bottom,left:right];clip=box(0,0,w,h)
    walls={x['id']:x for x in model['walls']}
    if len(walls)!=len(model['walls']):raise ValueError('Duplicate wall IDs')
    solids=[LineString(x['axis']).buffer(x['width']/2,cap_style='flat',join_style='mitre') for x in walls.values()]
    original=union_all(solids).intersection(clip);cuts=[];frames={}
    for opening in model['openings']:
        wall=walls[opening['wall']];a,u,n,length=wall_frame(wall)
        start=opening['offset'];span=opening['length']
        if start<0 or span<=0 or start+span>length:raise ValueError('Opening outside host wall')
        p=a+u*start;q=p+u*span;t=wall['width']/2
        cut=Polygon([p+n*t,q+n*t,q-n*t,p-n*t]);cuts.append(cut)
        frames[opening['id']]=(p,q,u,n,wall['width'],cut)
    if any(a.intersection(b).area>1e-8 for i,a in enumerate(cuts) for b in cuts[i+1:]):raise ValueError('Overlapping openings')
    mass=original.difference(union_all(cuts))
    if not mass.is_valid:raise ValueError('Invalid wall area')
    # Crop boundaries are cut ends, not new closing wall edges.
    boundary=mass.boundary.difference(clip.boundary.buffer(1e-7,cap_style='flat'))
    linework=list(boundary.geoms) if hasattr(boundary,'geoms') else [boundary]
    doc=ezdxf.new('R2010');doc.units=0;doc.appids.new('REDRAW_PILOT')
    colored_components = model.get('colored_components', False)
    styles = COMPONENT_STYLES if colored_components else {
        layer: (7, None) for layer in ('A-WALL', 'A-DOOR', 'A-WINDOW')
    }
    for layer, (aci, rgb) in styles.items():
        layer_record = doc.layers.new(layer, dxfattribs={'color': aci, 'lineweight': 0})
        if rgb is not None:
            layer_record.rgb = rgb
    def xy(p):return (float(p[0]+left),float(fh-1-p[1]-top))
    def tag(ent,oid):ent.set_xdata('REDRAW_PILOT',[(1000,oid)]);return ent
    for i,geom in enumerate(linework):
        if geom.is_empty:continue
        coords=list(geom.coords);closed=coords[0]==coords[-1]
        if closed:coords=coords[:-1]
        tag(doc.modelspace().add_lwpolyline([xy(p) for p in coords],close=closed,dxfattribs={'layer':'A-WALL'}),f'wall-boundary-{i}')
    opening_checks=[]
    for opening in model['openings']:
        oid=opening['id'];p,q,u,n,thickness,cut=frames[oid]
        remaining=mass.intersection(cut.buffer(-1e-5)).area
        if remaining>1e-6:raise ValueError('Opening obstructed')
        opening_checks.append({'id':oid,'kind':opening['kind'],'remaining_wall_area_px2':float(remaining)})
        kind = opening['kind']
        layer = 'A-WINDOW' if kind == 'window' else 'A-DOOR'
        if colored_components:
            layer = {'garage': 'A-GARAGE-DOOR', 'unresolved': 'A-OPENING-REVIEW'}.get(kind, layer)
        space = doc.modelspace()
        anchor = np.zeros(2)
        has_symbol = kind in ('window', 'door', 'garage') or 'panel' in opening
        use_block = model.get('symbol_blocks') and has_symbol
        if use_block:
            anchor = np.array(xy(p))
            space = doc.blocks.new(f'{kind.upper()}-{oid}')
            tag(doc.modelspace().add_blockref(space.name, anchor.tolist(),
                dxfattribs={'layer':layer}), oid)
        symbol_layer = '0' if use_block else layer

        def symbol_xy(point):
            return tuple(np.array(xy(point)) - anchor)

        def symbol_line(a, b):
            return tag(space.add_line(symbol_xy(a), symbol_xy(b), dxfattribs={'layer':symbol_layer}), oid)

        if kind=='window':
            for d in (-thickness/3,0,thickness/3):symbol_line(p+n*d,q+n*d)
        elif kind=='door':
            hinge_end = opening.get('hinge')
            if hinge_end not in ('start', 'end') or opening.get('side') not in (-1,1):
                raise ValueError('Door requires a hinge end and swing side')
            side = opening['side']
            hinge = (q if hinge_end == 'end' else p) + n*side*thickness/2
            radius = opening['length']
            closed_end = hinge + u*radius*(1 if hinge_end == 'start' else -1)
            open_end = hinge + n*side*radius
            symbol_line(hinge, open_end)
            # Transform both endpoint directions into CAD angles, choose the
            # short CCW quarter arc; the requested swing side is preserved.
            angle=lambda end:math.degrees(math.atan2(-(end-hinge)[1],(end-hinge)[0]))%360
            a,b=angle(closed_end),angle(open_end)
            start,end=(a,b) if (b-a)%360<180 else (b,a)
            tag(space.add_arc(symbol_xy(hinge),radius,start,end,dxfattribs={'layer':symbol_layer}),oid)
        elif kind=='garage':
            for d in (-thickness/5, thickness/5):symbol_line(p+n*d,q+n*d)
        elif kind=='unresolved':
            if 'panel' in opening:
                symbol_line(*opening['panel'])
        elif kind!='passage':
            raise ValueError('Unsupported opening kind')
    dxf=out/'redrawn.dxf';doc.saveas(dxf);saved,objects=read_native(dxf,(left,top),fh)
    audit=saved.audit()
    if audit.errors or audit.fixes:raise ValueError('DXF audit requires repair')
    if any(saved.layers.get(e.dxf.layer).is_off() for e in saved.modelspace()):raise ValueError('Unexpected hidden geometry')
    # Exact readback of wall boundary segments and opening cuts. No per-pixel
    # fit requirement: this is an explicitly regularized visual reconstruction.
    actual_walls=[LineString(o['coordinates']+[o['coordinates'][0]] if o['closed'] else o['coordinates']) for o in objects if o['layer']=='A-WALL']
    delta=union_all(actual_walls).hausdorff_distance(boundary)
    if delta>1e-6:raise ValueError('Saved wall geometry changed')
    wall_segments=[]
    for obj in objects:
        if obj['layer']!='A-WALL':continue
        pts=obj['coordinates']+([obj['coordinates'][0]] if obj['closed'] else [])
        wall_segments.extend(LineString([a,b]) for a,b in zip(pts,pts[1:]) if np.linalg.norm(np.array(a)-b)>1e-6)
    rounded=[tuple(sorted((tuple(np.round(s.coords[0],6)),tuple(np.round(s.coords[1],6))))) for s in wall_segments]
    if len(set(rounded))!=len(rounded):raise ValueError('Duplicate wall segments')
    native_walls=union_all(actual_walls)
    for oid,(_,_,_,_,_,cut) in frames.items():
        if not native_walls.intersection(cut.buffer(-1e-5)).is_empty:raise ValueError(f'Saved wall crosses opening {oid}')
    cv2.imwrite(str(out/'source.png'),crop)
    cv2.imwrite(str(out/'new.png'),render(objects,[w,h],zoom=4))
    overlay=cv2.resize(crop,None,fx=4,fy=4,interpolation=cv2.INTER_NEAREST)
    ink=render(objects,[w,h],zoom=4);overlay[np.min(ink,axis=2)<150]=(50,140,20)
    cv2.imwrite(str(out/'overlay.png'),overlay)
    summary={'scope':'one visually interpreted local layout; not an automatic image-to-CAD recognizer',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'crop_xyxy':model['crop_xyxy'],
        'units':'uncalibrated original-image pixels; x right, CAD y up',
        'wall_objects':len(walls),'clear_swing_doors':sum(o['kind']=='door' for o in model['openings']),
        'clear_windows':sum(o['kind']=='window' for o in model['openings']),
        'unresolved_door_panels':sum(o['kind']=='unresolved' for o in model['openings']),
        'entity_types':dict(Counter(e.dxftype() for e in saved.modelspace())),
        'layers':dict(Counter(e.dxf.layer for e in saved.modelspace())),
        'native_audit_errors':len(audit.errors),'duplicate_wall_segments':0,
        'wall_readback_hausdorff_px':float(delta),'opening_checks':opening_checks,
        'needs_confirmation':[o for o in model['openings'] if o['certainty']=='needs_confirmation'],
        'assumptions':model['regularization'],'out_of_scope':model['omitted']}
    (out/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return objects,crop,summary
