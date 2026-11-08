# Preprocessing log

Every choice made between OCR output and the clustering features, with counts.

## 1. Documents

- Harvested books with OCR: 3000
- Usable for clustering: 2578 (rule: word-weighted mean OCR confidence >= 50 and >= 100 clean tokens)
- Excluded as unreadable OCR: 422. They stay in the table and are used in the OCR-noise analysis; they are not silently dropped.

| Language tag | Harvested | Usable | Usable % | Median conf | Tag matches detected script |
|---|---|---|---|---|---|
| Bengali | 375 | 359 | 96% | 73.1 | 97% |
| English | 375 | 370 | 99% | 91.9 | 99% |
| Gujarati | 375 | 352 | 94% | 71.7 | 91% |
| Hindi | 375 | 333 | 89% | 75.8 | 95% |
| Kannada | 375 | 326 | 87% | 75.5 | 94% |
| Sanskrit | 375 | 281 | 75% | 60.7 | 65% |
| Tamil | 375 | 296 | 79% | 62.7 | 98% |
| Telugu | 375 | 261 | 70% | 55.2 | 99% |

## 2. Text cleaning

1. Unicode NFC normalisation (one code-point sequence per character).
2. Tokens are runs of letters and combining marks (`\p{L}\p{M}`); the default `\w+` pattern would split Indian-script words at vowel signs.
3. Tokens shorter than 2 characters, starting with a stray vowel sign, or mixing scripts are dropped as OCR noise; tokens in the book's own script or in Latin are kept.
4. Latin tokens lower-cased; English function words removed. Function words of every language are removed in the feature step by a per-language document-frequency cap (a term in more than 30% of the books of its own language), not by hand-written lists.
5. Digits, numerals and punctuation removed (not letters).

## 3. Variable relevance review

| Field | Missing % | Distinct | Decision | Reason |
|---|---|---|---|---|
| year | 18.6 | 162 | keep (numeric) | publication era shapes vocabulary and spelling; median-imputed with a missing flag |
| total_pages | 0.0 | 737 | keep as log10 (numeric) | book length; heavy right tail, so log-transformed |
| mean_conf | 0.3 | 2988 | keep (numeric) | OCR quality; needed to study whether noise drives clusters |
| n_tokens | 0.0 | 1241 | keep as log10 (numeric) | amount of usable text |
| script | 0.0 | 7 | keep (one-hot) | detected script; the only categorical field encoded |
| lang_tag | 0.0 | 8 | drop | catalogue tag; replaced by detected script because some tags are wrong |
| era | 0.0 | 5 | drop from features | derived from year (redundant); kept for profiles and sampling |
| title | 0.0 | 2971 | drop from features | not available for a new scan; used only to display results |
| creator | 8.3 | 2400 | drop from features | free text, mostly unique; display only |
| publisher | 28.7 | 1821 | drop from features | free text, high cardinality; display only |
| source_library | 32.9 | 248 | drop | provenance, not content |
| scanning_centre | 24.6 | 26 | drop | provenance; would let clusters form by scanning site (leakage) |
| subject_field | 0.0 | 288 | drop | mostly the scanning centre, not a topic (checked on real records) |
| classification | 49.0 | 496 | drop from features | sparse real subject labels; used only as a weak outside check |

## 4. Missing values

- `year`: 495 of 2578 usable books undated (19%). Imputed with the median (1923) and a `year_missing` flag, so undated books are not mistaken for typical-year books.
- `script`: never missing (always detected); unknown categories at prediction time are ignored by the encoder rather than raising an error.
- Text: books whose OCR is unusable are flagged, not imputed (there is no sensible text to impute).

## 5. Encoding and scaling

- Numeric fields ['year', 'log_pages', 'mean_conf', 'log_tokens'] are standardised (zero mean, unit variance) so year (hundreds) does not outweigh confidence (tens) in distance calculations.
- Categorical ['script'] is one-hot encoded: categories ['Bengali', 'Devanagari', 'Gujarati', 'Kannada', 'Latin', 'Tamil', 'Telugu'].
- The metadata block is used only in a sensitivity variant (text + metadata). The main study clusters text alone, so groups reflect content, not script or era.
