import { $, $$, api, busy, esc, h, store, toast } from "./api.js";
import { DIVIDERS, EMOJI_KITS, FILLERS, FRAMES, KAOMOJI, MARKERS, SPRINKLE_SETS, SYMBOLS, TEMPLATES } from "./decor.js";

const S = {
  fonts: {}, width: store.get("text:width", 32), align: "left", filler: "⠀", autowrap: true,
  emojiWide: true, cjkWide: false, breakLong: true, theme: "dark", undo: [], favs: store.get("text:favs", []),
  tab: "symbols", cat: "sparkle",
};
const seg = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : null;
const graphemes = (s) => (seg ? [...seg.segment(s)].map((x) => x.segment) : [...s]);

// ---------------- ширина и перенос ----------------
function isWide(cp) {
  return (cp >= 0x1100 && cp <= 0x115f) || (cp >= 0x2e80 && cp <= 0xa4cf) || (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) || (cp >= 0xfe30 && cp <= 0xfe4f) || (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0xffe0 && cp <= 0xffe6) || (cp >= 0x13000 && cp <= 0x1342f) || (cp >= 0x20000 && cp <= 0x3fffd);
}
function gWidth(g) {
  if (/^[\p{M}​-‍⁠﻿︎️]+$/u.test(g)) return 0;
  if (S.emojiWide && /\p{Extended_Pictographic}/u.test(g) && !/^[☀-➿]︎?$/u.test(g)) return 2;
  if (S.cjkWide && isWide(g.codePointAt(0))) return 2;
  return 1;
}
export const strWidth = (s) => graphemes(s).reduce((a, g) => a + gWidth(g), 0);

function alignLine(line, width) {
  if (S.align === "left") return line;
  const free = width - strWidth(line);
  if (free <= 0) return line;
  const fw = Math.max(1, strWidth(S.filler));
  const pad = S.align === "center" ? Math.floor(free / 2 / fw) : Math.floor(free / fw);
  return S.filler.repeat(pad) + line;
}

function wrapLine(line, width) {
  if (!line.trim() || strWidth(line) <= width) return [line];
  const out = [];
  let cur = "", w = 0;
  const lead = line.match(/^\s*/)[0];
  for (const tok of line.slice(lead.length).split(/(\s+)/)) {
    if (!tok) continue;
    const tw = strWidth(tok);
    if (/^\s+$/.test(tok)) { if (cur) { cur += tok; w += tw; } continue; }
    if (w + tw <= width) { cur += tok; w += tw; continue; }
    if (cur.trim()) { out.push(cur.trimEnd()); cur = ""; w = 0; }
    if (tw > width && S.breakLong) {
      for (const g of graphemes(tok)) {
        const gw = gWidth(g);
        if (w + gw > width && cur) { out.push(cur); cur = ""; w = 0; }
        cur += g; w += gw;
      }
    } else { cur = tok; w = tw; }
  }
  if (cur.trim()) out.push(cur.trimEnd());
  out[0] = lead + out[0];
  return out;
}

export function wrapText(text, width = S.width) {
  return text.split("\n").flatMap((l) => wrapLine(l, width)).map((l) => alignLine(l, width)).join("\n");
}

// ---------------- шрифты ----------------
function applyFont(text, key) {
  const m = S.fonts[key]?.map || {};
  const hasUpper = Object.keys(m).some((k) => k !== k.toLowerCase());
  return graphemes(text).map((c) => m[c] ?? (hasUpper ? undefined : m[c.toLowerCase()]) ?? c).join("");
}
const COMB = { "̶ зачерк": "̶", "̲ подчерк": "̲", "̸ слэш": "̸", "̅ надчерк": "̅", "̤ точки": "̤", "̰ волна": "̰" };

// ---------------- сборка поста по стилю (для режима «ИИ пишет смысл») ----------------
const STYLE_PRESETS = {
  soft: { font: "sans_bold", head: (t) => `˖ ࣪ ⊹ ${t} ⊹ ࣪ ˖`, marker: "⊹", div: "୨୧・┈・♡・┈・୨୧", tag: "𓂃", end: "૮₍ ˶ᵔ ᵕ ᵔ˶ ₎ა" },
  dark: { font: "fraktur", head: (t) => `⛓ ✶ ${t} ✶ ⛓`, marker: "†", div: "─ׂ┄꯭──ׂ┄꯭──┄꯭ׂ──ׂ┄", tag: "⸸", end: "🕷️ ⋆ ˚" },
  minimal: { font: "sans", head: (t) => `_ _\n⠀⠀${t}`, marker: "◦", div: "┈┈┈┈┈┈┈┈┈┈┈┈", tag: "⌗", end: "⠀⠀⠀⠀ ⸝⸝" },
  kpop: { font: "double", head: (t) => `𓏲 ๋࣭ ${t} ⋆ ࣪.`, marker: "✦", div: "₊˚ ‿︵‿୨୧ · · ♡ · · ୨୧‿︵‿ ˚₊", tag: "⌗", end: "₍ᐢ..ᐢ₎ ♡" },
  cottage: { font: "script", head: (t) => `🧺 𓂃 ${t} 𓂃 🌷`, marker: "𓏲", div: "• ─────── ✾ ─────── •", tag: "✿", end: "🍯 ✦ 🐝" },
  sparkle: { font: "sans_bold", head: (t) => `⊹ ۪ 𖥔 ˑ ִ ${t} ִ ˑ 𖥔 ۪ ⊹`, marker: "𖥔", div: "⋆˟̫₊⋆˟̫₊⋆˟̫₊⋆˟̫₊⋆˟̫₊", tag: "⋆", end: "˖ ࣪ ‹ 𖥔 ࣪ ˖ ぅ" },
  y2k: { font: "mono", head: (t) => `ଘ( ˊ♡ˋ )ଓ ${t} 🎀̸`, marker: "♡︎⃚", div: "⏔⏔⏔ ꒰ ᧔ෆ᧓ ꒱ ⏔⏔⏔", tag: "⑇", end: "💿 ✩ 🦋" },
  frame: { font: "sans_bold", head: (t) => `╭─► ೃ♡ ${t}`, marker: "│", div: "╰───────────────", tag: "⌗", end: "" },
};

function composePost(d, style) {
  const P = STYLE_PRESETS[style] || STYLE_PRESETS.soft;
  const emo = (d.emojis || []).filter(Boolean);
  const out = [P.head(applyFont(String(d.title || "").toLowerCase(), P.font)), fitDivider(P.div)];
  if (d.intro) out.push(d.intro, "");
  (d.points || []).forEach((p, i) => out.push(`${P.marker} ${p}${emo[i] ? " " + emo[i] : ""}`));
  out.push(fitDivider(P.div));
  if (d.outro) out.push(d.outro);
  const tags = (d.tags || []).map((t) => "#" + String(t).replace(/^#/, "").replace(/\s+/g, "_")).join(" ");
  if (tags) out.push(`${P.tag} ${tags}`);
  if (P.end) out.push(P.end);
  return out.join("\n");
}

// ---------------- инициализация ----------------
export async function initText(root) {
  S.fonts = (await api("/api/charmaps")).fonts;
  root.innerHTML = `
  <div class="page-head"><div><h1>✍️ Тексты постов</h1>
    <p>Эстетичное оформление постов для Telegram: ширина строки с авто-переносом, выравнивание, «шрифты» Unicode,
    огромная библиотека символов, разделители, рамки, шаблоны и нейросеть, которая оформит текст в выбранном стиле.</p></div></div>
  <div class="grid cols-side-r">
    <div class="stack">
      <div class="card">
        <div class="row" style="margin-bottom:10px">
          <div class="slider-row" style="grid-template-columns:110px 220px 40px"><span>Ширина строки</span><input type="range" id="txW" min="8" max="80"><output id="txWO"></output></div>
          <div class="seg" id="txAlign"><button data-v="left" class="on" title="Влево">⇤</button><button data-v="center" title="По центру">⇔</button><button data-v="right" title="Вправо">⇥</button></div>
          <select id="txFiller" style="width:auto" title="Чем заполнять отступ (Telegram съедает обычные пробелы в начале)"></select>
        </div>
        <div class="row small" style="margin-bottom:10px">
          <label class="check"><input type="checkbox" id="txAuto" checked> авто-перенос в предпросмотре</label>
          <label class="check"><input type="checkbox" id="txEmo" checked> эмодзи = 2</label>
          <label class="check"><input type="checkbox" id="txCjk"> иероглифы = 2</label>
          <label class="check"><input type="checkbox" id="txBreak" checked> рвать длинные слова</label>
        </div>
        <textarea class="editor" id="txEd" spellcheck="false" placeholder="Пиши или вставляй текст… Выдели фрагмент и нажми шрифт справа ✦"></textarea>
        <div class="mono-ruler" id="txRuler"></div>
        <div class="row" style="margin-top:10px">
          <button class="btn small" id="txApply" title="Записать переносы в сам текст">↩ Применить перенос</button>
          <button class="btn small ghost" id="txUndo">↶ Отмена</button>
          <button class="btn small ghost" id="txUnwrap" title="Склеить строки абзаца">⇥ Склеить</button>
          <button class="btn small ghost" id="txClear">🧹</button>
          <button class="btn small" id="txRules" title="Замены, запрещённые символы, шапка и подпись из раздела «Правила»">📜 Применить правила</button>
          <span class="muted small" id="txStats" style="margin-left:auto"></span>
        </div>
      </div>
      <div class="card"><h3>🔤 Шрифты и стиль <span class="hint">к выделению или ко всему тексту</span></h3>
        <div class="chips" id="txFonts"></div>
        <div class="chips" id="txMarks" style="margin-top:8px"></div>
        <div class="row" style="margin-top:8px">
          <button class="btn small" data-op="upper">АБВ</button><button class="btn small" data-op="lower">абв</button>
          <button class="btn small" data-op="title">Абв Где</button><button class="btn small" data-op="spaced">р а з р я д к а</button>
          <button class="btn small" data-op="strip" title="Убрать декор, оставить буквы/цифры">✂ декор</button>
          <select id="txMarker" style="width:auto"></select><button class="btn small" data-op="marker">маркер к строкам</button>
          <button class="btn small" data-op="number">𝟭. нумерация</button>
        </div>
      </div>
      <div class="card"><h3>📱 Как в Telegram</h3>
        <div class="row" style="margin-bottom:10px"><div class="seg" id="txTheme"><button data-v="dark" class="on">тёмная</button><button data-v="light">светлая</button></div>
          <label class="check small"><input type="checkbox" id="txQuote"> в цитате</label>
          <label class="check small"><input type="checkbox" id="txBold1"> первая строка жирным</label></div>
        <div class="prev-wrap" id="txPrevWrap"><div class="tg-bubble-prev" id="txPrev"></div></div>
        <div class="row" style="margin-top:12px">
          <button class="btn primary" id="txCopy">📋 Копировать текст</button>
          <button class="btn" id="txCopyRich" title="Telegram Desktop/Web вставят с форматированием">📋 С форматированием</button>
          <button class="btn ghost" id="txCopyHtml" title="parse_mode=HTML для ботов">&lt;/&gt; HTML</button>
          <button class="btn ghost" id="txSave">☆ В заметки</button>
        </div>
      </div>
    </div>
    <div class="stack">
      <div class="card">
        <div class="tabs" id="txTabs">
          <button data-t="symbols" class="on">✦ Символы</button><button data-t="favs">★</button><button data-t="kaomoji">૮₍˶ᵔᵕᵔ˶₎ა</button>
          <button data-t="dividers">┈ Разделители</button><button data-t="frames">꒰ Рамки</button><button data-t="templates">📌 Шаблоны</button>
          <button data-t="emoji">🎀 Эмодзи</button><button data-t="sprinkle">⊹ Россыпь</button><button data-t="notes">🗒</button><button data-t="ai">🧠 ИИ</button>
        </div>
        <div id="txPanel"></div>
      </div>
      <div class="help">Совет: Telegram использует пропорциональный шрифт, поэтому ширина — ориентир по символам.
        Для ровных колонок включай «эмодзи = 2» и выравнивай брайль-пробелом «⠀». ПКМ по символу — в избранное ★.</div>
    </div>
  </div>`;

  const ed = $("#txEd");
  ed.value = store.get("text:draft", "˖ ࣪ ⊹ мой пост ⊹ ࣪ ˖\nЗдесь будет красивый текст, который сам переносится по заданной ширине строки ✦\n୨୧・┈・♡・┈・୨୧");
  $("#txW").value = S.width;
  $("#txWO").textContent = S.width;
  $("#txFiller").innerHTML = Object.entries(FILLERS).map(([k, v]) => `<option value="${v}">${k}</option>`).join("");
  $("#txMarker").innerHTML = MARKERS.map((m) => `<option>${m}</option>`).join("");

  ed.oninput = () => { store.set("text:draft", ed.value); render(); };
  ed.onkeydown = (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "z" && S.undo.length) { e.preventDefault(); undo(); } };
  $("#txW").oninput = (e) => { S.width = +e.target.value; $("#txWO").textContent = S.width; store.set("text:width", S.width); render(); };
  $$("#txAlign button").forEach((b) => (b.onclick = () => { $$("#txAlign button").forEach((x) => x.classList.toggle("on", x === b)); S.align = b.dataset.v; render(); }));
  $("#txFiller").onchange = (e) => { S.filler = e.target.value; render(); };
  for (const [id, key] of [["txAuto", "autowrap"], ["txEmo", "emojiWide"], ["txCjk", "cjkWide"], ["txBreak", "breakLong"]]) {
    $("#" + id).onchange = (e) => { S[key] = e.target.checked; render(); };
  }
  $("#txApply").onclick = () => setText(wrapText(ed.value));
  $("#txUnwrap").onclick = () => setText(ed.value.replace(/([^\n])\n(?=[^\n])/g, "$1 ").replace(/⠀+/g, ""));
  $("#txUndo").onclick = undo;
  $("#txClear").onclick = () => setText("");
  $("#txRules").onclick = (e) => busy(e.currentTarget, async () => {
    const r = await api("/api/rules/apply_text", { text: $("#txEd").value });
    setText(r.text);
  });
  api("/api/rules").then((d) => {
    const w = +d.rules.text.width;
    if (w && !store.get("text:width", 0)) { S.width = w; $("#txW").value = w; $("#txWO").textContent = w; render(); }
  }).catch(() => {});
  $$("#txTheme button").forEach((b) => (b.onclick = () => { $$("#txTheme button").forEach((x) => x.classList.toggle("on", x === b)); S.theme = b.dataset.v; render(); }));
  $("#txQuote").onchange = render;
  $("#txBold1").onchange = render;
  $("#txCopy").onclick = () => copyPlain(output());
  $("#txCopyRich").onclick = copyRich;
  $("#txCopyHtml").onclick = () => copyPlain(toHtml(output()));
  $("#txSave").onclick = () => { const n = store.get("text:notes", []); n.unshift({ t: Date.now(), text: output() }); store.set("text:notes", n.slice(0, 60)); toast("Сохранено в заметки 🗒", "ok"); };

  const fbox = $("#txFonts");
  for (const [k, v] of Object.entries(S.fonts)) {
    const c = h(`<span class="chip" title="${k}">${esc(v.label)}</span>`);
    c.onclick = () => transformSel((t) => applyFont(t, k));
    fbox.append(c);
  }
  const mbox = $("#txMarks");
  for (const [label, ch] of Object.entries(COMB)) {
    const c = h(`<span class="chip">${esc(label)}</span>`);
    c.onclick = () => transformSel((t) => graphemes(t).map((g) => (/\s/.test(g) ? g : g + ch)).join(""));
    mbox.append(c);
  }
  $$("[data-op]", root).forEach((b) => (b.onclick = () => op(b.dataset.op)));
  $$("#txTabs button").forEach((b) => (b.onclick = () => { $$("#txTabs button").forEach((x) => x.classList.toggle("on", x === b)); S.tab = b.dataset.t; drawPanel(); }));
  drawPanel();
  render();
}

// ---------------- редактирование ----------------
function setText(v, keepUndo = true) {
  const ed = $("#txEd");
  if (keepUndo) { S.undo.push(ed.value); if (S.undo.length > 80) S.undo.shift(); }
  ed.value = v;
  store.set("text:draft", v);
  render();
}
function undo() { if (S.undo.length) setText(S.undo.pop(), false); }

function insert(str) {
  const ed = $("#txEd");
  const { selectionStart: a, selectionEnd: b, value } = ed;
  setText(value.slice(0, a) + str + value.slice(b));
  ed.focus();
  ed.selectionStart = ed.selectionEnd = a + str.length;
}

function transformSel(fn) {
  const ed = $("#txEd");
  let { selectionStart: a, selectionEnd: b, value } = ed;
  if (a === b) { a = 0; b = value.length; }
  const mid = fn(value.slice(a, b));
  setText(value.slice(0, a) + mid + value.slice(b));
  ed.focus();
  ed.selectionStart = a;
  ed.selectionEnd = a + mid.length;
}

function op(name) {
  const num = ["𝟭", "𝟮", "𝟯", "𝟰", "𝟱", "𝟲", "𝟳", "𝟴", "𝟵", "𝟭𝟬", "𝟭𝟭", "𝟭𝟮"];
  const ops = {
    upper: (t) => t.toUpperCase(), lower: (t) => t.toLowerCase(),
    title: (t) => t.replace(/(^|\s)(\p{L})/gu, (_, s, c) => s + c.toUpperCase()),
    spaced: (t) => t.split("\n").map((l) => graphemes(l).join(" ")).join("\n"),
    strip: (t) => t.replace(/[^\p{L}\p{N}\s.,!?—–\-:;'"«»()%]/gu, "").replace(/[ \t]+/g, " "),
    marker: (t) => t.split("\n").map((l) => (l.trim() ? `${$("#txMarker").value} ${l}` : l)).join("\n"),
    number: (t) => { let i = 0; return t.split("\n").map((l) => (l.trim() ? `${num[i++] || i}. ${l}` : l)).join("\n"); },
  };
  transformSel(ops[name]);
}

function output() {
  const v = $("#txEd").value;
  return S.autowrap ? wrapText(v) : v;
}

function render() {
  const out = output();
  const lines = out.split("\n");
  const maxW = Math.max(0, ...lines.map(strWidth));
  const prev = $("#txPrev");
  const first = lines[0] || "";
  prev.innerHTML = ($("#txBold1").checked ? `<b>${esc(first)}</b>\n${esc(lines.slice(1).join("\n"))}` : esc(out));
  if ($("#txQuote").checked) prev.innerHTML = `<div style="border-left:3px solid #6ab3f3;padding-left:8px;background:rgba(106,179,243,.1);border-radius:4px">${prev.innerHTML}</div>`;
  prev.classList.toggle("light", S.theme === "light");
  $("#txPrevWrap").classList.toggle("light", S.theme === "light");
  const len = [...out].length;
  $("#txStats").innerHTML = `${len} симв. · ${lines.length} стр. · макс. ширина ${maxW}/${S.width}` +
    (len > 4096 ? ` · <span style="color:var(--bad)">больше 4096 — не влезет в сообщение</span>` : len > 1024 ? " · для подписи к фото лимит 1024" : "");
  $("#txRuler").textContent = "┊".padEnd(S.width - 1, "·") + "┊ " + S.width;
}

// ---------------- копирование ----------------
async function copyPlain(t) {
  try { await navigator.clipboard.writeText(t); toast("Скопировано ✓", "ok"); }
  catch { const ta = h("<textarea></textarea>"); ta.value = t; document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove(); toast("Скопировано ✓", "ok"); }
}
function toHtml(t) {
  const lines = t.split("\n").map(esc);
  if ($("#txBold1").checked && lines.length) lines[0] = `<b>${lines[0]}</b>`;
  let body = lines.join("\n");
  if ($("#txQuote").checked) body = `<blockquote>${body}</blockquote>`;
  return body;
}
async function copyRich() {
  const t = output();
  const html = toHtml(t).replace(/\n/g, "<br>");
  try {
    await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([t], { type: "text/plain" }) })]);
    toast("Скопировано с форматированием ✓ (вставляй в Telegram Desktop / Web)", "ok");
  } catch { copyPlain(t); }
}

// ---------------- панели ----------------
function symBtn(s, wide) {
  const b = h(`<button class="sym ${wide ? "wide" : ""}" title="клик — вставить, ПКМ — в избранное">${esc(s)}</button>`);
  b.onclick = () => insert(s);
  b.oncontextmenu = (e) => {
    e.preventDefault();
    if (!S.favs.includes(s)) { S.favs.unshift(s); store.set("text:favs", S.favs); toast(`★ ${s}`); }
  };
  return b;
}

function listBtn(text, onclick) {
  const b = h(`<button title="${esc(text)}">${esc(text.split("\n")[0])}${text.includes("\n") ? " …" : ""}</button>`);
  b.onclick = onclick || (() => insert(text));
  return b;
}

function drawPanel() {
  const p = $("#txPanel");
  p.innerHTML = "";
  const T = S.tab;
  if (T === "symbols") {
    const cats = h(`<div class="chips" style="margin-bottom:10px"></div>`);
    for (const c of SYMBOLS) {
      const ch = h(`<span class="chip ${c.id === S.cat ? "on" : ""}">${esc(c.name)}</span>`);
      ch.onclick = () => { S.cat = c.id; drawPanel(); };
      cats.append(ch);
    }
    const grid = h(`<div class="sym-grid"></div>`);
    SYMBOLS.find((c) => c.id === S.cat).items.forEach((s) => grid.append(symBtn(s, [...s].length > 2)));
    p.append(cats, grid);
  } else if (T === "favs") {
    const grid = h(`<div class="sym-grid"></div>`);
    S.favs.forEach((s) => {
      const b = symBtn(s, [...s].length > 2);
      b.oncontextmenu = (e) => { e.preventDefault(); S.favs = S.favs.filter((x) => x !== s); store.set("text:favs", S.favs); drawPanel(); };
      grid.append(b);
    });
    const add = h(`<div class="row" style="margin-top:10px"><input type="text" placeholder="свой символ / фраза"><button class="btn small">★ добавить</button></div>`);
    $("button", add).onclick = () => { const v = $("input", add).value; if (v) { S.favs.unshift(v); store.set("text:favs", S.favs); drawPanel(); } };
    p.append(S.favs.length ? grid : h(`<div class="empty">ПКМ по любому символу — добавить сюда</div>`), add);
  } else if (T === "kaomoji") {
    const grid = h(`<div class="sym-grid"></div>`);
    KAOMOJI.forEach((k) => grid.append(symBtn(k, true)));
    p.append(grid);
  } else if (T === "dividers") {
    const list = h(`<div class="lines-list"></div>`);
    DIVIDERS.forEach((d) => list.append(listBtn(d, () => insert("\n" + fitDivider(d) + "\n"))));
    p.append(h(`<div class="muted small" style="margin-bottom:8px">Разделитель подгоняется под ширину строки (${S.width}).</div>`), list);
  } else if (T === "frames") {
    const list = h(`<div class="lines-list"></div>`);
    FRAMES.forEach((f) => list.append(listBtn(f.name, () => transformSel((t) => f.t.replace("{text}", t)))));
    p.append(h(`<div class="muted small" style="margin-bottom:8px">Оборачивает выделенный текст (или весь).</div>`), list);
  } else if (T === "templates") {
    const list = h(`<div class="lines-list"></div>`);
    TEMPLATES.forEach((t) => list.append(listBtn(t.name, () => insert(fillTemplate(t.t)))));
    p.append(list);
  } else if (T === "emoji") {
    for (const [name, kit] of Object.entries(EMOJI_KITS)) {
      const row = h(`<div style="margin-bottom:8px"><div class="muted small">${esc(name)}</div><div class="sym-grid"></div></div>`);
      kit.split(" ").forEach((e) => $(".sym-grid", row).append(symBtn(e)));
      p.append(row);
    }
  } else if (T === "sprinkle") {
    const box = h(`<div class="stack">
      <label class="field">Набор<select id="spSet">${Object.keys(SPRINKLE_SETS).map((k) => `<option>${k}</option>`).join("")}</select></label>
      <div class="slider-row"><span>плотность</span><input type="range" id="spDen" min="0.2" max="1" step="0.05" value="0.6"><output>0.6</output></div>
      <div class="slider-row"><span>строк</span><input type="range" id="spLines" min="1" max="12" value="3"><output>3</output></div>
      <label class="field">Вплести эмодзи<input type="text" id="spEmo" placeholder="🥛 🎀 🩰"></label>
      <div class="row"><button class="btn small" id="spGo">🎲 Сгенерировать</button><button class="btn small primary" id="spIns">Вставить</button></div>
      <pre class="out" id="spOut"></pre></div>`);
    p.append(box);
    $$(".slider-row input", box).forEach((i) => (i.oninput = () => (i.nextElementSibling.textContent = i.value)));
    const gen = () => ($("#spOut").textContent = sprinkle($("#spSet").value, +$("#spDen").value, +$("#spLines").value, $("#spEmo").value));
    $("#spGo").onclick = gen;
    $("#spIns").onclick = () => insert("\n" + $("#spOut").textContent + "\n");
    gen();
  } else if (T === "notes") {
    const notes = store.get("text:notes", []);
    const list = h(`<div class="lines-list"></div>`);
    notes.forEach((n) => list.append(listBtn(n.text, () => setText(n.text))));
    p.append(notes.length ? list : h(`<div class="empty">Сохранённые посты появятся здесь</div>`));
  } else if (T === "ai") {
    drawAI(p);
  }
}

function fitDivider(d) {
  // растягиваем/сжимаем повторяющиеся куски (┈┈┈, ───) под ширину строки
  const runs = [];
  for (const g of graphemes(d)) {
    const last = runs[runs.length - 1];
    if (last && last[0] === g) last[1]++; else runs.push([g, 1]);
  }
  const rep = runs.filter((r) => r[1] >= 2);
  if (!rep.length) return d;
  const join = () => runs.map(([g, n]) => g.repeat(n)).join("");
  let i = 0;
  for (let guard = 0; strWidth(join()) < S.width && guard < 500; guard++) rep[i++ % rep.length][1]++;
  for (let guard = 0; strWidth(join()) > S.width && rep.some((r) => r[1] > 1) && guard < 1000; guard++) {
    const r = rep[i++ % rep.length];
    if (r[1] > 1) r[1]--;
  }
  return join();
}

function fillTemplate(t) {
  const div = DIVIDERS[Math.floor(Math.random() * DIVIDERS.length)];
  return t.replaceAll("{divider}", div).replaceAll("{title}", "ЗАГОЛОВОК").replaceAll("{text}", "текст поста")
    .replaceAll("{tags}", "#тег #aesthetic").replaceAll("{name}", "имя").replaceAll("{age}", "возраст").replaceAll("{prn}", "она/её")
    .replaceAll("{city}", "город").replaceAll("{quote}", "цитата").replaceAll("{author}", "автор").replaceAll("{date}", "дата");
}

function sprinkle(set, density, lines, emoji) {
  const pool = SPRINKLE_SETS[set];
  const emo = emoji.split(/\s+/).filter(Boolean);
  const out = [];
  for (let l = 0; l < lines; l++) {
    let line = "";
    while (strWidth(line) < S.width - 1) {
      const r = Math.random();
      const tok = emo.length && r < 0.08 ? emo[Math.floor(Math.random() * emo.length)] : pool[Math.floor(Math.random() * pool.length)];
      const gap = " ".repeat(Math.max(1, Math.round((1 - density) * 4 * Math.random()) + 1));
      if (strWidth(line + tok + gap) > S.width) break;
      line += tok + gap;
    }
    out.push(line.trimEnd());
  }
  return out.join("\n");
}

function drawAI(p) {
  const st = store.get("text:ai", {});
  const box = h(`<div class="stack">
    <div class="seg" id="aiAct"><button data-v="post" class="on">Пост</button><button data-v="decorate">Оформить мой текст</button>
      <button data-v="nicks">Ники</button><button data-v="bio">Био</button><button data-v="divider">Разделители</button></div>
    <label class="field" id="aiTopicL">Тема / имя / данные<textarea id="aiTopic" rows="3" placeholder="например: анонс нового пака эмодзи с клубникой"></textarea></label>
    <div class="kv">
      <label class="field">Стиль<select id="aiStyle">
        <option value="soft">🎀 нежный / coquette</option><option value="dark">🕷 тёмный</option><option value="minimal">⠀ минимализм</option>
        <option value="kpop">💜 k-pop</option><option value="cottage">🧺 коттеджкор</option><option value="sparkle">⊹ россыпь символов</option>
        <option value="y2k">🍒 y2k</option><option value="frame">╭ рамки</option></select></label>
      <label class="field">Эмодзи-набор<select id="aiKit"><option value="">—</option>${Object.keys(EMOJI_KITS).map((k) => `<option>${k}</option>`).join("")}</select></label>
    </div>
    <label class="field">Символы (по умолчанию — твоё ★ избранное)<input type="text" id="aiSym"></label>
    <label class="field">Ещё пожелания<input type="text" id="aiExtra" placeholder="без хэштегов, больше воздуха, заголовок шрифтом 𝗯𝗼𝗹𝗱"></label>
    <label class="check small" id="aiComposeL"><input type="checkbox" id="aiCompose" checked> ИИ пишет смысл, оформляет программа (надёжно для бесплатных моделей)</label>
    <div class="row"><button class="btn primary" id="aiGo" data-busy="ИИ оформляет…">✨ Создать</button>
      <label class="check small"><input type="checkbox" id="aiReplace" checked> заменить текст в редакторе</label></div>
    <div id="aiRes" class="lines-list"></div></div>`);
  p.append(box);
  let act = st.act || "post";
  const setAct = (v) => {
    act = v;
    $$("#aiAct button").forEach((x) => x.classList.toggle("on", x.dataset.v === v));
    $("#aiTopicL").style.display = v === "decorate" || v === "divider" ? "none" : "";
    $("#aiComposeL").style.display = v === "post" ? "" : "none";
  };
  $$("#aiAct button").forEach((b) => (b.onclick = () => setAct(b.dataset.v)));
  setAct(act);
  $("#aiStyle").value = st.style || "soft";
  $("#aiKit").value = st.kit || "";
  $("#aiSym").value = st.sym ?? S.favs.slice(0, 20).join(" ");
  $("#aiTopic").value = st.topic || "";
  $("#aiGo").onclick = (e) => busy(e.currentTarget, async () => {
    const compose = act === "post" && $("#aiCompose").checked;
    const payload = {
      action: compose ? "post_content" : act, topic: $("#aiTopic").value, text: $("#txEd").value, style: $("#aiStyle").value, width: S.width,
      symbols: $("#aiSym").value, emojis: EMOJI_KITS[$("#aiKit").value] || "", extra: $("#aiExtra").value,
    };
    store.set("text:ai", { act, style: payload.style, kit: $("#aiKit").value, sym: payload.symbols, topic: payload.topic });
    const r = await api("/api/text/ai", payload);
    const res = $("#aiRes");
    res.innerHTML = "";
    if (compose) {
      const txt = (await api("/api/rules/apply_text", { text: composePost(r.result, payload.style) })).text;
      if ($("#aiReplace").checked) setText(txt); else insert("\n" + txt + "\n");
    } else if (Array.isArray(r.result)) {
      r.result.forEach((x) => res.append(listBtn(x)));
      toast("Кликни вариант, чтобы вставить");
    } else {
      const txt = r.result.trim();
      if ($("#aiReplace").checked) setText(txt); else insert("\n" + txt + "\n");
    }
  });
}
