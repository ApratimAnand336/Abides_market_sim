"""Series compression for the dashboard payload.

- Line series: LTTB (Largest-Triangle-Three-Buckets) picks indices that keep the
  visual shape. Columnar series that share a time axis are downsampled together
  using the indices LTTB chooses on the primary column.
- Step series (holdings, states) are compressed to change points only.
"""

from typing import Dict, List, Sequence

import numpy as np


def lttb_indices(x: Sequence[float], y: Sequence[float], n_out: int) -> np.ndarray:
    """Indices of the LTTB-selected points (always includes first and last).

    NaNs in y are treated as 0 for area computation only."""
    x = np.asarray(x, dtype=float)
    y = np.nan_to_num(np.asarray(y, dtype=float))
    n = len(x)
    if n_out >= n or n <= 2:
        return np.arange(n)
    if n_out < 3:
        return np.array([0, n - 1])

    idx = np.empty(n_out, dtype=int)
    idx[0], idx[-1] = 0, n - 1
    # bucket edges over the interior points 1..n-2
    edges = np.linspace(1, n - 1, n_out - 1).astype(int)
    a = 0
    for i in range(n_out - 2):
        start, end = edges[i], max(edges[i + 1], edges[i] + 1)
        # average of the next bucket (or the last point for the final bucket)
        if i + 2 < len(edges):
            nxt = slice(edges[i + 1], max(edges[i + 2], edges[i + 1] + 1))
            avg_x, avg_y = x[nxt].mean(), y[nxt].mean()
        else:
            avg_x, avg_y = x[-1], y[-1]
        bx, by = x[start:end], y[start:end]
        area = np.abs((x[a] - avg_x) * (by - y[a]) - (x[a] - bx) * (avg_y - y[a]))
        a = start + int(np.argmax(area))
        idx[i + 1] = a
    return idx


def downsample_columns(
    columns: Dict[str, Sequence[float]], primary: str, n_out: int, t_key: str = "t"
) -> Dict[str, List]:
    """Downsample every column with the indices LTTB picks on `primary`."""
    t = columns[t_key]
    if len(t) == 0:
        return {k: [] for k in columns}
    idx = lttb_indices(t, columns[primary], n_out)
    return {k: [v[i] for i in idx] for k, v in ((k, list(v)) for k, v in columns.items())}


def change_points(t: Sequence[float], *values: Sequence) -> List[int]:
    """Indices where any of `values` differs from the previous sample (first
    index always kept)."""
    keep = []
    prev = None
    for i in range(len(t)):
        cur = tuple(v[i] for v in values)
        if i == 0 or cur != prev:
            keep.append(i)
        prev = cur
    return keep
