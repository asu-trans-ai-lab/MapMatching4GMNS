"""Intelligent trace segmentation for loops / irregular GPS -- the "unusual case" other
matchers fail on.

Most-likely-path matching (trace2route) needs a distinct origin and destination: it finds the
best o->d path guided by the trace. A **loop** route (start == end, a circulator) collapses:
o == d makes the shortest o->d path trivially empty, so the loop never matches. Naive HMM
matchers also break on loops (they assume monotone progress along the trace).

Our fix: keep the trace (it is a good friend of the destination) and **cut it into pieces**
where each piece has a clean o->d, then match each piece and stitch. Loops are cut at the point
of maximum excursion; long/irregular traces are chunked by cumulative distance. No piece is a
loop, so every piece matches; stitched back together they reproduce the full route incl. loops.
"""
import math


def _hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp = math.radians(b[1] - a[1]); dl = math.radians(b[0] - a[0])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(x)))


def _cum(points):
    d = [0.0]
    for i in range(1, len(points)):
        d.append(d[-1] + _hav(points[i - 1], points[i]))
    return d


def is_loop(points, tol_m=300.0):
    """True if the trace returns near its start (a circulator / closed loop)."""
    return len(points) >= 3 and _hav(points[0], points[-1]) <= tol_m


def _farthest_index(points):
    """Index of the point farthest (great-circle) from the start -- the loop's apex."""
    s = points[0]
    best_i, best_d = 0, -1.0
    for i, p in enumerate(points):
        d = _hav(s, p)
        if d > best_d:
            best_d, best_i = d, i
    return best_i


def segment(points, *, max_piece_km=None, loop_tol_m=300.0, min_piece_pts=2):
    """Cut a trace into pieces, each with a distinct o->d (no piece is a loop).

    - Loop (start~end): split at the apex -> two open pieces (out and back).
    - Then optionally chunk each piece by cumulative distance (max_piece_km) so long routes
      stay short & self-correcting (the B/tmc2trace CHUNK principle).
    Returns a list of point-lists. A single non-loop short trace returns [points] unchanged.
    """
    if len(points) < min_piece_pts:
        return [points]

    # 1) break loops at the apex
    if is_loop(points, loop_tol_m):
        apex = _farthest_index(points)
        if apex >= 1 and apex <= len(points) - 2:
            base = [points[:apex + 1], points[apex:]]
        else:  # apex at an end -> split at the midpoint of cumulative distance
            c = _cum(points); half = c[-1] / 2
            mid = min(range(len(c)), key=lambda i: abs(c[i] - half))
            mid = max(1, min(mid, len(points) - 2))
            base = [points[:mid + 1], points[mid:]]
    else:
        base = [points]

    # 2) optionally chunk long pieces by distance
    if not max_piece_km:
        return [p for p in base if len(p) >= min_piece_pts]
    out = []
    for piece in base:
        c = _cum(piece); total = c[-1]
        if total <= max_piece_km * 1000 or len(piece) <= min_piece_pts:
            out.append(piece); continue
        step = max_piece_km * 1000
        start = 0; target = step
        for i in range(1, len(piece)):
            if c[i] >= target:
                out.append(piece[start:i + 1]); start = i; target = c[i] + step
        if start < len(piece) - 1:
            out.append(piece[start:])
    return [p for p in out if len(p) >= min_piece_pts]
