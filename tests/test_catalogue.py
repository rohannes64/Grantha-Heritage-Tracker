"""Catalogue classification codes -> main classes, by fixed rules (see pipeline/catalogue.py)."""
import pytest

from pipeline.catalogue import CLASSES, main_class


@pytest.mark.parametrize("code,expected", [
    ("Language. Linguistics. Literature | Literature | Poetry. Poems. Verse", "language and literature"),
    ("LANGUAGE. LINGUISTICS. LITERATURE | Literature | Drama. Plays", "language and literature"),
    ("Litrature", "language and literature"),
    ("Religion. Theology | Religions Of The Indian Subcontinent | Hinduism Narrowly", "religion"),
    ("Devotional", "religion"),
    ("Geography. Biography. History | Biographical And Related Studies | Biography", "geography, biography, history"),
    ("Medical", "applied sciences and medicine"),
    ("Natural Sciences", "natural sciences"),
    ("Philosophy. Psychology", "philosophy and psychology"),
    ("Generalities | General Reference Works Encyclopaedias", "generalities"),
    ("Social Sciences", "social sciences"),
])
def test_known_codes_map_to_their_main_class(code, expected):
    assert main_class(code) == expected and expected in CLASSES


@pytest.mark.parametrize("code", ["-", "Vacant", "", None, "Manufactures | Pulp Products | The Author La Grange Illinois",
                                  "वैदिक साहित्य", "Some Unrelated Words"])
def test_placeholders_junk_and_unmatched_codes_are_left_out(code):
    assert main_class(code) is None
