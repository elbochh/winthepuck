const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  ExternalHyperlink, LevelFormat, convertInchesToTwip, PageBreak,
} = require("docx");

// ---- page geometry (US Letter) -----------------------------------------
const PAGE = { width: 12240, height: 15840 };
const MARGIN = 1440;
const CONTENT = PAGE.width - MARGIN * 2;   // 9360 dxa

// ---- colours ------------------------------------------------------------
const INK = "1B2430";
const MUTED = "5A6472";
const ACCENT = "0F6FAF";
const HEAD_BG = "E8EEF4";
const ZEBRA = "F6F8FA";
const CODE_BG = "F2F4F7";

// ---- small builders -----------------------------------------------------
const P = (text, opts = {}) => new Paragraph({
  alignment: opts.align,
  spacing: { before: opts.before ?? 0, after: opts.after ?? 140, line: 276 },
  indent: opts.indent,
  children: [new TextRun({
    text, size: opts.size ?? 21, color: opts.color ?? INK,
    bold: opts.bold, italics: opts.italics, font: opts.font ?? "Calibri",
  })],
});

const Rich = (runs, opts = {}) => new Paragraph({
  alignment: opts.align,
  spacing: { before: opts.before ?? 0, after: opts.after ?? 140, line: 276 },
  children: runs.map(r => typeof r === "string"
    ? new TextRun({ text: r, size: 21, color: INK, font: "Calibri" })
    : new TextRun({ font: "Calibri", size: 21, color: INK, ...r })),
});

const H1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 360, after: 160 },
  children: [new TextRun({ text, size: 30, bold: true, color: INK, font: "Calibri" })],
});

const H2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 260, after: 120 },
  children: [new TextRun({ text, size: 24, bold: true, color: ACCENT, font: "Calibri" })],
});

const Bullet = (text, level = 0) => new Paragraph({
  numbering: { reference: "bullets", level },
  spacing: { after: 90, line: 276 },
  children: [new TextRun({ text, size: 21, color: INK, font: "Calibri" })],
});

const Code = (lines) => new Paragraph({
  spacing: { before: 90, after: 150 },
  shading: { type: ShadingType.CLEAR, fill: CODE_BG },
  indent: { left: 180, right: 180 },
  border: {
    top: { style: BorderStyle.SINGLE, size: 2, color: "D5DBE2" },
    bottom: { style: BorderStyle.SINGLE, size: 2, color: "D5DBE2" },
    left: { style: BorderStyle.SINGLE, size: 2, color: "D5DBE2" },
    right: { style: BorderStyle.SINGLE, size: 2, color: "D5DBE2" },
  },
  children: lines.flatMap((l, i) => [
    ...(i ? [new TextRun({ break: 1 })] : []),
    new TextRun({ text: l, font: "Consolas", size: 18, color: "17303F" }),
  ]),
});

const Rule = () => new Paragraph({
  spacing: { before: 60, after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "C9D3DC" } },
  children: [],
});

// widths must sum to CONTENT
function makeTable(header, rows, widths) {
  const cell = (text, { bold, fill, align, size } = {}, w) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: [new Paragraph({
      alignment: align,
      spacing: { after: 0, line: 260 },
      children: [new TextRun({
        text: String(text), bold, size: size ?? 19,
        color: bold ? INK : MUTED, font: "Calibri",
      })],
    })],
  });

  return new Table({
    columnWidths: widths,
    width: { size: CONTENT, type: WidthType.DXA },
    borders: {
      top:    { style: BorderStyle.SINGLE, size: 4, color: "C9D3DC" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "C9D3DC" },
      left:   { style: BorderStyle.SINGLE, size: 4, color: "C9D3DC" },
      right:  { style: BorderStyle.SINGLE, size: 4, color: "C9D3DC" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "DDE3E9" },
      insideVertical:   { style: BorderStyle.SINGLE, size: 2, color: "DDE3E9" },
    },
    rows: [
      new TableRow({
        tableHeader: true,
        children: header.map((h, i) => cell(h, { bold: true, fill: HEAD_BG }, widths[i])),
      }),
      ...rows.map((r, ri) => new TableRow({
        children: r.map((c, i) => cell(c, {
          fill: ri % 2 ? ZEBRA : undefined,
          bold: i === 0 && header.length > 2,
        }, widths[i])),
      })),
    ],
  });
}

const numbering = {
  config: [{
    reference: "bullets",
    levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.2) } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: convertInchesToTwip(0.6), hanging: convertInchesToTwip(0.2) } } } },
    ],
  }],
};

const sectionProps = {
  page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } },
};

function titleBlock(kicker, title, subtitle) {
  return [
    new Paragraph({
      spacing: { after: 60 },
      children: [new TextRun({ text: kicker.toUpperCase(), size: 18, bold: true,
        color: ACCENT, font: "Calibri", characterSpacing: 40 })],
    }),
    new Paragraph({
      spacing: { after: 80 },
      children: [new TextRun({ text: title, size: 40, bold: true, color: INK, font: "Calibri" })],
    }),
    new Paragraph({
      spacing: { after: 200 },
      children: [new TextRun({ text: subtitle, size: 22, color: MUTED, font: "Calibri" })],
    }),
    Rule(),
  ];
}

module.exports = {
  Document, Packer, Paragraph, TextRun, AlignmentType, ExternalHyperlink, PageBreak,
  P, Rich, H1, H2, Bullet, Code, Rule, makeTable, numbering, sectionProps,
  titleBlock, CONTENT, INK, MUTED, ACCENT, HEAD_BG, ShadingType, BorderStyle,
  TableCell, TableRow, Table, WidthType, fs,
};
