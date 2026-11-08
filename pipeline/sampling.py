"""Pure functions for building the stratified sample. No network here, so it is easy to test."""
import html
import random
import re

from . import config

_YEAR = re.compile(r"(1[5-9]\d\d|20\d\d)")


def parse_year(date_raw) -> int | None:
    """First plausible 4-digit year in the IA date field, else None."""
    if not date_raw:
        return None
    if isinstance(date_raw, list):
        date_raw = date_raw[0] if date_raw else ""
    m = _YEAR.search(str(date_raw))
    return int(m.group(1)) if m else None


def era_of(year: int | None) -> str | None:
    """Era band for a year; None means out of scope (after MAX_YEAR)."""
    if year is None:
        return "undated"
    if year > config.MAX_YEAR:
        return None
    for name, lo, hi in config.ERA_BANDS:
        if hi is None:
            continue
        if (lo is None or year >= lo) and year <= hi:
            return name
    return None


def stratified_order(items: list[dict], seed: int = config.SEED) -> list[dict]:
    """Shuffle each era band with a fixed seed, then interleave the bands round-robin.

    Taking the first n of this order gives an equal share per band (as far as each band
    allows), and the pilot (first 50) is always a subset of the full sample (first 375).
    """
    bands: dict[str, list[dict]] = {}
    for it in items:
        bands.setdefault(it["era"], []).append(it)
    order = [name for name, *_ in config.ERA_BANDS if name in bands]
    rng = random.Random(seed)
    for name in order:
        bands[name].sort(key=lambda x: x["identifier"])  # deterministic before shuffling
        rng.shuffle(bands[name])
    out, i = [], 0
    while any(i < len(bands[n]) for n in order):
        for n in order:
            if i < len(bands[n]):
                out.append(bands[n][i])
        i += 1
    return out


def choose_leaves(total_pages: int, positions=config.PAGE_POSITIONS) -> list[tuple[int, float]]:
    """Leaf indices (0-based) at fixed fractions through the book, de-duplicated."""
    seen, out = set(), []
    for p in positions:
        leaf = min(total_pages - 1, max(0, round(p * (total_pages - 1))))
        if leaf not in seen:
            seen.add(leaf)
            out.append((leaf, p))
    return out


_DC = re.compile(r"dc\.([a-z.]+):\s*(.*?)\s*(?:<br\s*/?>|</p>|$)", re.I)


def parse_dc(description) -> dict[str, list[str]]:
    """Dublin Core fields embedded in DLI item descriptions ('dc.x.y: value<br />')."""
    if isinstance(description, list):
        description = " ".join(description)
    out: dict[str, list[str]] = {}
    for key, val in _DC.findall(description or ""):
        val = html.unescape(re.sub(r"<[^>]+>", "", val)).strip()
        if val:
            out.setdefault(key.lower(), []).append(val)
    return out


def first_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, list):
        return "; ".join(str(x) for x in v) if v else None
    return str(v)


def total_pages_of(dc: dict, meta: dict) -> int | None:
    """Page count: DLI's dc.description.totalpages, else IA's imagecount."""
    for raw in (dc.get("description.totalpages") or [None])[:1] + [first_str(meta.get("imagecount"))]:
        digits = re.sub(r"\D", "", raw or "")
        if digits and int(digits) > 0:
            return int(digits)
    return None
