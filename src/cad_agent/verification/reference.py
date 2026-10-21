"""Checks kept separate from future generated modeling scripts."""

import math


def check_reference_pocket_vertices(points: list[tuple[float, float, float]]) -> bool:
    """Check the exact corner set of our axis-aligned reference task in metres.

    This intentionally validates one known task, not arbitrary CAD designs.
    """
    expected = {(x, y, z) for x in (-0.05, 0.05) for y in (-0.03, 0.03) for z in (0.0, 0.01)}
    expected |= {(x, y, z) for x in (-0.02, 0.02) for y in (-0.01, 0.01) for z in (0.005, 0.01)}
    if len(points) != len(expected):
        return False
    remaining = list(expected)
    for point in points:
        match = next(
            (
                p
                for p in remaining
                if len(point) == 3 and all(math.isfinite(a) and abs(a - b) < 1e-8 for a, b in zip(point, p))
            ),
            None,
        )
        if match is None:
            return False
        remaining.remove(match)
    return not remaining
