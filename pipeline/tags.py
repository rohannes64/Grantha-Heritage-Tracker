"""Multi-tags (docs/accuracy_plan.md, round 2): the nearest group, plus any group the item sits as close to
as 9 in 10 of that group's own train books do. At most MAX_TAGS, nearest first. No labels are used."""
import numpy as np

MAX_TAGS = 3
SPREAD_Q = 0.9


def group_spread(own_dist: np.ndarray, labels: np.ndarray, groups) -> np.ndarray:
    """Per group: the SPREAD_Q quantile of its member books' distances to its centre."""
    return np.array([np.quantile(own_dist[labels == g], SPREAD_Q) for g in groups])


def tags(dists: np.ndarray, spread: np.ndarray, max_tags: int = MAX_TAGS) -> list[list[int]]:
    """dists: items x groups distances to the group centres. Returns each item's tags, nearest first;
    the first tag is always the nearest group (the main group)."""
    out = []
    for d in np.atleast_2d(dists):
        order = np.argsort(d)
        extra = [int(g) for g in order[1:] if d[g] <= spread[g]]
        out.append([int(order[0])] + extra[:max_tags - 1])
    return out
