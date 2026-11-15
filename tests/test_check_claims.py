"""The claims checker must flag numbers that no result file or code constant supports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_claims  # noqa: E402

FACTS = {"corpus": {"harvested": 15288, "usable": 13342, "by_language": [{"name": "Telugu", "usable": 1321, "harvested": 1914}],
                    "text_source": {"hocr": 9000, "tesseract_pages": 4342}},
         "hierarchical": {"silhouette": 0.0403, "k": 3},
         "evaluation": {"test": {"t2_accuracy": 0.475, "t2_p": 0.0004997, "t2_labelled_train": 360, "t2_labelled_heldout": 118},
                        "val": {"t2_labelled_heldout": 110}}}


def flagged(text):
    return [tok for _, tok, _ in check_claims.unsourced(text.split("\n"), check_claims.allowed(FACTS))]


def test_sourced_numbers_pass_in_their_printed_forms():
    assert flagged("13,342 of 15,288 books (87.3%); silhouette 0.040; accuracy 47.5%; p = 0.0005; 588 labelled") == []


def test_code_constants_pass():
    assert flagged("confidence at least 50, at least 100 tokens, 20 resamples of 80%, k from 2 to 15, 2,000 shuffles") == []


def test_fabricated_numbers_are_flagged():
    text = "16,586 books, 57.89% accuracy vs 40.35%, cophenetic r = 0.9984, eps = 0.60 with 18.2% noise, 84.2% agreement"
    assert set(flagged(text)) >= {"16,586", "57.89%", "40.35%", "0.9984", "18.2%", "84.2%"}


def test_structural_numbers_are_skipped():
    assert flagged("See Slide 7 and Figure 4.1, Q 2.3, Unit III, CO2, logged on 2026-11-14, printed in 1923.") == []


def test_website_text_is_checked_but_markup_and_code_are_not(tmp_path):
    html = tmp_path / "page.html"
    html.write_text('<html><head><style>.a{width:57.89%}</style><script>const k = 0.9984;</script></head>'
                    '<body><div class="x" data-n="16586">We read 16,586 books.</div><p>13,342 usable.</p></body></html>',
                    encoding="utf-8")
    js = tmp_path / "view.js"
    js.write_text('const pad = 18.2; el.textContent = `Accuracy ${data.acc} vs 40.35% baseline`; '
                  "const label = 'Noise: 84.2%'; const s = \"13,342 books\";", encoding="utf-8")
    ok = check_claims.allowed(FACTS)
    html_bad = [t for _, t, _ in check_claims.unsourced(check_claims.read_text(html), ok)]
    js_bad = [t for _, t, _ in check_claims.unsourced(check_claims.read_text(js), ok)]
    assert html_bad == ["16,586"]                       # visible text only: CSS, script and attributes skipped
    assert sorted(js_bad) == ["40.35%", "84.2%"]        # string literals only: code numbers and ${...} skipped
