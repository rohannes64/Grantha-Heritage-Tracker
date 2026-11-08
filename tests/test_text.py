from pipeline import text


def test_indic_words_stay_whole():
    # Hindi word with vowel signs and a virama: \w+ would split it, our tokenizer must not.
    assert text.clean_tokens("संस्कृति और इतिहास", "Devanagari") == ["संस्कृति", "और", "इतिहास"]
    assert text.clean_tokens("பூராயக் காட்சியே", "Tamil") == ["பூராயக்", "காட்சியே"]


def test_noise_is_dropped():
    toks = text.clean_tokens("ப்க்ழுத153722 aबc ि x ஐதே", "Tamil")
    assert "aबc" not in toks          # mixed scripts
    assert "x" not in toks            # too short
    assert all(not t[0] in "ि" for t in toks)   # no token starting with a vowel sign
    assert "ஐதே" in toks


def test_latin_kept_in_indic_book_and_lowercased():
    assert text.clean_tokens("Sanskrit ग्रन्थ", "Devanagari") == ["sanskrit", "ग्रन्थ"]


def test_other_indic_script_dropped():
    # Bengali word inside a Tamil book is treated as OCR confusion
    assert text.clean_tokens("বাংলা தமிழ்", "Tamil") == ["தமிழ்"]


def test_digits_removed():
    assert text.clean_tokens("Chapter 12 ௧௨ १२", "Latin") == ["chapter"]


def test_stopwords():
    assert text.remove_stopwords(["the", "history", "of", "law"]) == ["history", "law"]
