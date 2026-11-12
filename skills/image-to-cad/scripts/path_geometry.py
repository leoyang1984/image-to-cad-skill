"""Compile the shared absolute M/L/C/Z path format into native DXF geometry."""
from math import isfinite


def parse_path(path, height, *, width=None):
    if not isinstance(path, str):
        raise ValueError('A path requires an M/L/C/Z command string')
    tokens = iter(path.split())

    def point():
        try:
            x, y = float(next(tokens)), float(next(tokens))
        except (StopIteration, ValueError) as error:
            raise ValueError('Incomplete or invalid path coordinate') from error
        if not isfinite(x) or not isfinite(y):
            raise ValueError('Path coordinates must be finite')
        if width is not None and not (-.5 <= x <= width - .5 and -.5 <= y <= height - .5):
            raise ValueError('Path coordinates fall outside the reference frame')
        return x, height - 1 - y

    if next(tokens, None) != 'M':
        raise ValueError('An outline must begin with M')
    start = current = point()
    segments = []
    closed = False
    for command in tokens:
        if command == 'L':
            end = point()
            segments.append((current, end))
        elif command == 'C':
            handle1, handle2, end = point(), point(), point()
            segments.append((current, handle1, handle2, end))
        elif command == 'Z':
            closed = True
            if current != start:
                segments.append((current, start))
            if next(tokens, None) is not None:
                raise ValueError('Z must end the outline')
            break
        else:
            raise ValueError(f'Unsupported outline command {command}')
        current = end
    if not segments:
        raise ValueError('An outline requires at least one segment')
    return segments, closed


def add_native_path(modelspace, segments, closed, attrs, *, single_line=False):
    start = segments[0][0]
    if all(len(segment) == 2 for segment in segments):
        if single_line and len(segments) == 1 and not closed:
            return modelspace.add_line(*segments[0], dxfattribs=attrs)
        vertices = [start, *(segment[-1] for segment in segments)]
        if closed:
            vertices.pop()
        return modelspace.add_lwpolyline(vertices, close=closed, dxfattribs=attrs)

    # Triple internal knots preserve deliberate corners in a chain of cubics.
    controls = [start]
    for segment in segments:
        if len(segment) == 2:
            a, b = segment
            controls.extend((tuple((2*x+y)/3 for x, y in zip(a, b)),
                             tuple((x+2*y)/3 for x, y in zip(a, b)), b))
        else:
            controls.extend(segment[1:])
    count = len(segments)
    knots = [0]*4 + [k for k in range(1, count) for _ in range(3)] + [count]*4
    entity = modelspace.add_open_spline(controls, degree=3, knots=knots, dxfattribs=attrs)
    entity.closed = closed
    return entity
