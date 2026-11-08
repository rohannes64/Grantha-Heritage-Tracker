# Pilot OCR quality

Pilot: the first 50 harvested books of each language in draw order (400 books with OCR).

Usability rule (fixed before the run): median word confidence >= 60 and median script ratio >= 0.80.
Agreement with the Internet Archive's OCR is a consistency check, not ground truth.

| Language | Docs | Pages | Tag matches script | Median conf | Pages conf>=70 | Median script ratio | Words/page | Empty pages | IA pages compared | Median IA agreement | Usable |
|---|---|---|---|---|---|---|---|---|---|---|---|
| English | 50 | 250 | 100.0% | 92.41 | 92.8% | 1.0 | 315.5 | 1.6% | 23 | 99.16 | yes |
| Hindi | 50 | 250 | 100.0% | 76.05 | 68.0% | 1.0 | 240.5 | 6.0% | 230 | 96.83 | yes |
| Sanskrit | 50 | 250 | 72.0% | 62.29 | 28.0% | 1.0 | 184.0 | 2.4% | 244 | 86.68 | yes |
| Bengali | 50 | 250 | 98.0% | 72.96 | 62.4% | 1.0 | 197.0 | 1.2% | 243 | 94.47 | yes |
| Gujarati | 50 | 250 | 86.0% | 69.51 | 48.0% | 1.0 | 216.0 | 2.0% | 235 | 92.61 | yes |
| Telugu | 50 | 250 | 100.0% | 54.89 | 8.0% | 1.0 | 140.0 | 4.4% | 235 | 85.99 | NO |
| Kannada | 50 | 250 | 96.0% | 75.81 | 65.6% | 1.0 | 163.0 | 0.4% | 249 | 94.69 | yes |
| Tamil | 50 | 250 | 98.0% | 63.85 | 24.8% | 1.0 | 144.0 | 2.4% | 241 | 92.16 | yes |

Models used per language (documents re-routed when OSD found a different script):

- English: {'eng': 50}
- Hindi: {'hin': 50}
- Sanskrit: {'ben': 4, 'eng': 9, 'san': 36, 'tam': 1}
- Bengali: {'ben': 49, 'eng': 1}
- Gujarati: {'eng': 4, 'guj': 43, 'hin': 3}
- Telugu: {'tel': 50}
- Kannada: {'eng': 1, 'kan': 48, 'tel': 1}
- Tamil: {'eng': 1, 'tam': 49}
