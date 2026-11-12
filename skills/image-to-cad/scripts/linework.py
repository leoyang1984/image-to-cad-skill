"""Extract editable, unclassified paths from already-clean raster linework."""
import cv2
import numpy as np

from regularize import canonical_edge, clean_linework, tolerances


def thin(mask):
    """Zhang–Suen thinning preserves junctions while removing double stroke edges."""
    pixels = np.pad(mask, 1).astype(bool)
    center = pixels[1:-1, 1:-1]
    neighbors = [
        pixels[:-2, 1:-1], pixels[:-2, 2:], pixels[1:-1, 2:], pixels[2:, 2:],
        pixels[2:, 1:-1], pixels[2:, :-2], pixels[1:-1, :-2], pixels[:-2, :-2],
    ]
    north, _, east, _, south, _, west, _ = neighbors
    # Already-clean linework converges quickly. Dense ink belongs in direct/simplified input.
    for _ in range(128):
        changed = False
        for first, second, third, fourth in ((east, south, north, west), (north, west, east, south)):
            count = np.sum(neighbors, axis=0, dtype=np.uint8)
            transitions = np.zeros(center.shape, dtype=np.uint8)
            for a, b in zip(neighbors, neighbors[1:] + neighbors[:1]):
                transitions += ~a & b
            keep_corner = first & second & (third | fourth)
            remove = center & (count >= 2) & (count <= 6) & (transitions == 1) & ~keep_corner
            if remove.any():
                center[remove] = False
                changed = True
        if not changed:
            return center
    raise ValueError('Ink is too dense for clean line extraction; use direct or simplified input')


def neighbors_of(p, nodes):
    x, y = p
    for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1)):
        q = (x + dx, y + dy)
        if q in nodes and not (dx and dy and ((x + dx, y) in nodes or (x, y + dy) in nodes)):
            yield q


def follow_paths(skeleton):
    ys, xs = np.nonzero(skeleton)
    if len(xs) > 250_000:
        raise ValueError('Too many line pixels for clean line extraction; use direct or simplified input')
    nodes = {(int(x), int(y)) for x, y in zip(xs, ys)}
    adjacency = {p: tuple(neighbors_of(p, nodes)) for p in sorted(nodes)}
    endpoints = [p for p, links in adjacency.items() if len(links) != 2]
    visited = set()
    for start in (*endpoints, *adjacency):
        for step in adjacency[start]:
            edge = canonical_edge(start, step)
            if edge in visited:
                continue
            visited.add(edge)
            path = [start, step]
            while len(adjacency[path[-1]]) == 2 and path[-1] != start:
                a, b = path[-2:]
                candidate = next(q for q in adjacency[b] if q != a)
                edge = canonical_edge(b, candidate)
                if edge in visited:
                    break
                visited.add(edge)
                path.append(candidate)
            yield path


def approximate(path, epsilon):
    closed = path[0] == path[-1]
    contour = np.array(path[:-1] if closed else path, dtype=np.int32)
    simplified = cv2.approxPolyDP(contour, epsilon, closed).reshape(-1, 2).tolist()
    if closed:
        if len(simplified) < 3:
            simplified = contour.tolist()
        simplified.append(simplified[0])
    return simplified


def extract_linework(image, frame):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    threshold, ink = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    x, y, width, height = cv2.boundingRect(ink)
    if not width or not height:
        raise ValueError('No foreground ink detected')
    # The original raster frame stays intact. Work only on the ink region.
    region = ink[y:y + height, x:x + width]
    if region.size > 8_000_000:
        raise ValueError('Clean linework region exceeds 8 million pixels; prepare a smaller input explicitly')
    if np.count_nonzero(region) > 2_000_000:
        raise ValueError('Too much foreground ink for clean line extraction; use direct or simplified input')
    skeleton = thin(region)
    scale = min(frame[2:])
    epsilon = max(.5, min(2.0, scale * .0007))
    min_length = max(2.0, scale * .0015)
    paths, rejected = [], 0
    for path in follow_paths(skeleton):
        if cv2.arcLength(np.array(path, dtype=np.int32), False) < min_length:
            rejected += 1
            continue
        paths.append([tuple((px + x, py + y)) for px, py in approximate(path, epsilon)])
    settings = tolerances(frame, {})
    before = len(paths)
    paths = clean_linework(paths, settings['gap'])
    if not paths:
        raise ValueError('No editable line paths remained after cleanup')
    return {
        'schema_version': 1, 'frame': frame, 'interpretation': 'automatic_linework',
        'components': [{'id': 'raster-linework', 'kind': 'linework', 'paths': paths}],
        'relationships': [],
        'regularization': ['Otsu binarization, stroke thinning, path simplification and duplicate cleanup.'],
        'unresolved_questions': ['Classify important components and verify openings, junctions and stair treads in the source.'],
    }, {
        'otsu_threshold': threshold, 'foreground_bounds': [x, y, x + width, y + height],
        'skeleton_pixels': int(skeleton.sum()), 'simplification_tolerance_px': epsilon,
        'discarded_short_paths': rejected, 'minimum_path_length_px': min_length,
        'paths_before_cleanup': before, 'paths': len(paths), 'gap_joining': False,
    }
