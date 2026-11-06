"""Render read-back drawing paths as SVG and PNG."""
import cv2
import numpy as np


def paths_svg(objects,color='#222'):
    items=[]
    for obj in objects:
        pts=obj['coordinates']
        if len(pts)==1:
            items.append(f'<circle cx="{pts[0][0]}" cy="{pts[0][1]}" r=".35" fill="{color}"/>');continue
        d='M'+' L'.join(f'{x:.8f},{y:.8f}' for x,y in pts)+(' Z' if obj['closed'] else '')
        items.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width=".65" stroke-linejoin="round"/>')
    return ''.join(items)

def render(objects,size,zoom=3,stroke=1):
    canvas=np.full((size[1]*zoom,size[0]*zoom,3),255,np.uint8)
    for obj in objects:
        pts=np.rint(np.array(obj['coordinates'])*zoom).astype('int32')
        if len(pts)==1:cv2.circle(canvas,tuple(pts[0]),1,(20,20,20),-1)
        else:cv2.polylines(canvas,[pts],obj['closed'],(20,20,20),stroke,cv2.LINE_AA)
    return canvas
