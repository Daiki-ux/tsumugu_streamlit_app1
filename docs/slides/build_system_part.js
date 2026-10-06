// docs/slides/build_system_part.js — 特別監査会資料の「システムパート」を作る（前段資料と同じデザイン）
//   使い方: NODE_PATH=<pptxgenjs のある node_modules> node docs/slides/build_system_part.js out.pptx
//   1 枚目はエグゼクティブサマリ（別案はサマリとストーリーの 2 枚。merge_deck.py が全体の 2 枚目へ移す）。ページ番号は merge_deck.py が振り直す
const pptxgen = require("pptxgenjs");
const OUT = process.argv[2];
// VARIANT=story で別案（外部環境 → 内部環境 → 解決策 → 文化 → 収益 → その先 の大枠を前に出した版）
// VARIANT=short で別案の 7 分版（前段の背景などを 1 枚に作り直した統合スライドを含む）
const SHORT = process.env.VARIANT === "short";
const ALT = process.env.VARIANT === "story" || SHORT;
const S = (base, short) => (SHORT ? short : base);
const V = (base, alt) => (ALT ? alt : base);

// 前段資料（デジタル庁デザインシステムをもとにした資料）の色と寸法
const C = {
  ink: "1A1A1A", sub: "666666", line: "CCCCCC", grey: "F2F2F2", white: "FFFFFF",
  blue: "0017C1", blueSoft: "E8F1FE", blueMid: "8EA9DB", blueBg: "D9E6FF",
  green: "197A4B", greenSoft: "E6F5EC", amber: "806300", amberSoft: "FBF5E0", red: "CE0000", redSoft: "FDEEEE",
  tag: "C5E0B4", teal: "1E7F7A", tealSoft: "E3F4F2",
};
const F = "Noto Sans JP";
const W = 13.33, X0 = 0.67, CW = 12.0;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";

function T(s, t, o) { s.addText(t, Object.assign({ isTextBox: true, fontFace: F, color: C.ink, margin: 0, valign: "top" }, o)); }
function box(s, x, y, w, h, fill, o = {}) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill },
    line: o.line ? { color: o.line, width: o.lw || 1, dashType: o.dash ? "dash" : "solid" } : { color: fill, width: 0 } });
}
function head(s, title, lead, tag) {
  s.background = { color: C.white };
  T(s, title, { x: X0, y: 0.5, w: CW - 1.2, h: 0.75, fontSize: 30, bold: true, valign: "middle" });
  s.addShape(pres.shapes.LINE, { x: X0, y: 1.6, w: CW, h: 0, line: { color: C.line, width: 1 } });
  if (lead) T(s, lead, { x: X0, y: 1.78, w: CW, h: 0.6, fontSize: 16, lineSpacingMultiple: 1.2 });
  if (tag) { box(s, 11.64, 0.15, 1.5, 0.35, C.tag); T(s, tag, { x: 11.69, y: 0.15, w: 1.45, h: 0.35, fontSize: 12, valign: "middle" }); }
  T(s, "0", { x: 11.87, y: 6.92, w: 0.8, h: 0.35, fontSize: 12, color: C.sub, align: "right", valign: "middle" });
}
function caption(s, t) { T(s, t, { x: X0, y: 6.92, w: 10.9, h: 0.35, fontSize: 11, color: C.sub, valign: "middle" }); }
function card(s, x, y, w, h, title, body, o = {}) {
  box(s, x, y, w, h, o.fill || C.grey, { line: o.line, dash: o.dash, lw: o.lw });
  const runs = [];
  if (o.kicker) runs.push({ text: o.kicker, options: { fontSize: o.ks || 11, bold: true, color: o.kc || C.blue, breakLine: true } });
  runs.push({ text: title, options: { fontSize: o.ts || 16, bold: true, color: o.tc || C.ink, breakLine: !!body } });
  if (body) runs.push({ text: body, options: { fontSize: o.bs || 13, color: o.bc || C.sub } });
  T(s, runs, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: h - 0.25, lineSpacingMultiple: 1.2, paraSpaceAfter: 3 });
}
function arrow(s, x, y, w) { s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: C.sub, width: 1.5, endArrowType: "triangle" } }); }
function table(s, rows, o) {
  const hdr = rows[0].map((t) => ({ text: t, options: { bold: true, color: C.sub, fill: { color: C.grey }, fontSize: (o.fs || 13) - 1 } }));
  const body = rows.slice(1).map((r) => r.map((t, i) => ({ text: t, options: { bold: i === 0, fontSize: o.fs || 13, color: C.ink } })));
  s.addTable([hdr, ...body], { x: o.x || X0, y: o.y, w: o.w || CW, colW: o.colW, rowH: o.rowH, fontFace: F, valign: "middle",
    border: { type: "solid", pt: 0.75, color: C.line }, margin: [0.05, 0.12, 0.05, 0.12] });
}

// ============ エグゼクティブサマリ（全体の 2 枚目に置く） ============
{
  const s = pres.addSlide();
  head(s, "エグゼクティブサマリ", null, "サマリ");
  const rows = ALT ? [
    ["WHY", "なぜ", "貸出の機会が増えた今、地場企業とのつながりの深さが銀行の差になる。だが地場企業は承継に不安を抱え、行内で承継に取り組める人は限られ、知見は異動のたびに失われる"],
    ["WHAT", "何を", "ベテランの勘と判断基準を言葉にし、LLM で経験の浅い担当者にも知見と示唆を届ける「ツムグ」。承継に取り組める人を増やす。書くのはいつもの日報だけ"],
    ["HOW", "どうやって", "日々の日報がクエリとなり、貯まった記録から示唆が返る。事業の継続を意識した営業を文化にする。ツムグの情報は融資の判断には使わない"],
    ["ROI", "投資対効果", "企業が続けば貸出が続き、承継・相続の支援は手数料になる。3 年の費用 4,900 万円に対し、中位の試算で効果は約 2.3 億円（約 4.8 倍）、2 年目に回収"],
  ] : [
    ["WHY", "なぜ", "金利のある世界では、地域企業との関係の深さが収益の差になる。その深さは担当者個人の記憶にあり、異動のたびに失われ、支援の機会を見落としている"],
    ["WHAT", "何を", "Salesforce の画面の中に置く「つなぐ層」。いつもの日報を読み、過去の記録と重ねて予兆に意味を付け、相談できる人と社内の支援事例につなぐ。最初のテーマは事業承継"],
    ["HOW", "どうやって", "新しい入力はつくらない。AI が記録・事例・人を集めて読み、予兆の判断には現場の知見（ベテランの勘と判断基準）を言葉にした基準を使う。点数化せず、与信・人事評価には使わない"],
    ["ROI", "投資対効果", "3 年の費用 4,900 万円に対し、中位の試算で効果は約 2.3 億円（約 4.8 倍）、2 年目に回収。約 7 割は、増えた貸出機会を案件に変える「攻め」の効果"],
  ];
  rows.forEach(([en, ja, body], i) => {
    const y = 1.85 + i * 1.08;
    box(s, X0, y, 1.8, 0.95, C.blue);
    T(s, [{ text: en, options: { fontSize: 20, bold: true, color: C.white, breakLine: true } }, { text: ja, options: { fontSize: 11, color: C.white } }],
      { x: X0, y: y + 0.12, w: 1.8, h: 0.8, align: "center" });
    box(s, X0 + 1.95, y, CW - 1.95, 0.95, C.blueSoft);
    T(s, body, { x: X0 + 2.15, y, w: CW - 2.35, h: 0.95, fontSize: 15, valign: "middle", lineSpacingMultiple: 1.15 });
  });
  box(s, X0, 6.2, CW, 0.62, C.blueMid);
  T(s, V("その関係を、個人の記憶ではなく、組織の資産にする。", "貸し続けられる環境を、自ら作る。"), { x: X0 + 0.3, y: 6.2, w: CW - 0.6, h: 0.62, fontSize: 18, bold: true, color: C.white, valign: "middle" });
  if (ALT) s.addNotes("結論から。なぜ：貸出の機会が増えた今、地場企業とのつながりが差になるのに、地場企業は承継に不安を抱え、行内で承継に取り組める人は限られている。何を：ベテランの知見を言葉にし、LLMで経験の浅い担当者にも届けるツムグ。承継に取り組める人を増やします。どうやって：日報がクエリになり示唆が返る。事業の継続を意識した営業を文化にします。投資対効果：企業が続けば貸出が続き、支援は手数料にもなる。3年で費用4,900万円に対し中位で約2.3億円。一言でいうと、貸し続けられる環境を自ら作る、です。");
  else s.addNotes("結論から。なぜ：金利のある世界では関係の深さが収益の差になるのに、その深さは担当者の記憶にあり、異動で失われる。何を：SFAの中の『つなぐ層』。最初のテーマは事業承継。どうやって：新しい入力はつくらず、AIが記録を読み、予兆の判断には現場の知見を言葉にした基準を使う。投資対効果：3年で費用4,900万円に対し、中位で約2.3億円。その7割は攻めの効果です。");
}

// ============ ストーリーの全体像（別案だけ） ============
if (ALT) {
  const s = pres.addSlide();
  head(s, "ツムグのストーリー", "なぜ銀行がツムグに投資するのか。外部環境から、その先の広がりまで", "サマリ");
  const st = [
    ["外部環境", "貸出の機会が増え、地場企業とのつながりの深さが差になる。一方、地場企業は高齢化と承継問題を抱える", C.grey, C.sub],
    ["内部環境", "承継の課題に取り組める人は限られる。定期異動も多く、スキルと知見は個人の中にとどまる", C.grey, C.sub],
    ["解決策：ツムグ", "ベテランの勘と判断基準を言葉にし、LLM で経験の浅い担当者にも届ける。書くのはいつもの日報だけ", C.blueSoft, C.blue],
    ["文化", "日報がクエリとなり、貯まった記録から示唆が返る。事業の継続を意識した営業が当たり前になる", C.blueSoft, C.blue],
    ["収益", S("企業が続けば、雇用と技術が守られ、貸出が続く。承継・相続の支援は手数料に。信頼で取引が安定する", "企業が続けば貸出が続き、承継・相続の支援は手数料に。3 年で効果は約 2.3 億円（費用の約 4.8 倍）"), C.greenSoft, C.green],
    ["その先", "承継 → 成長 → 相続へと支援が深まり、銀行は地域の企業と企業をつなぐ役になる", C.greenSoft, C.green],
  ];
  const gap = 0.35, w = (CW - gap * 2) / 3, h = 1.45;
  st.forEach(([k, d, f, col], i) => {
    const x = X0 + (i % 3) * (w + gap), y = 2.45 + Math.floor(i / 3) * (h + 0.25);
    box(s, x, y, w, h, f);
    T(s, [{ text: `${i + 1}　${k}`, options: { fontSize: 16, bold: true, color: col, breakLine: true } }, { text: " ", options: { fontSize: 5, breakLine: true } }, { text: d, options: { fontSize: 12.5 } }],
      { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: h - 0.25, lineSpacingMultiple: 1.2 });
    if (i % 3 < 2) arrow(s, x + w + 0.04, y + h / 2, gap - 0.08);
  });
  box(s, X0, 5.9, CW, 0.85, C.blueMid);
  T(s, [{ text: "貸し続けられる環境を、自ら作る。　", options: { fontSize: 20, bold: true, color: C.white } }, { text: "融資するか、しないかを判断するだけの銀行は先細る", options: { fontSize: 13, color: C.white } }],
    { x: X0 + 0.3, y: 5.9, w: CW - 0.6, h: 0.85, valign: "middle" });
  s.addNotes("ストーリーの全体像です。外部環境：貸出の機会が増え、地場企業とのつながりが差になる一方、地場企業は承継問題を抱える。内部環境：承継に取り組める人は限られ、異動で知見は属人化している。そこでツムグ。ベテランの知見を言葉にし、LLMで経験の浅い担当者にも届けて、取り組める人を増やす。日報がクエリとなって示唆が返り、事業の継続を意識した営業が文化になる。企業が続けば貸出が続き、支援は手数料にもなる。そしてその先、銀行は地域のつなぎ役になる。融資するかしないかだけの銀行は先細る。だからこそ、貸し続けられる環境を自ら作る。");
}

// ============ 外部環境（7 分版だけ：前段 2〜4 枚目と「なぜ事業承継から」を 1 枚に） ============
if (SHORT) {
  const s = pres.addSlide();
  head(s, "外部環境：関係の深さが、銀行の差になる", "金利が戻り、貸出の機会が増えた。その機会を捉えられるかは、地場企業との関係の深さで決まる", "外部環境");
  const cw = (CW - 0.5) / 3, y = 2.45;
  // 1. 金利
  box(s, X0, y, cw, 3.15, C.grey);
  T(s, "金利が戻った", { x: X0 + 0.2, y: y + 0.12, w: cw - 0.4, h: 0.35, fontSize: 15, bold: true });
  s.addChart(pres.charts.LINE, [{ name: "政策金利（%）", labels: ["2016/1", "2024/3", "2024/7", "2025/1", "2026/6"], values: [-0.1, 0.1, 0.25, 0.5, 1.0] }],
    { x: X0 + 0.1, y: y + 0.5, w: cw - 0.2, h: 2.0, chartColors: [C.blue], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 6,
      showValue: true, dataLabelPosition: "t", dataLabelFontSize: 9, dataLabelFontFace: F, dataLabelColor: C.ink, dataLabelFormatCode: "0.00",
      catAxisLabelFontSize: 9, catAxisLabelFontFace: F, catAxisLabelColor: C.sub, valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false });
  T(s, "政策金利は 2026 年 6 月に 1.00%。年内のさらなる引き上げも見込まれる", { x: X0 + 0.2, y: y + 2.5, w: cw - 0.4, h: 0.6, fontSize: 11, color: C.sub, lineSpacingMultiple: 1.1 });
  // 2. 預貸率
  const x2 = X0 + cw + 0.25;
  box(s, x2, y, cw, 3.15, C.grey);
  T(s, "貸出の機会が増えた", { x: x2 + 0.2, y: y + 0.12, w: cw - 0.4, h: 0.35, fontSize: 15, bold: true });
  s.addChart(pres.charts.BAR, [{ name: "前年同期", labels: ["全国銀行", "地方銀行"], values: [60.6, 73.9] }, { name: "2026年1〜3月期", labels: ["全国銀行", "地方銀行"], values: [62.6, 75.8] }],
    { x: x2 + 0.1, y: y + 0.5, w: cw - 0.2, h: 2.0, barDir: "col", barGrouping: "clustered", chartColors: ["BBBBBB", C.blueMid], barGapWidthPct: 50,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelFontFace: F, dataLabelColor: C.ink, dataLabelFormatCode: "0.0",
      catAxisLabelFontSize: 9.5, catAxisLabelFontFace: F, catAxisLabelColor: C.sub, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 90, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      showLegend: true, legendPos: "b", legendFontSize: 8.5, legendFontFace: F });
  T(s, "預貸率は 2023 年頃を底に上昇。ただし、機会を捉えられる銀行とそうでない銀行の差が広がる", { x: x2 + 0.2, y: y + 2.5, w: cw - 0.4, h: 0.6, fontSize: 11, color: C.sub, lineSpacingMultiple: 1.1 });
  // 3. 地場企業の承継
  const x3 = X0 + 2 * (cw + 0.25);
  box(s, x3, y, cw, 3.15, C.amberSoft);
  T(s, "一方、地場企業は承継に不安", { x: x3 + 0.2, y: y + 0.12, w: cw - 0.4, h: 0.35, fontSize: 15, bold: true, color: C.amber });
  [["50.1%", "全国企業の後継者不在率（2025年）"], ["約 3 割", "代表者が 70 代でも後継者が不在"], ["最長 10 年", "承継の準備に必要とされる期間"]].forEach(([b, l], i) => {
    const yy = y + 0.6 + i * 0.82;
    T(s, b, { x: x3 + 0.2, y: yy, w: 1.75, h: 0.6, fontSize: 22, bold: true, color: C.amber, valign: "middle" });
    T(s, l, { x: x3 + 1.95, y: yy, w: cw - 2.1, h: 0.6, fontSize: 11.5, valign: "middle", lineSpacingMultiple: 1.1 });
  });
  box(s, X0, 5.8, CW, 0.9, C.blueMid);
  T(s, [{ text: "差を生むのは、既存顧客との関係の深さ。", options: { fontSize: 16, bold: true, color: C.white, breakLine: true } },
    { text: "関係が浅いと他行に乗り換えられる。中でも、関係が途切れたときに失うものが最も大きいのが事業承継（最初のテーマ）", options: { fontSize: 12.5, color: C.white } }],
    { x: X0 + 0.25, y: 5.8, w: CW - 0.5, h: 0.9, valign: "middle", lineSpacingMultiple: 1.1 });
  caption(s, "出典：日本経済新聞・大和総研（政策金利）、日本総研（預貸率・地方銀行の環境）、帝国データバンク・MS コンパス（後継者不在）");
  s.addNotes("外部環境です。日銀の利上げで政策金利は1.00%になり、預金に金利がつく時代に戻りました。預貸率も2023年頃を底に上がり、貸出の機会は増えています。ただし、その機会を捉えられる銀行とそうでない銀行の差が広がっています。差を生むのは、既存のお客さまとの関係の深さです。浅いと他行に乗り換えられます。一方で地場企業は、後継者不在が約半数、70代でも3割が不在と、承継に不安を抱えています。関係が途切れたときに失うものが最も大きいのが事業承継なので、ここを最初のテーマにしました。");
}

// ============ 内部環境（7 分版だけ：前段 5〜7 枚目を 1 枚に） ============
if (SHORT) {
  const s = pres.addSlide();
  head(s, "内部環境：知見が、担当者個人にとどまっている", "承継の課題に取り組める人は限られ、定期異動のたびに知見が失われる。その結果、支援の機会を見落とす", "内部環境");
  const fl = [["気づきの発生", "雑談や表情から、担当者が違和感に気づく"], ["記録のばらつき", "残すかどうかも、粒度も担当者次第"], ["記憶への依存", "記録されない気づきは、頭の中にだけ残る"]];
  const fw = (CW - 0.9) / 3;
  fl.forEach(([t, d], i) => {
    const x = X0 + i * (fw + 0.45);
    card(s, x, 2.45, fw, 1.05, t, d, { fill: C.grey, ts: 14, bs: 11.5, kicker: String(i + 1), ks: 11 });
    if (i < 2) arrow(s, x + fw + 0.06, 2.97, 0.33);
  });
  const lw = 7.0;
  T(s, "担当者任せが生むリスク", { x: X0, y: 3.75, w: lw, h: 0.35, fontSize: 14, bold: true, color: C.red });
  const rk = [["承継に取り組める人が限られる", "経験のある人は一部。本部に相談が来るのは、事態が表に出てから"], ["異動・退職で知見が消える", "後継者問題や経営の違和感が、引き継がれずに消える"],
    ["担当者ごとにばらつく", "同じ地域でも、顧客理解の深さが経験年数や関心で変わる"], ["関係が途切れる", "担当が替わるたびに、顧客との関係がゼロから始まる"]];
  rk.forEach(([t, d], i) => {
    const yy = 4.15 + i * 0.58;
    box(s, X0, yy, 0.08, 0.5, C.red);
    T(s, [{ text: t + "　", options: { fontSize: 13, bold: true } }, { text: d, options: { fontSize: 11.5, color: C.sub } }], { x: X0 + 0.2, y: yy, w: lw - 0.2, h: 0.5, valign: "middle" });
  });
  const rx = X0 + lw + 0.3, rw = CW - lw - 0.3;
  box(s, rx, 3.75, rw, 2.75, C.redSoft);
  T(s, [{ text: "結果：支援機会の見落とし", options: { fontSize: 15, bold: true, color: C.red, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "支援すべきタイミングを逃す", options: { bullet: true, breakLine: true } }, { text: "同じ質問をお客さまに繰り返し、信頼を損なう", options: { bullet: true, breakLine: true } },
    { text: "担当交代のたびに、関係が後退する", options: { bullet: true, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "環境は変わったのに、組織の情報の持ち方は変わっていない", options: { fontSize: 12, bold: true } }],
    { x: rx + 0.2, y: 3.85, w: rw - 0.4, h: 2.55, fontSize: 12.5, paraSpaceAfter: 4, lineSpacingMultiple: 1.1 });
  caption(s, "しかし、こうした何気ないやり取りの中に、お客さまとの関係を深める宝が眠っている");
  s.addNotes("内部環境です。担当者は面談の中で違和感に気づきますが、記録に残すかは人次第で、多くは担当者の記憶にしか残りません。その結果、承継に取り組める人は一部に限られ、異動や退職で知見が消え、担当が替わるたびに関係がゼロから始まります。支援すべきタイミングを逃し、同じ質問を繰り返して信頼を損なう。環境は変わったのに、組織の情報の持ち方は変わっていません。");
}

// ============ 区切り ============
{
  const s = pres.addSlide();
  s.background = { color: C.blueBg };
  T(s, "システムパート", { x: 0.67, y: 2.3, w: 11, h: 1.0, fontSize: 40, bold: true });
  T(s, "3 つの条件に、ツムグはどう応えるか", { x: 0.67, y: 3.4, w: 11, h: 0.6, fontSize: 22 });
  T(s, "条件への答え ／ なぜ事業承継から ／ プロダクト ／ 技術 ／ 予兆の判断 ／ 入力→処理→出力 ／ デモ ／ 当初案からの変化 ／ 効果 ／ ROI ／ 投資 ／ 広がり方",
    { x: 0.67, y: 4.4, w: 11.8, h: 0.8, fontSize: 13, color: C.sub, lineSpacingMultiple: 1.3 });
  T(s, "0", { x: 11.87, y: 6.92, w: 0.8, h: 0.35, fontSize: 12, color: C.sub, align: "right", valign: "middle" });
  s.addNotes("ここからシステムパート。前段で挙げた3つの条件に、ツムグがどう応えるかをお話しします。");
}

// ============ 3 つの条件への答え ============
{
  const s = pres.addSlide();
  head(s, "3 つの条件に、ツムグはこう応える", S("前段の「残る・引き継がれる・つながる」を、新しい入力を増やさずに満たす", "属人化を解くには、気づきが「残る・引き継がれる・つながる」ことが要る。それぞれに応える機能"), "システム");
  const cols = SHORT ? [
    ["残る", "いつもの日報の気づきが、そのまま残る", "新しい入力欄はつくらない。書く補助：音声で入力・AI で整える・下書き保存", "日報（訪問後）の画面"],
    ["引き継がれる", "前任者たちの記録を、訪問前に読める", "これまでの予兆と根拠／次の世代につなぎたいもの／会話のヒント／担当期間ごとの面談メモ", "取引先（訪問前）の画面"],
    ["つながる", "記録が重なったときだけ、予兆として知らせる", "① 判定 ② 次にすること ③ 相談する ④ 参考にする（社内事例・現場の知恵・制度）", "日報を登録したときの反応"],
  ] : [
    ["残る", "いつもの日報に書かれた気づきが、そのまま残る", "新しい入力欄はつくらない。音声で入力・AI で整える・下書き保存で、書く手間を減らす", "日報（訪問後）の画面"],
    ["引き継がれる", "前任者たちの記録を、訪問前にまとめて読める", "担当期間ごとの面談メモ、これまでに出てきた予兆と根拠。相談すると、相談相手もその企業の記録を読める", "取引先（訪問前）の画面"],
    ["つながる", "記録が重なったときだけ、予兆として知らせる", "相談できる人（前任者・似た事例の担当者）、社内の支援事例、公的な制度につなぐ", "日報を登録したときの反応"],
  ];
  const cw = (CW - 0.6) / 3;
  cols.forEach(([cond, ans, det, where], i) => {
    const x = X0 + i * (cw + 0.3);
    box(s, x, 2.55, cw, 0.75, C.blueSoft);
    T(s, cond, { x: x + 0.2, y: 2.55, w: cw - 0.4, h: 0.75, fontSize: 20, bold: true, color: C.blue, valign: "middle" });
    T(s, "▼", { x, y: 3.32, w: cw, h: 0.3, fontSize: 12, color: C.sub, align: "center" });
    box(s, x, 3.65, cw, S(2.35, 2.15), C.white, { line: C.line });
    T(s, [{ text: ans, options: { fontSize: S(16, 15), bold: true, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } }, { text: det, options: { fontSize: S(13, 12), color: C.sub } }],
      { x: x + 0.2, y: 3.78, w: cw - 0.4, h: S(1.65, 1.6), lineSpacingMultiple: S(1.2, 1.12) });
    T(s, where, { x: x + 0.2, y: S(5.55, 5.42), w: cw - 0.4, h: 0.35, fontSize: 11, bold: true, color: C.green });
  });
  if (SHORT) T(s, "支店長は「対話の状況」を点数ではなく段階で、本部は受けた相談と「くり返し出ている話」を見る", { x: X0, y: 5.86, w: CW, h: 0.3, fontSize: 12, color: C.ink });
  box(s, X0, 6.2, CW, 0.62, C.amberSoft);
  T(s, "最終判断は常に担当者・支店長が行う。点数化せず、与信・人事評価には使わない", { x: X0 + 0.25, y: 6.2, w: CW - 0.5, h: 0.62, fontSize: 15, bold: true, color: C.amber, valign: "middle" });
  s.addNotes("前段の3つの条件への答えです。残る：新しい欄はつくらず、いつもの日報を読む。書く手間は音声入力などで減らす。引き継がれる：前任者の記録を訪問前にまとめて読める。つながる：記録が重なったときだけ知らせ、人と事例につなぐ。判断は人が行い、与信や評価には使いません。");
}

// ============ なぜ事業承継から ============
{
  const s = pres.addSlide();
  head(s, "なぜ、最初のテーマは事業承継か", "関係が途切れたときに失うものが最も大きく、行内に支援の出口がある", "システム");
  const rs = [
    ["失うものが最も大きい", "後継者が決まらないまま廃業すると、預金・貸出の取引そのものが消える。他行への乗り換え以上の損失になる"],
    ["気づくまでに時間がかかる", "兆しは雑談や小さな変化として、数年かけて日報に現れる。担当が替わると、つながらずに消える"],
    ["支援の出口が行内にある", "事業承継支援室、M&A、事業承継税制。気づきを具体的な支援につなげられる"],
  ];
  rs.forEach(([t, d], i) => card(s, X0, 2.55 + i * 1.4, 5.3, 1.25, t, d, { kicker: `理由 ${i + 1}`, ts: 16, bs: 12.5, fill: C.blueSoft }));
  const stats = [["50.1%", "全国企業の後継者不在率（2025年）", "帝国データバンク"], ["約 3 割", "代表者が 70 代の企業でも後継者が不在", "同調査を紹介した MS コンパス"],
    ["最長 10 年", "ゼロからの事業承継に必要とされる準備期間", "同上（一般論）"], ["約 4 割", "後継者難倒産のうち、代表者が突然動けなくなった「不測の事態」", "同上"]];
  const gx = X0 + 5.6, gw = (X0 + CW - gx - 0.2) / 2, gh = 1.97;
  stats.forEach(([big, lab, src], i) => {
    const x = gx + (i % 2) * (gw + 0.2), y = 2.55 + Math.floor(i / 2) * (gh + 0.16);
    box(s, x, y, gw, gh, C.white, { line: C.line });
    T(s, big, { x: x + 0.2, y: y + 0.12, w: gw - 0.4, h: 0.75, fontSize: 32, bold: true, color: C.blue });
    T(s, lab, { x: x + 0.2, y: y + 0.9, w: gw - 0.4, h: 0.7, fontSize: 12.5, lineSpacingMultiple: 1.15 });
    T(s, src, { x: x + 0.2, y: y + gh - 0.35, w: gw - 0.4, h: 0.28, fontSize: 9.5, color: C.sub });
  });
  caption(s, "人材・設備・取引など他のテーマへは、予兆の定義（rules.json）を足して広げる");
  s.addNotes("関係の深さの話を、最初はなぜ事業承継に絞るのか。理由は3つ。廃業すると取引そのものが消える、兆しが数年かけて現れるので担当交代で消えやすい、そして行内に支援の出口がある。後継者不在は約半数、準備に最長10年、後継者難倒産の4割は不測の事態です。");
}

// ============ プロダクトと主な機能 ============
{
  const s = pres.addSlide();
  head(s, "どんなプロダクトか・主な機能", "Salesforce の画面の中に、ツムグの表示領域を置く。担当者が書くのはいつもの日報だけ", "システム");
  const cols = [
    ["訪問前", "取引先を開く", C.blue, C.blueSoft, [["これまでに出てきた予兆と根拠", "過去 3 年、担当者をまたいで"], ["次の世代につなぎたいもの", "雇用・取引・技術と、その担い手"], ["お客さまとの会話のヒント", "AI のヒントとして記録と区別"], ["面談メモの履歴", "担当期間ごとに折りたたみ"]]],
    ["訪問後", "日報を登録する", C.green, C.greenSoft, [["書く補助", "音声で入力・AI で整える・下書き保存"], ["① 判定", "支援の検討が必要か（4 段階）と理由"], ["② 次にすること ③ 相談する", "会話のヒント、相談できる人、窓口"], ["④ 参考にする", "社内の支援事例・現場の知恵・制度"]]],
    ["支店長・本部", "状況・相談", C.amber, C.amberSoft, [["対話の状況（支店長）", "点数ではなく、支援の段階で"], ["本部の画面", "受けた相談、くり返し出ている話"], ["見える範囲は役割で決まる", "担当先／自支店／相談を受けた企業"], ["パイロット評価・監査", "アンケート集計と監査ログ"]]],
  ];
  const cw = (CW - 0.5) / 3;
  cols.forEach(([t, sub, col, soft, items], i) => {
    const x = X0 + i * (cw + 0.25), y = 2.5;
    box(s, x, y, cw, 0.62, col);
    T(s, [{ text: t + "　", options: { fontSize: 17, bold: true, color: C.white } }, { text: sub, options: { fontSize: 12, color: C.white } }],
      { x: x + 0.2, y, w: cw - 0.4, h: 0.62, valign: "middle" });
    items.forEach(([a, b], j) => {
      const yy = y + 0.72 + j * 0.88;
      box(s, x, yy, cw, 0.8, soft);
      T(s, [{ text: a, options: { fontSize: 14, bold: true, breakLine: true } }, { text: b, options: { fontSize: 12, color: C.sub } }],
        { x: x + 0.18, y: yy + 0.08, w: cw - 0.36, h: 0.7, lineSpacingMultiple: 1.1 });
    });
  });
  caption(s, "パイロット版は Streamlit で SFA の画面を模している（灰色の帯が SFA、点線から下がツムグの領域）");
  s.addNotes("画面は3つの場面に分かれます。訪問前は予兆と根拠、次の世代につなぎたいもの、会話のヒント。訪問後は日報を登録すると判定・次にすること・相談する・参考にするが返ります。支店長と本部は、点数ではなく支援の段階で状況を見ます。");
}

// ============ 技術・仕組み ============
{
  const s = pres.addSlide();
  head(s, "使っている技術・仕組み", "AI が日報を手がかりに記録・事例・人を読み、予兆とアドバイスを書く。知らせるかは現場の知見で決める", "システム");
  const stack = [["画面", "Streamlit（SFA を模擬）", C.grey], ["処理", "Python ／ pandas（照合）／ if 文（判定）", C.blueSoft], ["検索", "scikit-learn の TF-IDF", C.blueSoft],
    ["収集", "requests ＋ BeautifulSoup（公的サイト）", C.blueSoft], ["データ", "SQLite（日報・判定・相談・監査ログ）", C.amberSoft], ["公開", "GitHub ＋ Streamlit Community Cloud", C.grey], ["AI（任意）", "OpenAI：抽出・理由文・助言・文字起こし", C.greenSoft]];
  stack.forEach(([k, v, f], i) => {
    const y = 2.5 + i * 0.6;
    box(s, X0, y, 5.0, 0.52, f, k.startsWith("AI") ? { line: C.green, dash: true } : {});
    T(s, k, { x: X0 + 0.15, y, w: 1.25, h: 0.52, fontSize: 13, bold: true, valign: "middle" });
    T(s, v, { x: X0 + 1.4, y, w: 3.5, h: 0.52, fontSize: 12, color: C.sub, valign: "middle" });
  });
  const rx = X0 + 5.3, rw = CW - 5.3;
  T(s, "工程ごとの担い手", { x: rx, y: 2.45, w: rw, h: 0.4, fontSize: 15, bold: true, color: C.blue });
  table(s, [["工程", "やり方", "そう選んだ理由"],
    ["判定", "現場の知見を訳したルール", "毎回同じ答えが出て、なぜ知らせたかを示せる（次のページ）"],
    ["照合", "pandas", "いつ・誰が・何回を数えるだけ。AI は要らない"],
    ["検索", "TF-IDF", "件数が少なく、なぜその事例が出たか説明できる"],
    ["抽出", "辞書＋LLM", "日報を読み、予兆に当たる文を拾う。引用が原文に無いものは捨てる"],
    ["文章", "LLM", "集めた事例・人だけを根拠に、理由文とアドバイスを書く"]],
    { x: rx, y: 2.9, w: rw, colW: [0.9, 1.9, rw - 2.8], fs: 12, rowH: 0.52 });
  box(s, rx, 6.15, rw, 0.62, C.redSoft);
  T(s, "つながないもの：融資・格付け・人事評価", { x: rx + 0.2, y: 6.15, w: rw - 0.4, h: 0.62, fontSize: 14, bold: true, color: C.red, valign: "middle" });
  caption(s, "LLM のキーが無いときは辞書・定型文・用意した結果で動き、画面にもそう書く（公開中のデモはこの状態）");
  s.addNotes("技術は講義で扱ったものが中心です。日報がクエリになり、AIが過去の記録・事例・人を集めて読み、予兆とアドバイスを書きます。ただし知らせるかどうかの線引きは、現場の知見を訳したルールで決めます。公開中のデモはキーを入れていないので、AIの部分は模擬です。");
}

// ============ システムの全体構成（アーキテクチャ） ============
{
  const s = pres.addSlide();
  head(s, "システムの全体構成（アーキテクチャ）", "SFA の画面の中にツムグの表示領域を置き、日報 1 件ごとに処理して反応を返す。融資・人事のシステムとはつながない", "システム");
  const LX = X0, LW = 8.95, LBL = 1.05;            // 本体の列（左に段の名前）
  const CX = LX + LBL, CWW = LW - LBL;
  function tier(y, h, name, sub, fill) {
    box(s, LX, y, LW, h, fill);
    T(s, [{ text: name, options: { fontSize: 13, bold: true, breakLine: true } }, { text: sub, options: { fontSize: 9, color: C.sub } }], { x: LX + 0.12, y: y + 0.08, w: LBL - 0.1, h: h - 0.1, lineSpacingMultiple: 1.05 });
  }
  function chips(y, h, items, o = {}) {
    const g = 0.08, w = (CWW - 0.15 - g * (items.length - 1)) / items.length;
    items.forEach((it, i) => { const x = CX + i * (w + g); box(s, x, y, w, h, C.white, { line: o.line || C.line, dash: o.dash });
      const [t, d] = Array.isArray(it) ? it : [it, ""];
      T(s, d ? [{ text: t, options: { fontSize: o.ts || 10.5, bold: true, breakLine: true } }, { text: d, options: { fontSize: o.ds || 8.5, color: C.sub } }] : t,
        { x: x + 0.06, y, w: w - 0.12, h, fontSize: o.ts || 10.5, bold: !d, align: "center", valign: "middle", lineSpacingMultiple: 1.0 }); });
  }
  function down(y) { s.addShape(pres.shapes.LINE, { x: LX + 0.5, y, w: 0, h: 0.2, line: { color: C.sub, width: 1.5, beginArrowType: "triangle", endArrowType: "triangle" } }); }
  // 使う人
  tier(2.4, 0.55, "使う人", "", C.white);
  chips(2.46, 0.43, ["法人担当者（担当先）", "支店長（自支店）", "本部 事業承継支援室（相談を受けた企業）"], { ts: 10.5 });
  down(2.97);
  // 画面
  tier(3.19, 0.82, "画面", "SFA の中", C.grey);
  chips(3.25, 0.7, [["取引先（訪問前）", "予兆と根拠・会話のヒント"], ["日報（訪問後）", "音声入力・下書き → 反応"], ["対話の状況", "支店長・段階で"], ["本部", "相談・くり返し出る話"], ["評価・監査", "アンケート・ログ"]]);
  down(4.03);
  // 処理
  tier(4.25, 1.38, "処理", "tsumugu.py\n判定基準は\nrules.json", C.blueSoft);
  const pw1 = CWW * 0.62, pw2 = CWW - 0.15 - pw1 - 0.08;
  box(s, CX, 4.31, pw1, 1.26, C.white, { line: C.blue });
  T(s, [{ text: "反応層（日報 1 件ごと）", options: { fontSize: 10.5, bold: true, color: C.blue, breakLine: true } },
    { text: "② 抽出 → ③ 照合 → ④ 判定 → ⑤ 検索 → ⑥ 人軸 → ⑦ 次の一手", options: { fontSize: 10.5, bold: true, breakLine: true } },
    { text: "辞書＋LLM ／ pandas ／ 現場の知見を訳したルール ／ TF-IDF ／ 担当履歴・相談記録 ／ LLM（無ければ定型文）", options: { fontSize: 8.5, color: C.sub } }],
    { x: CX + 0.1, y: 4.36, w: pw1 - 0.2, h: 1.16, lineSpacingMultiple: 1.15 });
  const kx = CX + pw1 + 0.08;
  box(s, kx, 4.31, pw2, 1.26, C.white, { line: C.blue });
  T(s, [{ text: "ナレッジ層（日報とは別に回す）", options: { fontSize: 10.5, bold: true, color: C.blue, breakLine: true } },
    { text: "⓪ 収集 crawler.py → 貯める → 索引 ranking.py（TF-IDF）", options: { fontSize: 10, breakLine: true } },
    { text: "訪問前のまとめ・入力補助も同じ処理から", options: { fontSize: 8.5, color: C.sub } }],
    { x: kx + 0.1, y: 4.36, w: pw2 - 0.2, h: 1.16, lineSpacingMultiple: 1.15 });
  down(5.65);
  // データ
  tier(5.87, 0.95, "データ", "SQLite\n1 ファイル", C.amberSoft);
  chips(5.93, 0.83, [["行内データ", "企業・行員・担当履歴・相談"], ["日報", "日報・予兆タグ・下書き"], ["ナレッジ", "社内事例・現場の知恵・公的情報"], ["判定と反応", "判定・候補タグ・アンケート"], ["監査ログ", "誰が・いつ・何を見たか"]]);
  // 右：外とのつながり
  const RX = LX + LW + 0.45, RW = X0 + CW - RX;
  const ext = [
    [2.4, 1.62, "つながない", "融資・格付け・人事評価のシステム。判定の結果を流さず、記録を評価に使わない", C.redSoft, C.red, false, null],
    [4.25, 0.64, "公的なサイト（9 ページ）", "中小機構・国税庁を ⓪ 収集", C.white, C.blue, false, 4.57],
    [4.99, 0.64, "LLM（任意・OpenAI）", "抽出・理由文・助言。無ければ模擬", C.greenSoft, C.green, true, 5.31],
    [5.87, 0.95, "合成データ（架空）", "最初に取り込む（10 社・日報 79 件）", C.white, C.amber, false, 6.34],
  ];
  ext.forEach(([y, h, t, d, f, col, dash, ay]) => {
    box(s, RX, y, RW, h, f, { line: col, dash, lw: 1.25 });
    T(s, [{ text: t, options: { fontSize: 11, bold: true, color: col, breakLine: true } }, { text: d, options: { fontSize: 9.5, color: C.ink } }], { x: RX + 0.1, y: y + 0.06, w: RW - 0.2, h: h - 0.1, lineSpacingMultiple: 1.1 });
    if (ay) s.addShape(pres.shapes.LINE, { x: LX + LW + 0.04, y: ay, w: 0.37, h: 0, line: { color: col, width: 1.5, beginArrowType: "triangle", dashType: dash ? "dash" : "solid" } });
  });
  caption(s, "公開：GitHub（非公開リポジトリ）→ Streamlit Community Cloud。認証は SFA、見える範囲（認可）はツムグが役割で決める");
  s.addNotes("全体の構成です。担当者・支店長・本部は、SFAの画面の中のツムグの表示領域を使います。パイロットではStreamlitで模擬しています。日報を登録すると、処理の反応層が抽出から次の一手までを順に行います。日報とは別に、ナレッジ層が公的サイトを集め、TF-IDFの索引を作ります。データはSQLiteの1ファイルで、行内データ・日報・ナレッジ・判定・監査ログを持ちます。外とのつながりは、公的サイト、任意のLLM、最初に取り込む合成データの3つ。融資・格付け・人事評価のシステムとはつなぎません。");
}

// ============ 予兆の判断のしかた ============
{
  const s = pres.addSlide();
  head(s, "予兆の判断に、現場だからわかる知見を使う", "データだけで決めない。ベテランの勘と判断基準を言葉にして形式知にし、記録の事実に当てはめる", "システム");
  const y = 2.5, h = 2.75;
  box(s, X0, y, 3.55, h, C.grey);
  T(s, [{ text: "記録の事実（データ）", options: { fontSize: 15, bold: true, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "日報の記述（いつ・誰が・何を）", options: { bullet: true, breakLine: true } }, { text: "担当の移り変わり", options: { bullet: true, breakLine: true } },
    { text: "顧客マスタ（経営者の年齢・業歴）", options: { bullet: true } }], { x: X0 + 0.2, y: y + 0.18, w: 3.15, h: h - 0.3, fontSize: 13, paraSpaceAfter: 6 });
  T(s, "×", { x: X0 + 3.6, y, w: 0.5, h, fontSize: 28, bold: true, color: C.sub, align: "center", valign: "middle" });
  const mx = X0 + 4.15, mw = 4.6;
  box(s, mx, y, mw, h, C.blueSoft);
  T(s, [{ text: "現場の知見（暗黙知を言葉に）", options: { fontSize: 15, bold: true, color: C.blue, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "何を予兆とみなすか（工場長の退職 → 技術継承の属人化）", options: { bullet: true, breakLine: true } },
    { text: "どう重なると意味があるか（単独では知らせない）", options: { bullet: true, breakLine: true } },
    { text: "いつ黙るか（迷う場合は提示しない）", options: { bullet: true, breakLine: true } },
    { text: "伝え聞きの扱い（「らしい」は未確認）", options: { bullet: true } }], { x: mx + 0.2, y: y + 0.18, w: mw - 0.4, h: h - 0.3, fontSize: 13, paraSpaceAfter: 6 });
  arrow(s, mx + mw + 0.08, y + h / 2, 0.45);
  const ox = mx + mw + 0.62, ow = X0 + CW - ox;
  box(s, ox, y, ow, h, C.greenSoft);
  T(s, [{ text: "判定", options: { fontSize: 15, bold: true, color: C.green, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "種類の異なる予兆が 3 つ以上重なり、うち 2 系統が直近 12 か月に出たときだけ知らせる", options: { fontSize: 13, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "言葉を条件に訳したもの。言葉と条件は並べて持つ", options: { fontSize: 11, color: C.sub } }], { x: ox + 0.2, y: y + 0.18, w: ow - 0.4, h: h - 0.3, lineSpacingMultiple: 1.15 });
  T(s, "一人の勘に頼らないために", { x: X0, y: 5.45, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.amber });
  const g = [["書く・見直すのは本部", "事業承継支援室が判断基準を言葉で書き、本部の画面で見直す"], ["現場の声で増やす", "くり返し出ている話を、本部が予兆に加えるか判断する"], ["結果で確かめる", "担当者の反応（対話を始めた・見送り）を見直しの材料にする"]];
  const gw = (CW - 0.4) / 3;
  g.forEach(([t, d], i) => card(s, X0 + i * (gw + 0.2), 5.85, gw, 0.97, t, d, { fill: C.amberSoft, ts: 13.5, bs: 11.5 }));
  s.addNotes("予兆の判断は、データだけでも、一人のベテランの言葉だけでもありません。日報や担当の移り変わりといった記録の事実に、現場だからわかる知見、つまり何を予兆とみなすか、どう重なると意味があるか、いつ黙るかを当てはめます。ベテランの勘を言葉にして形式知にし、それを条件に訳して判定します。基準は本部が書いて見直し、現場でくり返し出ている話から予兆を増やし、担当者の反応で確かめる。一人の勘に頼らず、組織で育てる仕組みです。");
}

// ============ 入力 → 処理 → 出力 ============
{
  const s = pres.addSlide();
  head(s, "入力 → 処理 → 出力の流れ", "日報 1 件を登録すると、7 つの工程を通り、4 つのまとまりで反応が返る", "システム");
  const y = 2.45, h = 3.0;
  box(s, X0, y, 3.2, h, C.grey);
  T(s, [{ text: "入力", options: { fontSize: 12, bold: true, color: C.sub, breakLine: true } }, { text: "いつもの日報 1 件", options: { fontSize: 17, bold: true, breakLine: true } },
    { text: "面談相手・活動区分・訪問日・業務報告", options: { fontSize: 12, color: C.sub, breakLine: true } }, { text: " ", options: { fontSize: 8, breakLine: true } },
    { text: "照らし合わせる材料", options: { fontSize: 12, bold: true, breakLine: true } }, { text: "過去の記録と担当交代、社内の支援事例、現場の知恵、公的な制度、判定の基準", options: { fontSize: 12, color: C.sub } }],
    { x: X0 + 0.2, y: y + 0.15, w: 2.8, h: h - 0.25, lineSpacingMultiple: 1.15 });
  arrow(s, X0 + 3.28, y + h / 2, 0.4);
  const px = X0 + 3.8, pw = 4.6;
  box(s, px, y, pw, h, C.blueSoft);
  T(s, "処理", { x: px + 0.2, y: y + 0.1, w: 2, h: 0.3, fontSize: 12, bold: true, color: C.blue });
  (SHORT ? [["①", "登録", "SQLite に保存。二重登録を除く"], ["②", "抽出", "辞書＋LLM。伝聞は「未確認」"], ["③", "照合", "pandas で過去 36 か月を並べる"], ["④", "判定", "現場の知見を訳したルール"],
    ["⑤", "検索", "TF-IDF で事例・知恵・制度"], ["⑥", "人軸", "担当履歴・相談記録から"], ["⑦", "次の一手", "LLM（無ければ定型文）"]] :
   [["①", "登録", "二重登録を除く"], ["②", "抽出", "予兆の言い回し。伝聞は「未確認」"], ["③", "照合", "過去 36 か月をいつ・誰が・何回"], ["④", "判定", "3 種以上の重なり＋直近 12 か月"],
    ["⑤", "検索", "TF-IDF で事例・知恵・制度"], ["⑥", "人軸", "前任者・似た事例の担当者"], ["⑦", "次の一手", "会話のヒントと行内の準備"]]).forEach(([n, t, d], i) => {
    const yy = y + 0.42 + i * 0.36;
    T(s, n, { x: px + 0.2, y: yy, w: 0.35, h: 0.34, fontSize: 13, bold: true, color: C.blue, valign: "middle" });
    T(s, t, { x: px + 0.55, y: yy, w: 1.15, h: 0.34, fontSize: 13, bold: true, valign: "middle" });
    T(s, d, { x: px + 1.7, y: yy, w: pw - 1.8, h: 0.34, fontSize: 11.5, color: C.sub, valign: "middle" });
  });
  arrow(s, px + pw + 0.08, y + h / 2, 0.4);
  const ox = px + pw + 0.6, ow = X0 + CW - ox;
  box(s, ox, y, ow, h, C.greenSoft);
  T(s, [{ text: "出力（担当者に返る反応）", options: { fontSize: 12, bold: true, color: C.green, breakLine: true } },
    { text: "① 判定", options: { fontSize: 14, bold: true, breakLine: true } }, { text: "状態・理由・次の世代につなぎたいもの", options: { fontSize: 11.5, color: C.sub, breakLine: true } },
    { text: "② 次にすること", options: { fontSize: 14, bold: true, breakLine: true } }, { text: "会話のヒント・行内での準備", options: { fontSize: 11.5, color: C.sub, breakLine: true } },
    { text: "③ 相談する", options: { fontSize: 14, bold: true, breakLine: true } }, { text: "相談できる人・行内の窓口", options: { fontSize: 11.5, color: C.sub, breakLine: true } },
    { text: "④ 参考にする", options: { fontSize: 14, bold: true, breakLine: true } }, { text: "社内の支援事例・現場の知恵・制度", options: { fontSize: 11.5, color: C.sub } }],
    { x: ox + 0.2, y: y + 0.1, w: ow - 0.4, h: h - 0.15, lineSpacingMultiple: 1.05 });
  T(s, "入力されたデータはどこへ行くか", { x: X0, y: 5.6, w: 6, h: 0.35, fontSize: 14, bold: true, color: C.amber });
  const dest = S([["日報", "次に誰かが開いたときの材料になる"], ["判定", "支店長の「対話の状況」になる"], ["相談", "相談相手がその企業の記録を読める"], ["すべての操作", "監査ログに残る"]],
    [["日報", "次に開く人の材料に"], ["判定", "支店長の「対話の状況」に"], ["相談", "相談相手も記録を読める"], ["すべての操作", "監査ログに残る"]]);
  const dw = (CW - 0.45) / 4;
  dest.forEach(([k, v], i) => card(s, X0 + i * (dw + 0.15), 6.0, dw, 0.82, k, v, { fill: C.amberSoft, ts: 13, bs: 11.5 }));
  if (SHORT) caption(s, "画面：Streamlit（SFA を模擬）／ 収集：requests＋BeautifulSoup（公的サイト）／ 公開：GitHub＋Streamlit Community Cloud ／ 与信には流さない");
  s.addNotes("入力はいつもの日報1件。登録すると、抽出・照合・判定・検索・人軸・次の一手の順に処理し、4つのまとまりで返します。データの行き先も決めています。日報は次に開く人の材料に、相談すると相手が記録を読めるようになり、すべての操作は監査ログに残ります。与信には流しません。");
}

// ============ デモ ============
{
  const s = pres.addSlide();
  head(s, "実際の利用シーン（デモ）", "カナイ精工を担当する佐々木さんの 1 日で、「知らせる」ときと「黙る」ときを見せる", "システム");
  const sc = [["①", "訪問前に読む", "佐々木（法人担当）／カナイ精工", "前任の林・宮本が見てきた予兆と根拠。次の世代につなぎたい技術と担い手（斎藤工場長）"],
    ["②", "日報 → 予兆が立つ", "雑談で「工場長が来春退職を考えているらしい」", "過去の記録と重なって判定 4。伝聞は「未確認」の印。相談できる人と社内の事例が返る"],
    ["③", "立たない（黙る）", "宮本／太田電装「経営は外から人を招くことも」", "予兆が 1 つでは知らせない。記録として残すだけ"],
    ["④", "くり返し出ている話", "阿部／ヤマト化成「ベトナムの展示会へ出展」", "まだ予兆の定義にない話。本部が予兆に加えるかを判断する"],
    ["⑤", "支店長・本部", "土屋支店長／林（本部）", "点数ではなく支援の段階で見る。受けた相談から記録を読める"]];
  sc.forEach(([n, t, who, see], i) => {
    const y = 2.45 + i * 0.86, hl = i === 1;
    box(s, X0, y, 0.6, 0.76, hl ? C.green : C.blue);
    T(s, n, { x: X0, y, w: 0.6, h: 0.76, fontSize: 18, bold: true, color: C.white, align: "center", valign: "middle" });
    box(s, X0 + 0.7, y, CW - 0.7, 0.76, hl ? C.greenSoft : C.grey);
    T(s, [{ text: t, options: { fontSize: 15, bold: true, breakLine: true } }, { text: who, options: { fontSize: 11, color: C.sub } }], { x: X0 + 0.9, y: y + 0.08, w: 4.3, h: 0.66, lineSpacingMultiple: 1.05 });
    T(s, see, { x: X0 + 5.3, y, w: CW - 5.5, h: 0.76, fontSize: 13, valign: "middle", lineSpacingMultiple: 1.1 });
  });
  caption(s, "サイドバーの「デモの進め方」①〜⑤ で再現できる　https://nonsmoker-code-tsumugu-pilot-sketch-app-x2gh4i.streamlit.app");
  s.addNotes("ライブデモ。①佐々木さんでカナイ精工を開き、前任者の記録と、次の世代につなぎたい技術（斎藤工場長の薄板加工）を見せる。②日報を登録。雑談の一言が過去の記録と重なって判定4に。伝聞は未確認の印。③太田電装では予兆が1つなので黙る。知らせないことも設計。④くり返し出ている話は本部が判断。⑤時間があれば支店長の対話の状況。");
}

// ============ 当初案からの変化 ============
{
  const s = pres.addSlide();
  head(s, "当初案からの変化", "作りながら「本当に現場で使われるか」を確かめ、足すより削る判断を重ねた", "システム");
  table(s, [["", "最初はこう考えた", "こう変えた", "なぜ"],
    ["入力", "日報とは別に「一言」「気づき欄」を書く", "新しい欄をなくし、いつもの業務報告だけを読む", "追加の入力は使われない（現場の声）。予兆のもとは業務報告に書かれる事実だった"],
    ["画面", "独立したアプリを作る", "SFA の中に表示領域を置く", "二重入力を避け、開く場所を増やさない"],
    ["外の情報", "外部の承継事例の記事も集める", "公的な制度・法令だけ。事例は社内から", "自行の経験のほうが次の一手と相談相手につながる"],
    ["見せ方", "「失われる地域価値」、大きな数字", "「次の世代につなぎたいもの」、控えめに", "脅す言い方は対話を止める。点数も付けない"],
    ["効果の証拠", "反応は「対話を始めた／見送り」の 2 つ", "「本部に相談した／案件になった」を足して 4 つ", "攻めの ROI（相談→案件化の率）を測るため"],
    ["判定の当てはめ方", "LLM がベテランの言葉を毎回読んで判断する", "言葉を条件に訳し、知らせるかどうかはプログラムが決める", "毎回同じ答えが出て、根拠を示せる。キーが無くても動く"]],
    { y: 2.45, colW: [1.75, 3.1, 3.2, 3.95], fs: 12, rowH: 0.5 });
  box(s, X0, 6.12, CW, 0.7, C.amberSoft);
  T(s, [{ text: "変えなかったこと：予兆の判断に、現場の知見（ベテランの勘と判断基準）を使う　", options: { fontSize: 14, bold: true, color: C.amber } }, { text: "ツムグの価値の核", options: { fontSize: 13 } }],
    { x: X0 + 0.25, y: 6.12, w: CW - 0.5, h: 0.7, valign: "middle" });
  s.addNotes("いちばん大きな変化は入力です。最初は日報とは別に一言や気づき欄を書いてもらう案でした。でも追加の入力は使われない。合成データを見直すと、予兆のもとは業務報告に書かれる事実でした。だから欄をなくしました。もう一つ、判定の当てはめ方も変えました。企画書ではLLMがベテランの言葉を毎回読んで判断する形でしたが、言葉を条件に訳し、知らせるかどうかはプログラムが決める形にしました。毎回同じ答えが出て根拠を示せるからです。変えなかったのは、予兆の判断に現場の知見を使うこと。経緯は変更記録に残しています。");
}

// ============ 貸し続けられる環境を、自ら作る（別案だけ） ============
if (ALT) {
  const s = pres.addSlide();
  head(s, "貸し続けられる環境を、自ら作る", "事業の継続を意識した営業を、いつもの日報から文化にする", "効果・投資");
  const y = 2.5, h = 2.35, w = 5.4;
  box(s, X0, y, w, h, C.grey);
  T(s, [{ text: "融資するか、しないかを判断するだけの銀行", options: { fontSize: 16, bold: true, color: C.sub, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "業績が悪くなってから気づく", options: { bullet: true, breakLine: true } }, { text: "打てる手が少なく、貸すか引き上げるかの二択になる", options: { bullet: true, breakLine: true } },
    { text: "取引が先細り、関係も浅いまま", options: { bullet: true } }], { x: X0 + 0.25, y: y + 0.2, w: w - 0.5, h: h - 0.3, fontSize: 14, paraSpaceAfter: 8 });
  arrow(s, X0 + w + 0.15, y + h / 2, CW - 2 * w - 0.3);
  const rx = X0 + CW - w;
  box(s, rx, y, w, h, C.blueSoft);
  T(s, [{ text: "支援して、貸し続けられる状態を作る銀行", options: { fontSize: 16, bold: true, color: C.blue, breakLine: true } }, { text: " ", options: { fontSize: 6, breakLine: true } },
    { text: "日報の小さな変化から、早く気づく", options: { bullet: true, breakLine: true } }, { text: "承継・成長・相続の支援で、打てる手を増やす", options: { bullet: true, breakLine: true } },
    { text: "企業が続き、貸出も続く。お金だけではない信頼ができる", options: { bullet: true } }], { x: rx + 0.25, y: y + 0.2, w: w - 0.5, h: h - 0.3, fontSize: 14, paraSpaceAfter: 8 });
  if (SHORT) {
    const cw4 = (CW - 0.45) / 4;
    [["担当者", "経験が浅くても、ベテランの知見を借りて動ける"], ["支店長", "支援の対話の進み具合が段階でわかる"], ["本部", "経営者が誰にも相談していない段階で相談が来る"], ["銀行", "企業が続き貸出が続く。支援は手数料にもなる"]]
      .forEach(([t, d], i) => card(s, X0 + i * (cw4 + 0.15), 5.05, cw4, 1.2, t, d, { fill: C.greenSoft, tc: C.green, ts: 14, bs: 12, bc: C.ink, kicker: "立場ごとの効果", kc: C.green, ks: 9.5 }));
  } else {
  const cw = (CW - 0.4) / 3;
  [["承継に取り組める人が増える", "経験の浅い担当者も、ベテランの知見を借りて動ける"], ["情報が自然に貯まる", "いつもの営業活動が、そのまま企業が続くための記録になる"], ["示唆が育つ", "その日の日報がクエリとなり、貯まった記録から確かな示唆が返る"]]
    .forEach(([t, d], i) => card(s, X0 + i * (cw + 0.2), 5.05, cw, 1.2, t, d, { fill: C.greenSoft, tc: C.green, ts: 14, bs: 12, bc: C.ink }));
  }
  caption(s, "ツムグの情報は融資の判断には使わない。使うのは、企業が続くよう支援するため");
  s.addNotes("銀行は金利で収益を上げる。でも、融資するかしないかを判断するだけでは先細ります。かといって、収益の悪い企業に貸し続けることはできない。だからこそ、支援して貸し続けられる状態を自ら作る。ツムグがあれば、経験の浅い担当者もベテランの知見を借りて動け、いつもの営業活動が企業が続くための記録になり、示唆が育ちます。なお、ツムグの情報は融資の判断には使いません。");
}

// ============ 期待される効果（前段の 3 つ＋立場ごと） ============
{
  const s = pres.addSlide();
  head(s, "導入によって期待される効果", "担当者が先に得をし、その記録から、支店・本部・銀行の効果が生まれる", "効果・投資");
  const top = ALT ? [["承継に取り組める人が増える", "経験の浅い担当者も、ベテランの知見を借りて支援できる"], ["関係の継続性", "担当者が変わっても、顧客との関係の積み重ねが途切れない"], ["支援機会の早期発見", "複数の記録をつなぎ、個人では気づきにくい予兆に気づける"], ["担当者の負担軽減", "着任時から過去の経緯がわかり、築き直す負担が減る"]] : [["関係の継続性", "担当者が変わっても、顧客との関係の積み重ねが途切れない"], ["支援機会の早期発見", "複数の記録をつなぐことで、個人では気づきにくい予兆に気づける"], ["担当者の負担軽減", "着任時から過去の経緯を把握でき、一から関係を築き直す負担が減る"]];
  const tw = (CW - 0.25 * (top.length - 1)) / top.length;
  top.forEach(([t, d], i) => card(s, X0 + i * (tw + 0.25), 2.45, tw, 1.3, t, d, { fill: C.greenSoft, tc: C.green, ts: ALT ? 13 : 18, bs: ALT ? 12 : 13, bc: C.ink }));
  T(s, "立場ごとに見ると", { x: X0, y: 3.95, w: 5, h: 0.35, fontSize: 14, bold: true, color: C.sub });
  const cols = [["担当者", ["訪問前に過去の経緯がわかる", "何を聞けばよいかのヒント", "誰に聞けばよいかがわかる"]], ["支店長", ["支援の対話の進み具合が段階でわかる", "部下への声かけの材料", "異動の引継ぎで途切れない"]],
    ["本部", ["経営者が誰にも相談していない段階で相談が来る", "新しい予兆に気づける", "ベテランの判断を組織の資産に"]], ["銀行", ["守り：乗り換え・廃業を防ぎ取引を維持", "攻め：承継・M&A・付随融資の案件", "眠っていた日報を活かす"]]];
  const cw = (CW - 0.45) / 4;
  cols.forEach(([t, items], i) => {
    const x = X0 + i * (cw + 0.15);
    box(s, x, 4.35, cw, 0.42, C.blue);
    T(s, t, { x, y: 4.35, w: cw, h: 0.42, fontSize: 14, bold: true, color: C.white, align: "center", valign: "middle" });
    box(s, x, 4.82, cw, 1.95, C.grey);
    T(s, items.map((it, j) => ({ text: it, options: { bullet: true, breakLine: j < items.length - 1 } })), { x: x + 0.12, y: 4.92, w: cw - 0.24, h: 1.8, fontSize: 12, paraSpaceAfter: 6, lineSpacingMultiple: 1.05 });
  });
  caption(s, "KPI は記録数ではなく、訪問前の閲覧率・日報の作成時間・早期相談の件数・「対話を始めた」の割合（記録数をノルマにしない）");
  s.addNotes("効果は前段で挙げた3つ、関係の継続性・支援機会の早期発見・担当者の負担軽減です。立場ごとに見ると、担当者が先に得をするから記録が集まり、そこから支店・本部・銀行の効果が生まれます。KPIは記録数にしません。");
}

// ============ ROI ============
{
  const s = pres.addSlide();
  head(s, "守りの ROI と攻めの ROI", V("守り＝取引の乗り換え・消失を防ぐ。攻め＝増えた貸出機会を案件に変える。投資の意味は攻めにある", "企業が続くことが収益になる。守り＝貸出が続く・乗り換えを防ぐ。攻め＝承継・相続などの支援が案件と手数料になる"), "効果・投資");
  s.addChart(pres.charts.BAR, [
    { name: "効果", labels: ["1 年目", "2 年目", "3 年目"], values: [3495, 8155, 11650] },
    { name: "費用", labels: ["1 年目", "2 年目", "3 年目"], values: [3500, 700, 700] },
  ], { x: X0, y: 2.4, w: 6.3, h: 3.15, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60, chartColors: [C.blue, "BBBBBB"],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelFontFace: F, dataLabelColor: C.ink, dataLabelFormatCode: "#,##0",
    showLegend: true, legendPos: "t", legendFontSize: 11, legendFontFace: F, catAxisLabelColor: C.sub, catAxisLabelFontSize: 12, catAxisLabelFontFace: F,
    valAxisLabelColor: C.sub, valAxisLabelFontSize: 10, valAxisLabelFormatCode: "#,##0", valGridLine: { color: "E6E6E6", size: 0.5 }, catGridLine: { style: "none" },
    showTitle: true, title: "年ごとの効果と費用（中位・万円）", titleFontSize: 13, titleFontFace: F, titleColor: C.ink });
  const parts = [["守り 基礎", 3200, "7FA3D9"], ["守り 本丸", 500, "C9A227"], ["攻め 社内", 7950, C.green]];
  const tot = 11650; let xx = X0;
  T(s, "3 年目（定常時）の効果 11,650 万円の内訳", { x: X0, y: 5.65, w: 6.3, h: 0.3, fontSize: 12, bold: true });
  parts.forEach(([k, v, c]) => { const w = 6.3 * v / tot; s.addShape(pres.shapes.RECTANGLE, { x: xx, y: 5.98, w, h: 0.4, fill: { color: c }, line: { color: C.white, width: 1 } });
    if (w > 0.9) T(s, `${k} ${Math.round(v / tot * 100)}%`, { x: xx, y: 5.98, w, h: 0.4, fontSize: 11, bold: true, color: C.white, align: "center", valign: "middle" }); xx += w; });
  T(s, "守り 基礎 3,200（探す時間・引継ぎ）／ 守り 本丸 500（乗り換え・廃業を防ぎ預貸を維持）／ 攻め 社内 7,950（承継・M&A 手数料と付随融資）", { x: X0, y: 6.42, w: 6.3, h: 0.45, fontSize: 10, color: C.sub });
  const rx = X0 + 6.7, rw = CW - 6.7;
  T(s, "前提を変えたときの 3 年累計（費用 4,900 万円）", { x: rx, y: 2.4, w: rw, h: 0.35, fontSize: 13, bold: true });
  [["保守", "4,618 万円", "0.9 倍　3 年では回収しきれない", C.sub, C.grey], ["中位", "2 億 3,300 万円", "4.8 倍　2 年目に回収", C.blue, C.blueSoft], ["楽観", "7 億 4,025 万円", "15.1 倍　1 年目に回収", C.green, C.greenSoft]]
    .forEach(([k, b, r, col, soft], i) => { const y = 2.8 + i * 0.92; box(s, rx, y, rw, 0.82, soft, i === 1 ? { line: col, lw: 1.5 } : {});
      T(s, k, { x: rx + 0.2, y, w: 0.8, h: 0.82, fontSize: 15, bold: true, color: col, valign: "middle" });
      T(s, [{ text: b, options: { fontSize: 18, bold: true, breakLine: true } }, { text: "効果 ÷ 費用 " + r, options: { fontSize: 11.5, color: C.sub } }], { x: rx + 1.05, y: y + 0.08, w: rw - 1.15, h: 0.72 }); });
  T(s, [{ text: "守りの金額は「貸倒の削減」ではなく「取引の維持」で置く。前者は与信目的に見えるため", options: { bullet: true, breakLine: true } },
    { text: "攻めを生むのは ⑤ 事例 ⑥ 人 ⑦ 次の一手の出力。検索結果の出し方が ROI を決める", options: { bullet: true, breakLine: true } },
    { text: "数字はすべて仮置き。率はパイロットの 4 段階フィードバックで実測に置き換える", options: { bullet: true } }],
    { x: rx, y: 5.62, w: rw, h: 1.25, fontSize: 11.5, paraSpaceAfter: 4 });
  s.addNotes("前段の言葉で言うと、守りは取引の乗り換えや消失を防ぐこと、攻めは増えた貸出機会を案件に変えること。中位の前提で3年の効果は約2.3億円、費用の4.8倍、2年目に回収です。ただし守りは約3割で、それだけでは費用と同程度。7割は攻めの効果です。保守的な前提だと3年で回収しきれないので、段階ごとに判断します。");
}

// ============ 承認してほしい投資 ============
{
  const s = pres.addSlide();
  head(s, "承認してほしい投資内容", "第 1 段階として、1 支店・事業承継に絞ったパイロットを、5,000 万円の枠で", "効果・投資");
  const lw = 4.7;
  [["初期開発", "2,800", "内製 2 名 × 12 か月相当＋UI・基盤・権限設計"], ["運用", "700 × 3 年", "クラウド・LLM API・保守改善"], ["合計", "4,900", "予算 5,000 万円の内側（残り 100 は予備）"]].forEach(([k, v, d], i) => {
    const y = 2.45 + i * 0.95, last = i === 2; box(s, X0, y, lw, 0.85, last ? C.blue : C.grey);
    const fc = last ? C.white : C.ink;
    T(s, k, { x: X0 + 0.18, y: y + 0.06, w: 1.4, h: 0.38, fontSize: 13, bold: true, color: fc });
    T(s, v, { x: X0 + 1.6, y: y + 0.02, w: lw - 1.78, h: 0.42, fontSize: 19, bold: true, color: fc, align: "right" });
    T(s, d, { x: X0 + 0.18, y: y + 0.46, w: lw - 0.36, h: 0.36, fontSize: 10.5, color: last ? C.white : C.sub });
  });
  T(s, "お願いすること", { x: X0, y: 5.4, w: lw, h: 0.35, fontSize: 14, bold: true, color: C.red });
  T(s, [{ text: "パイロット（1 支店・事業承継）の承認", options: { bullet: { type: "number" }, breakLine: true } }, { text: "「記録は評価に使わない」方針の明示", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "SFA 外データの連携許可と、協力部署のアサイン", options: { bullet: { type: "number" } } }], { x: X0, y: 5.78, w: lw, h: 1.1, fontSize: 12.5, paraSpaceAfter: 3 });
  const rx = X0 + 5.1, rw = CW - 5.1;
  T(s, "段階ごとに「続ける／直す／やめる」を判断する", { x: rx, y: 2.4, w: rw, h: 0.35, fontSize: 14, bold: true });
  [["0", "準備", "過去日報の取り込みと名寄せ、判定基準を作る", "", C.sub], ["1", "読む", "訪問前に過去の記録が読める", "判断①　開く習慣がついたか", C.blue],
    ["2", "書くのが楽に", "音声入力・下書きで手間が減る", "判断②　作成時間は減ったか", C.blue], ["3", "つながる", "予兆・事例・相談先が返る", "判断③　シグナルは妥当か、早期相談は増えたか", C.green]].forEach(([n, t, d, j, col], i) => {
    const y = 2.82 + i * 0.75;
    s.addShape(pres.shapes.OVAL, { x: rx, y: y + 0.08, w: 0.52, h: 0.52, fill: { color: col }, line: { color: col } });
    T(s, n, { x: rx, y: y + 0.08, w: 0.52, h: 0.52, fontSize: 15, bold: true, color: C.white, align: "center", valign: "middle" });
    T(s, [{ text: t, options: { fontSize: 14, bold: true, breakLine: true } }, { text: d, options: { fontSize: 11, color: C.sub } }], { x: rx + 0.65, y: y + 0.02, w: 3.0, h: 0.7, lineSpacingMultiple: 1.05 });
    if (j) { box(s, rx + 3.7, y + 0.06, rw - 3.7, 0.58, C.amberSoft); T(s, j, { x: rx + 3.85, y: y + 0.06, w: rw - 4.0, h: 0.58, fontSize: 11.5, valign: "middle" }); }
  });
  T(s, "パイロット：1 支店・9〜12 か月。証明できたら全店へ、そして次の広がりへ", { x: rx, y: 5.85, w: rw, h: 0.32, fontSize: 12, color: C.sub });
  const nw = (rw - 0.3) / 3;
  ["成長を支える", "相続・資産承継へ", "地域のつなぎ役へ"].forEach((t, i) => { box(s, rx + i * (nw + 0.15), 6.25, nw, 0.55, i === 2 ? C.greenSoft : C.blueSoft); T(s, t, { x: rx + i * (nw + 0.15), y: 6.25, w: nw, h: 0.55, fontSize: 13, bold: true, align: "center", valign: "middle" }); });
  caption(s, "");
  s.addNotes("お願いするのは第1段階のパイロットです。初期2,800万円と運用700万円×3年で4,900万円。読む、書くのが楽に、つながる、の順に進め、それぞれの終わりで続ける・直す・やめるを判断します。つながるが期待通りでなくても、読む・書くの価値と、判定基準・データ接続の知見は残ります。");
}

// ============ 有用性が証明された後の広がり方 ============
{
  const s = pres.addSlide();
  head(s, "有用性が証明された後の広がり方", "承継の支援を起点に、成長・相続へと支援が深まり、その積み重ねで銀行は地域のつなぎ役になる", "効果・投資");
  const steps = [
    ["起点", "事業承継を支える", "今回のパイロット。承継は、停滞から成長へのきっかけにもなる", "承継コンサル・M&A", C.blue, C.blueSoft],
    ["A　深さ", "成長を支える", "承継後の設備投資・新しい事業・人材。予兆の定義に「成長の兆し」などを足す", "設備投資・運転資金の融資、ビジネスマッチング", C.blue, C.blueSoft],
    ["B　横", "相続・資産承継を支える", "事業の承継は、経営者個人の相続や株式の承継でもある。法人と個人の担当がつながる", "相続・信託・資産運用", C.blue, C.blueSoft],
    ["C　地域", "地域のつなぎ役になる", "継ぐ人がいない企業と受け手、技術と若手、支援機関をつなぐ", "地域の中で取引・雇用・預貸が回る", C.green, C.greenSoft],
  ];
  const gap = 0.32, w = (CW - gap * 3) / 4, y = 2.5, h = 2.75;
  steps.forEach(([k, t, d, rev, col, soft], i) => {
    const x = X0 + i * (w + gap);
    box(s, x, y, w, h, soft, i === 3 ? { line: col, lw: 1.5 } : {});
    T(s, [{ text: k, options: { fontSize: 11, bold: true, color: col, breakLine: true } }, { text: t, options: { fontSize: 15, bold: true, breakLine: true } },
      { text: " ", options: { fontSize: 5, breakLine: true } }, { text: d, options: { fontSize: 11.5, color: C.sub } }],
      { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: 1.85, lineSpacingMultiple: 1.15 });
    s.addShape(pres.shapes.LINE, { x: x + 0.15, y: y + 2.0, w: w - 0.3, h: 0, line: { color: C.line, width: 0.75 } });
    T(s, [{ text: "銀行にとって　", options: { fontSize: 9.5, bold: true, color: col } }, { text: rev, options: { fontSize: 11 } }], { x: x + 0.15, y: y + 2.08, w: w - 0.3, h: 0.6, lineSpacingMultiple: 1.1 });
    if (i < 3) arrow(s, x + w + 0.03, y + h / 2, gap - 0.06);
  });
  T(s, "C は目指して作るものではなく、承継・成長・相続の支援を重ねた結果として、銀行が立つ位置", { x: X0, y: 5.33, w: CW, h: 0.35, fontSize: 13, bold: true, color: C.green });
  const hw = (CW - 0.3) / 2;
  card(s, X0, 5.78, hw, 1.05, "広がるたびに貯まるもの", "地域企業が続いていくための情報、判断の知見、人と企業のつながり。器は同じで、予兆の定義とつなぐ先を足していく", { fill: C.grey, ts: 13.5, bs: 11 });
  card(s, X0 + hw + 0.3, 5.78, hw, 1.05, "先に決めておく条件", "企業同士をつなぐ前のお客さまの同意。与信に使わない約束を地域にも広げる。情報の扱いと説明のルール", { fill: C.amberSoft, ts: 13.5, bs: 11, tc: C.amber });
  caption(s, "他の金融機関への仕組みの提供（外販）は、地域が重ならない相手との共同利用などに限った最後の選択肢（付録 A2）");
  s.addNotes("有用性が証明された後の広がり方です。起点は事業承継の支援。承継は停滞から成長へのきっかけにもなるので、次に成長を支える支援へ深まります。また、事業の承継は経営者個人の相続でもあるので、法人と個人の担当がつながります。こうして支援の幅が広がるたびに収益の機会が増え、その積み重ねで、銀行は自然と地域のつなぎ役になります。継ぐ人がいない企業と受け手をつなげるのは、地域の企業をいちばん多く知る地域の銀行です。ただし企業同士をつなぐ前には、お客さまの同意と、与信に使わない約束を地域にも広げることが条件です。外販は、関係の深さという差を手放さないよう、最後の選択肢にとどめます。");
}

// ============ 結論 ============
{
  const s = pres.addSlide();
  head(s, V("関係の深さを、組織の資産にする", "貸し続けられる環境を、自ら作る"), V("金利のある世界で差になる関係の深さを、いつもの日報から積み上げる。その第一歩として、1 支店・事業承継のパイロットを承認してください", "企業が続けば、雇用と技術が守られ、銀行は貸出を続けられる。その第一歩として、1 支店・事業承継のパイロットを承認してください"), "結論");
  const pts = ALT ? [["承継に取り組める人を増やす", "ベテランの知見を LLM で届ける"], ["手間は増やさない", "いつもの日報だけを読む"], ["与信・評価には使わない", "企業が続くよう支援するために使う"]] : [["新しい入力はつくらない", "いつもの日報だけを読む"], ["現場の知見で判断する", "AI は読む・探す・書くを担う"], ["与信・評価には使わない", "だから記録が集まる"]];
  const cw = (CW - 0.6) / 3;
  pts.forEach(([t, d], i) => card(s, X0 + i * (cw + 0.3), 2.85, cw, 1.4, t, d, { fill: C.blueSoft, ts: 18, bs: 14 }));
  box(s, X0, 4.65, CW, 1.0, C.blueMid);
  T(s, "数字が悪くなってからでは、遅い。一人の担当者の気づきを、地域を支える銀行の力に変える。", { x: X0 + 0.3, y: 4.65, w: CW - 0.6, h: 1.0, fontSize: 19, bold: true, color: C.white, valign: "middle" });
  T(s, "ご質問をお待ちしています", { x: X0, y: 6.0, w: 6, h: 0.4, fontSize: 14, bold: true });
  if (ALT) s.addNotes("貸し続けられる環境を、自ら作る。承継に取り組める人を増やし、手間は増やさず、与信・評価には使わない。企業が続けば、雇用と技術が守られ、銀行は貸出を続けられる。その第一歩としてパイロットの承認をお願いします。");
  else s.addNotes("関係の深さを、組織の資産にする。新しい入力をつくらず、現場の知見で判断し、与信・評価には使わない。その第一歩としてパイロットの承認をお願いします。");
}

// ============ 付録 ============
{
  const s = pres.addSlide();
  head(s, "付録 A1　ROI 試算の前提", "数字はすべて仮置き。公開資料は要再確認、それ以外は本番前に実数へ差し替える", "付録");
  table(s, [["前提", "保守", "中位", "楽観", "出所・状態"],
    ["法人担当者 × 担当先", "200 人 × 50 社", "同左", "同左", "中規模地銀の仮置き"], ["時間単価", "4,000 円/h", "同左", "同左", "人件費＋間接費の仮置き"],
    ["探す時間（1 人・週）× 削減率", "1.0h × 30%", "1.5h × 50%", "2.0h × 60%", "パイロットで実測へ"], ["廃業率 × 回避率", "0.3% × 10%", "0.5% × 20%", "0.7% × 30%", "因果は証明しにくい → 感度で示す"],
    ["1 社の預貸残高 × 収益率", "4,000 万 × 0.8%", "5,000 万 × 1.0%", "6,000 万 × 1.2%", "対象行の取引先属性で差し替え"], ["シグナル→対話→相談→案件化", "2→40→30→15%", "3→50→40→25%", "4→60→50→30%", "4 段階フィードバックで実測"],
    ["手数料 ／ 付随融資", "300 万 ／ 2,000 万", "500 万 ／ 3,000 万", "700 万 ／ 4,000 万", "料率と実績で差し替え"], ["立ち上がり（1・2・3 年目）", "20・60・100%", "30・70・100%", "40・80・100%", "仮置き"],
    ["費用", "初期 2,800 ＋ 運用 700 × 3 年 = 4,900 万円", "", "", "積み上げ直す"]], { y: 2.45, colW: [3.2, 2.1, 2.1, 2.1, 2.5], fs: 11.5, rowH: 0.42 });
  caption(s, "計算式はチームの ROI 試算（参考5）と同じ");
  s.addNotes("数字の出所と、どれを実測に置き換えるかを答えるときに使う。");
}
{
  const s = pres.addSlide();
  head(s, "付録 A2　仕組みの共有（外販）：最後の選択肢", "同じ地域で競う銀行には出さない。関係の深さという差を手放さないため。自行の 3 年試算にも混ぜない", "付録");
  [["TAM", "15.7 億円/年", "国内の地域金融機関すべて（地銀 99・信金 254・信組 145）"], ["SAM", "13.6 億円/年", "法人担当の体制が近い地銀＋信金"], ["SOM", "5,474 万円/年", "5 年後の導入シェア 地銀 5%・信金 3%・信組 1%（仮）"], ["導入コンサル", "1.4 億円", "SOM 到達までの一時収入"]]
    .forEach(([k, v, d], i) => { const cw = (CW - 0.45) / 4, x = X0 + i * (cw + 0.15); box(s, x, 2.45, cw, 1.9, C.grey);
      T(s, [{ text: k, options: { fontSize: 13, bold: true, color: C.blue, breakLine: true } }, { text: v, options: { fontSize: 22, bold: true, breakLine: true } }, { text: d, options: { fontSize: 11, color: C.sub } }], { x: x + 0.2, y: 2.6, w: cw - 0.4, h: 1.7, lineSpacingMultiple: 1.2 }); });
  T(s, [{ text: "出すとしたら：地域が重ならない金融機関との共同利用（運用費を分け合う）、判断基準を現場の言葉で育てる方法と導入の伴走。他行の顧客データは扱わず、判断基準はその行が自分で書く", options: { bullet: true, breakLine: true } },
    { text: "混ぜない理由：外販は体制・営業・契約を伴う別の事業判断。同じ表に足すと自行の投資判断の説得力が薄れる", options: { bullet: true, breakLine: true } },
    { text: "競合：SFA・生成 AI 営業支援と M&A プラットフォームは補完。競合は「行内データで予兆を意味づける」層に限る", options: { bullet: true, breakLine: true } },
    { text: "単価（地銀 600・信金 300・信組 150 万円/年）とシェアは仮置き。機関数は発表前に再確認", options: { bullet: true } }],
    { x: X0, y: 4.6, w: CW, h: 2.2, fontSize: 13, paraSpaceAfter: 8 });
  s.addNotes("外販を聞かれたときに使う。広がり方の本命は地域のつなぎ役で、外販は最後の選択肢。同じ地域で競う銀行に出すと、関係の深さという差を手放すことになる。");
}
{
  const s = pres.addSlide();
  head(s, "付録 A3　セキュリティ・個人情報の考え方", "「誰が何を見られるか」と「目的外に使わせない」を先に設計した", "付録");
  const items = [["見える範囲を役割で絞る", "担当者は自分の担当先（前任者の記録を含む）、支店長は自支店、本部は相談を受けた企業だけ。認証は SFA、認可はツムグ"],
    ["相談で開く", "見られない記録は、見られる人に相談してつなぐ。相談を受けた人は、その企業の記録を読めるようになる"],
    ["すべて記録する", "閲覧・検索・相談を監査ログに残し、目的外の利用を後から確かめられる"], ["与信・評価に使わない", "融資・入出金データとつながない。判定を与信に流さない。点数やランキングを付けない"],
    ["伝え聞きは印を付ける", "「〜らしい」などの伝聞は「未確認」とし、次の訪問で確かめる問いを出す"], ["まだ決めていないこと", "経営者の健康に関する情報の扱い、顧客情報を LLM に渡すときの行内規程、お客さまへの説明のあり方"]];
  const cw = (CW - 0.3) / 2;
  items.forEach(([t, d], i) => card(s, X0 + (i % 2) * (cw + 0.3), 2.45 + Math.floor(i / 2) * 1.47, cw, 1.35, t, d, { fill: i === 5 ? C.amberSoft : C.grey, ts: 15, bs: 12.5 }));
  s.addNotes("セキュリティや個人情報についてのチームとしての考え方。");
}
{
  const s = pres.addSlide();
  head(s, "付録 A4　意思決定レビューの想定問答", "判断を問う質問と、仕組みを問う質問の両方に、チームの誰でも答えられるように", "付録");
  const qa = [["判断", "なぜ「知らせるか」を LLM に任せない？", "毎回同じ答えが出て、なぜ知らせたかを示せないと現場の信頼を失う。判断の中身は現場の知見で、それを条件に訳した"],
    ["判断", "LLM がもっと正確で安くなったら？", "読む・探す・書くは LLM に寄せてよい。「何を予兆とみなすか」は現場の知見として人が持ち続ける"],
    ["判断", "買えばいいのでは？ なぜ内製？", "記録（SFA）と承継先探し（M&A 基盤）は買う。その間の「自行データで予兆を意味づける」部分は外にない"],
    ["判断", "結局、業務効率化では？", "効率化は効果の約 3 割。残り 7 割は気づきを案件に変える部分で、出力（事例・人・次の一手）が違う"],
    ["仕組み", "「SFA に登録する」を押すと何が起きる？", "保存 → 抽出 → 過去 36 か月と照合 → ルールで判定 → 事例・人を検索 → 反応を表示。監査ログにも残る"],
    ["仕組み", "なぜ太田電装では何も出ない？", "予兆が 1 種類だけだから。3 種以上が重なったときだけ知らせる。黙ることも設計"],
    ["仕組み", "現場の知恵はどう集める？", "社内チャットの決まったチャンネルの投稿を夜間に取り込む想定（デモは手で用意した 12 件）"],
    ["仕組み", "与信に使わないと価値が減る？", "逆。与信に使えば現場は書かなくなる。切り離すことが、記録が集まる条件"]];
  const cw = (CW - 0.3) / 2;
  qa.forEach(([k, q, a], i) => { const x = X0 + (i % 2) * (cw + 0.3), y = 2.45 + Math.floor(i / 2) * 1.1; box(s, x, y, cw, 1.0, C.grey);
    box(s, x + 0.12, y + 0.12, 0.75, 0.3, k === "判断" ? C.amberSoft : C.blueSoft);
    T(s, k, { x: x + 0.12, y: y + 0.12, w: 0.75, h: 0.3, fontSize: 10.5, bold: true, color: k === "判断" ? C.amber : C.blue, align: "center", valign: "middle" });
    T(s, q, { x: x + 1.0, y: y + 0.09, w: cw - 1.1, h: 0.36, fontSize: 13, bold: true, valign: "middle" });
    T(s, a, { x: x + 0.15, y: y + 0.48, w: cw - 0.3, h: 0.5, fontSize: 11, color: C.sub, lineSpacingMultiple: 1.05 }); });
  s.addNotes("全員回答制。担当に関係なく、全員が答えられるように練習しておく。");
}

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
