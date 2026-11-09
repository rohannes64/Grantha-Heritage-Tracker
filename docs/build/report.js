// Builds docs/Grantha_Report.docx from the study outputs in reports/ and web/data/.
// Run from the project root:  node docs/build/report.js
const fs = require("fs");
const path = require("path");
const sizeOf = (() => { const m = require("image-size"); return m.imageSize || m.default || m; })();
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, LevelFormat, PageBreak, TableOfContents, Footer, PageNumber, BorderStyle,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const FONT = "Arial";
const W = 9638;                       // A4 with 2 cm margins, in DXA
const f = (x, d = 3) => (x == null ? "n/a" : Number(x).toFixed(d));
const pct = (x, d = 0) => `${(100 * x).toFixed(d)}%`;
const n = (x) => Number(x).toLocaleString("en-IN");

// ---------- building blocks
const P = (text, opts = {}) => new Paragraph({ spacing: { after: 120, line: 300 }, ...opts,
  children: (Array.isArray(text) ? text : [text]).map((t) => (typeof t === "string" ? new TextRun(t) : t)) });
const b = (t) => new TextRun({ text: t, bold: true });
const i = (t) => new TextRun({ text: t, italics: true });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const bullet = (t) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: 290 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === "string" ? new TextRun(x) : x)) });
let listNo = 0;
const newList = () => { listNo += 1; };
const numbered = (t) => new Paragraph({ numbering: { reference: "numbers", level: 0, instance: listNo }, spacing: { after: 60, line: 290 },
  children: (Array.isArray(t) ? t : [t]).map((x) => (typeof x === "string" ? new TextRun(x) : x)) });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

let figNo = 0, tabNo = 0;
function figure(rel, caption, widthPx = 620) {
  const file = path.join(ROOT, rel);
  const data = fs.readFileSync(file);
  const d = sizeOf(data);
  const w = Math.min(widthPx, 640), h = Math.round((d.height / d.width) * w);
  figNo += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data, transformation: { width: w, height: h },
        altText: { title: caption, description: caption, name: path.basename(rel) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: `Figure ${figNo}. `, bold: true, size: 18 }), new TextRun({ text: caption, size: 18 })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(caption, heads, rows, widths, { highlight } = {}) {
  const total = widths.reduce((a, c) => a + c, 0);
  const scale = W / total;
  const cw = widths.map((x) => Math.floor(x * scale));
  cw[cw.length - 1] += W - cw.reduce((a, c) => a + c, 0);
  const cell = (text, j, { head, hi } = {}) => new TableCell({
    borders, width: { size: cw[j], type: WidthType.DXA },
    shading: head ? { fill: "E8E2D6", type: ShadingType.CLEAR, color: "auto" } : hi ? { fill: "FFF4DF", type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: j > 0 && /^[-\d.,%+ ]+$|^n\/a$/.test(String(text)) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), bold: !!head, size: 18 })] })],
  });
  tabNo += 1;
  return [
    new Paragraph({ spacing: { before: 160, after: 80 }, keepNext: true,
      children: [new TextRun({ text: `Table ${tabNo}. `, bold: true, size: 18 }), new TextRun({ text: caption, size: 18 })] }),
    new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: cw, rows: [
      new TableRow({ tableHeader: true, children: heads.map((h, j) => cell(h, j, { head: true })) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, j) => cell(c, j, { hi: highlight && highlight(ri) })) })),
    ] }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}


// ---------- content (v2), in report_content.js
const content = require("./report_content.js")({ P, b, i, H1, H2, bullet, numbered, newList, pageBreak, figure, table, f, pct, n,
  AlignmentType, Paragraph, TextRun, TableOfContents, HeadingLevel, FONT, J });

const doc = new Document({
  creator: "Grantha team", title: "Grantha: project report",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 32, bold: true, color: "3B2A1A" }, paragraph: { spacing: { before: 360, after: 160 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 26, bold: true, color: "3B2A1A" }, paragraph: { spacing: { before: 240, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "Grantha, SIH26096    ", size: 16, color: "808080" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" })] })] }) },
    children: content,
  }],
});

const out = path.join(ROOT, "docs", "Grantha_Report.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(out, buf); console.log("wrote", out, figNo, "figures", tabNo, "tables"); });
