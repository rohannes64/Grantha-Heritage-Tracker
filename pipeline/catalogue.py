"""Librarians' classification field -> one of nine top-level classes.

About half of the harvested books carry a catalogue `classification` such as
"Language. Linguistics. Literature | Literature | Poetry. Poems. Verse" or "Religion. Theology | ... | Hinduism".
Its first segment follows the main classes of the Universal Decimal Classification (generalities, philosophy,
religion, social sciences, natural sciences, applied sciences, arts, language and literature, geography/
biography/history). This module maps a code to that main class with fixed keyword rules on the first
segment, so it can serve as a second, human-made ground truth next to the assistant-made subject labels.

Rules, not judgement: a code whose first segment matches no rule, or that is a known placeholder or junk
value, maps to None and is left out (and counted), never guessed. Added 2026-11-14 as an exploratory
measure, after the evaluation plan; it does not replace target T2.
"""
import re

CLASSES = ["generalities", "philosophy and psychology", "religion", "social sciences", "natural sciences",
           "applied sciences and medicine", "arts", "language and literature", "geography, biography, history"]

# (pattern on the lower-cased first segment, class); first match wins, so order matters
RULES = [
    (r"^generalit", "generalities"),
    (r"^(philosoph|psycholog)", "philosophy and psychology"),
    (r"^(religion|theology|devotional|jain|hindu|buddh|islam|christian|bible|vedic|veda)", "religion"),
    (r"^(social|education|econom|politic|law|sociolog|commerce)", "social sciences"),
    (r"^(natural|mathemat|astronom|physic|chemist|botan|zoolog|science)", "natural sciences"),
    (r"^(technology|applied|medic|ayurved|agricultur|engineer|manufactur|home)", "applied sciences and medicine"),
    (r"^(arts?\b|fine arts|music|recreation|sport|games)", "arts"),
    (r"^(language|linguistic|literature|litrature|literary|poetry|drama|fiction|novel|prose|english|hindi|bengali|sanskrit|tamil|telugu|kannada|gujarati)",
     "language and literature"),
    (r"^(geograph|history|biograph)", "geography, biography, history"),
]
JUNK = re.compile(r"^\s*(-+|vacant|unknown|n\.?a\.?|none|null)\s*$|la grange illinois", re.IGNORECASE)


def main_class(code) -> str | None:
    if not isinstance(code, str) or not code.strip() or JUNK.search(code):
        return None
    first = code.split("|")[0].strip().lower()
    for pattern, cls in RULES:
        if re.search(pattern, first):
            return cls
    return None
