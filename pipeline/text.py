"""Text cleaning for noisy multi-script OCR. Shared by the study and the web app, so a new
document is cleaned exactly like the archive documents were.

Why a custom tokenizer: the usual `\\w+` pattern splits Indian-script words at every vowel sign
(combining marks are not `\\w` in Python), so it would shred Hindi or Tamil words into pieces.
Here a token is a run of letters *and* combining marks (`\\p{L}\\p{M}`).
"""
import unicodedata

import regex

from . import config

TOKEN = regex.compile(r"[\p{L}\p{M}]+")
MIN_TOKEN_CHARS = 2


def script_of_char(c: str) -> str | None:
    o = ord(c)
    for script, ranges in config.SCRIPT_RANGES.items():
        if any(lo <= o <= hi for lo, hi in ranges):
            return script
    return None


def token_script(tok: str) -> str | None:
    """The single script of a token's letters, or None if letters come from mixed/unknown scripts."""
    scripts = {script_of_char(c) for c in tok if unicodedata.category(c)[0] == "L"}
    if len(scripts) != 1:
        return None
    return scripts.pop()


def clean_tokens(text: str, script: str) -> list[str]:
    """Tokens from OCR text, kept only if they are in the document's script or in Latin
    (Indian-language books often cite English terms). Mixed-script tokens are OCR noise."""
    text = unicodedata.normalize("NFC", text or "")
    out = []
    for tok in TOKEN.findall(text):
        if len(tok) < MIN_TOKEN_CHARS or unicodedata.category(tok[0])[0] != "L":
            continue  # too short, or starts with a stray vowel sign (broken OCR)
        s = token_script(tok)
        if s is None or (s != script and s != "Latin"):
            continue
        out.append(tok.lower() if s == "Latin" else tok)
    return out


# Common English function words. Indian-language stopwords are not hand-listed: the TF-IDF step
# drops any term found in more than half of the documents (max_df), which removes them per corpus.
ENGLISH_STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most
my myself no nor not now of off on once only or other our ours ourselves out over own same she should
so some such than that the their theirs them themselves then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you your
yours yourself yourselves also upon thus shall may might must one two vol page pp ibid ed
""".split())


def remove_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in ENGLISH_STOPWORDS]
