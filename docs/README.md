# Documents

- `Heritage_Topic_Finder_Report.docx`: the project report (DFDs, methods, every result, limits).
- `Heritage_Topic_Finder_Deck.pptx`: the presentation deck, with speaker notes.
- `viva_notes.md`: viva questions and answers, by area.
- `paper_draft.md`: short-paper draft on the script-vs-topic and OCR findings.

The report and deck are generated from the study outputs, so their numbers always match `reports/`:

```bash
cd docs/build && npm install && cd ../..
node docs/build/report.js
node docs/build/deck.js
```

To check them by eye: `docker build -t heritage-render -f docs/build/render.Dockerfile docs/build`, then convert
to PDF with LibreOffice inside that image.
