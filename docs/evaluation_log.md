# Evaluation log

One line per evaluation run (docs/evaluation_plan.md).

| Date | Split | Setting | T1 page agreement | T2 subject accuracy vs best baseline | T3 bootstrap | Targets |
|---|---|---|---|---|---|---|
| 2026-11-09 | val | B average k=3 | 0.903 (chance 0.36, abstain 3%) | 0.409 vs 0.376 | 0.78 | T1✓ T2✗ T3✓ |
| 2026-11-09 | val | G average k=6 | 0.704 (chance 0.18, abstain 3%) | 0.590 vs 0.464 | 0.58 | T1✗ T2✓ T3✗ |

Round 1 (validation, 2026-11-09): per-language centring of embeddings and the encoder changed to Gemini
Embedding 001 (docs/accuracy_plan.md). Validation labels grew from 93 to 293 books, so the script-only
baseline moved from 0.376 to 0.464. Silhouette now picks 6 groups by itself (average linkage), with script
NMI 0.06: the groups follow subject (society/law, two literature groups, science, grammar, religion).
T2 met (+12.6 points, p = 0.0005). T1 missed: 0.704, about 3.9x chance (0.18) but under 0.80, since a single
page must now pick 1 of 6 groups instead of 1 of 3. T3 missed narrowly: 0.58 against 0.60.
| 2026-11-09 | val | G average k=6 | 0.704 (chance 0.18, abstain 3%); tagged 0.818 at 1.48 tags | 0.590 vs 0.464; tagged 0.700 at 1.61 tags, precision 0.46 | 0.58 | T1✗ T2✓ T3✗ |

Round 2 (validation, 2026-11-09): same model as round 1, plus multi-tags by the rule fixed beforehand in
docs/accuracy_plan.md. Strict scores unchanged (T1 0.704, T2 0.590, T3 0.58). Tagged, as secondary measures:
the uploaded page's tags include its book's group 0.818 of the time (1.48 tags per page); the book's subject
is among its tags' subjects 0.700 of the time (1.61 tags per book, tag precision 0.46).
