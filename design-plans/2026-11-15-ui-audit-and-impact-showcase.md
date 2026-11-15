# UI Audit & Real-World Impact Showcase Plan

Written against: `57a2c27`

## Design language
- Audited surface: `web/` Darkroom application (`web/tokens.css`, `web/components.css`, `web/app.css`, `web/galaxy.css`, `web/galaxy.html`)
- Design sources: `web/tokens.css`, `web/components.css`, `web/app.css`
- Documented decisions: Darkroom amber theme (`--color-paper`, `--color-paper-2`, `--color-paper-3`, `--color-ink`, `--color-accent`), `44px` minimum interactive control height in `.seg label` (`web/components.css` L51) and `.slab nav a` (`web/components.css` L20), `48px` `.btn` / `.input` height, 7-link sticky `.slab` navigation (`web/components.css` L23–34).
- Governing owners and consumers: `web/tokens.css` (palette, type, spacing), `web/components.css` (`.slab`, `.btn`, `.seg`, `.sheet`, `.table-wrap`), `web/app.css` (`.page-head`, `.study-section`, `.figures-row`), `web/galaxy.css` / `web/galaxy.html` (Archive map).
- Explicit exceptions: None documented.

## Findings
| # | Problem | Evidence | Proposed change | Scope | Confidence |
| --- | --- | --- | --- | --- | --- |
| 1 | Sub-44px interactive targets in Archive map | Contract: `web/components.css` L51 (`.seg label { min-height: 44px }`). Runtime: `web/galaxy.css` L61–64 sets `.seg-sm label { min-height: 36px }` and `.gx-sample { min-height: 34px }`. | Set `.seg-sm label` and `.gx-sample` `min-height` to `44px` in `web/galaxy.css`. | `web/galaxy.css` | High |
| 2 | Stale Archive map subtitle copy | Contract: `web/galaxy.html` L34 states `"Colour is the book’s language."` while L71–75 (`#colour-by`) now switches between `Language` and `Group`. | Update `web/galaxy.html` L34 to `"Every dot is one book, placed by how the model reads its text. Colour by language or topic group."` | `web/galaxy.html` | High |
| 3 | Missing real-world problems showcase in navigation | Contract: `.slab nav ul` (`web/components.css` L19–34) links the primary product surfaces; no page demonstrates end-to-end real-world archivist/researcher problems solved with rendered motion explainers. | Add `web/impact.html` + `web/impact.css` and add the `"Impact"` link to `.slab nav ul` across `web/*.html`, tightening `@media (max-width: 80rem)` gap in `web/components.css` if needed. | `web/impact.html`, `web/impact.css`, `web/components.css`, `web/*.html` | High |

## Improve first
Finding 1 (`web/galaxy.css` control height alignment) — brings all interactive controls on `galaxy.html` back into conformance with the `44px` `.seg label` contract in `web/components.css` with zero layout regressions.

## Evidence chain
- Surface: `web/galaxy.html`, `web/galaxy.css`, `web/components.css`, and new `web/impact.html`
- Problem: Sub-44px controls in `galaxy.css`, stale copy in `galaxy.html`, and no dedicated real-world impact showcase page with rendered motion explainers.
- Design evidence: `web/components.css` L15–56, `web/tokens.css` L1–20, `web/app.css` L10–13.
- Owner: `web/components.css` & `web/galaxy.css`

## Design decision
Align `web/galaxy.css` controls to `44px`, update `web/galaxy.html` subtitle copy, and introduce `web/impact.html` (`web/impact.css`) following the exact Darkroom `.slab` / `.page-head` / `.study-section` / `.figures-row` / `.sheet` primitives, embedding MP4 animations rendered via `raea` on the high-spec GCP VM (`grantha-render-cpu`).

## Changes
1. `web/galaxy.css` — update `.seg-sm label` and `.gx-sample` `min-height` to `44px`.
2. `web/galaxy.html` — update `.page-head p` copy to reflect `Language | Group` colouring.
3. `web/impact.html` & `web/impact.css` — showcase 4 concrete real-world problems solved by Grantha (Cross-Script Discovery, Unindexed Page Triage, Rapid Catalogue Coding, Duplicate/Edition Detection) with `raea`-rendered MP4 animations and verified `facts.json` figures.
4. `web/*.html` — add `<a href="impact.html">Impact</a>` to `.slab nav ul`.

## Validation
- Repository: `python scripts/check_claims.py`, `sloplint.mjs web/galaxy.html web/impact.html`, `python -m pytest -q -p no:cacheprovider`.
- Interface: Headless Edge at `1440×900` and `375×812` with `0` horizontal overflow and `0` HTTP `>= 400` asset errors.
