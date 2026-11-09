# Documents

- `Grantha_Report.docx`: the project report (DFDs, methods, every result, limits).
- `Grantha_Deck.pptx`: the presentation deck, with speaker notes.
- `viva_notes.md`: viva questions and answers, by area.
- `paper_draft.md`: short-paper draft: clustering finds language before topic, and how removing it helps.
- `evaluation_plan.md`, `accuracy_plan.md`: rules and targets, written before the results they govern.
- `evaluation_log.md`: every validation round and the one test run.

The report and deck are generated from the study outputs, so their numbers always match `reports/`:

```bash
cd docs/build && npm install && cd ../..
node docs/build/report.js        # content in docs/build/report_content.js
node docs/build/deck.js
```

To check them by eye: `docker build -t heritage-render -f docs/build/render.Dockerfile docs/build`, then convert
to PDF with LibreOffice inside that image.
