import { $, $$, api, busy, debounce, dropZone, esc, h, library, linkify, pickImages, runJob, store, toast, uploadFiles } from "./api.js";

const CELL = 100;
const KIND_LABEL = { single: "эмодзи", big: "арт", banner: "баннер", tall: "разделитель", collage: "коллаж", heart: "сердечко", text: "текст", spacer: "пусто" };
const DEF_BOARDS = () => [
  { id: "main", name: "main", title: "Мой пак", short_name: "", emoji: "✨", needs_repainting: false, items: [] },
  { id: "hearts", name: "hearts", title: "Мой пак ♡ ч/б", short_name: "", emoji: "🖤", needs_repainting: true, items: [] },
];

const S = {
  boards: store.get("emoji:boards", null) || DEF_BOARDS(),
  cur: 0, sel: null, scale: 0.5, cols: 8, rows: 25, exact: false, exactImg: null, rowsUsed: 0, bg: "#17212b",
};
let uid = Date.now() % 100000;
const board = () => S.boards[S.cur];
const items = () => board().items;
const selItem = () => items().find((i) => i.id === S.sel);
const save = debounce(() => store.set("emoji:boards", S.boards), 300);

export async function initEmoji(root) {
  root.innerHTML = `
  <div class="page-head"><div><h1>✨ Эмодзи-паки</h1>
    <p>Полотно 800×2500 (сетка 8×25 по 100×100). ИИ решает, где удалить фон, что сделать крупным артом, одиночным эмодзи,
    баннером 2–4×1 или разделителем 1×2+. Сердечки-рамочки — в отдельную ч/б плашку. GIF → анимированные эмодзи, экспорт в SVG/TGS.</p></div></div>
  <div class="grid cols-3">
    <div class="stack">
      <div class="card"><h3>🗂 Картинки <span class="hint">клик — добавить</span></h3>
        <div class="drop" id="emDrop" style="padding:12px">⬆ Перетащи картинки / GIF</div>
        <div class="lib-grid" id="emLib" style="margin-top:10px;grid-template-columns:repeat(auto-fill,minmax(64px,1fr));max-height:300px"></div>
      </div>
      <div class="card"><h3>🧠 Авто-композиция</h3>
        <label class="field">Идея пака для ИИ<textarea id="emDesc" rows="3" placeholder="например: нежный бело-розовый пак, крупный арт сверху, баннер с надписью «soft girl», ряды мелких бантиков"></textarea></label>
        <div class="row" style="margin-top:8px">
          <button class="btn primary" id="emAI" data-busy="ИИ раскладывает…">✨ ИИ-раскладка</button>
          <select id="emStyle" style="width:auto"><option value="balanced">гармонично</option><option value="big_first">крупное сверху</option><option value="rows">крупное / ряд мелких</option></select>
          <button class="btn" id="emAuto" data-busy="…">⚡ Авто</button>
        </div>
        <div class="muted small" style="margin-top:6px">Берутся выбранные в библиотеке картинки (или все, что уже на полотне).</div>
      </div>
      <div class="card"><h3>➕ Добавить</h3>
        <div class="row">
          <button class="btn small" id="addText">🔤 Текст-баннер</button>
          <button class="btn small" id="addHeart">🤍 Сердечко</button>
          <button class="btn small" id="addCollage">🧩 Коллаж</button>
          <button class="btn small" id="addSpacer">⬚ Пусто</button>
        </div>
        <div class="sep" style="margin:10px 0"></div>
        <label class="field">Нарисовать нейросетью<input type="text" id="emGenPrompt" placeholder="pink bows and pearls, soft aesthetic"></label>
        <div class="row" style="margin-top:8px">
          <button class="btn small" id="genBanner" data-busy="Рисую…">🎨 Баннер 4×1</button>
          <button class="btn small" id="genArt" data-busy="Рисую…">🖼 Арт 4×4</button>
          <button class="btn small" id="genIcon" data-busy="Рисую…">🔹 Эмодзи</button>
        </div>
      </div>
    </div>

    <div class="stack">
      <div class="card">
        <div class="row between">
          <div class="board-tabs" id="emTabs"></div>
          <div class="row">
            <label class="check small"><input type="checkbox" id="emExact"> точный рендер</label>
            <select id="emZoom" style="width:auto"><option value="0.35">35%</option><option value="0.5" selected>50%</option><option value="0.75">75%</option></select>
            <button class="btn small ghost" id="emRepack" title="Переупаковать незакреплённые">↺</button>
            <button class="btn small ghost danger" id="emClear">🧹</button>
          </div>
        </div>
        <div class="board-wrap"><div class="board" id="emBoard"></div></div>
        <div class="muted small" style="margin-top:6px">Тяни блоки мышкой (привязка к сетке), уголок — размер. Del — удалить. 🔒 — закрепить при авто-раскладке.</div>
      </div>
      <div class="card"><h3>📱 Как в панели эмодзи <span class="hint">8 в ряд</span></h3>
        <div class="row" style="margin-bottom:8px"><button class="btn small" id="emTgPrev" data-busy="Рендер…">Обновить</button>
          <input type="color" id="emBg" value="#17212b" title="Фон чата"></div>
        <div class="tg-emoji-panel" id="emTg"><div class="empty" style="grid-column:1/-1">Нажми «Обновить»</div></div>
      </div>
    </div>

    <div class="stack">
      <div class="card"><h3>🔧 Элемент</h3><div id="emInsp"><div class="empty">Выбери блок на полотне</div></div></div>
      <div class="card"><h3>📦 Пак</h3>
        <label class="field">Название пака<input type="text" id="bTitle"></label>
        <label class="field" style="margin-top:8px">Короткое имя (ссылка, латиница)<input type="text" id="bShort" placeholder="auto"></label>
        <div class="kv" style="margin-top:8px">
          <label class="field">Эмодзи по умолчанию<input type="text" id="bEmoji"></label>
          <label class="check small" style="align-self:end" title="Эмодзи перекрашиваются в цвет текста темы (для ч/б)"><input type="checkbox" id="bRepaint"> адаптивный цвет</label>
        </div>
        <label class="check small" style="margin-top:8px"><input type="checkbox" id="bSkip"> пропускать пустые ряды</label>
        <div class="sep" style="margin:12px 0"></div>
        <div class="row"><label class="check small"><input type="checkbox" id="exSvg"> + SVG</label>
          <label class="check small"><input type="checkbox" id="exTgs"> + TGS (вектор)</label></div>
        <label class="field" style="margin-top:8px">Загрузка в Telegram<select id="exUp">
          <option value="none">Только скачать архив</option><option value="user">От моего аккаунта</option><option value="bot">Через моего бота</option></select></label>
        <div class="row end"><button class="btn" id="exAll" title="Все вкладки-паки">Собрать все</button><button class="btn primary" id="exOne">🚀 Собрать пак</button></div>
      </div>
    </div>
  </div>`;

  const drop = $("#emDrop");
  const add = async (files) => { const r = await uploadFiles(files); r.files.forEach((f) => addImage(f)); drawLib(); };
  drop.onclick = () => { const i = h(`<input type="file" multiple accept="image/*">`); i.onchange = () => add(i.files); i.click(); };
  dropZone(drop, add);

  $("#emAI").onclick = (e) => busy(e.currentTarget, () => layout("ai"));
  $("#emAuto").onclick = (e) => busy(e.currentTarget, () => layout("auto"));
  $("#addText").onclick = () => addItem({ kind: "text", w: 4, h: 1, text: { content: "˖ ࣪ ⊹ soft ⊹ ࣪ ˖", size: 40, color: "#ffffff" }, bg_colors: ["#ff9ac1", "#a18cd1"], emoji: "🎀" });
  $("#addSpacer").onclick = () => addItem({ kind: "spacer", w: 1, h: 1 });
  $("#addHeart").onclick = async () => {
    const r = await pickImages({ multi: true });
    if (!r?.length) return;
    const hb = S.boards.findIndex((b) => b.id === "hearts");
    if (hb >= 0) S.cur = hb;
    r.forEach((name, i) => addItem({ src: name, kind: "heart", w: i % 3 === 2 ? 2 : 1, h: 1, mask: "heart", mask_mode: "inside", bw: true, fit: "cover", emoji: "🖤", outline: 2 }));
  };
  $("#addCollage").onclick = async () => {
    const r = await pickImages({ multi: true });
    if (r?.length) addItem({ kind: "collage", srcs: r, src: r[0], w: Math.min(8, Math.max(2, r.length)), h: 2, gap: 6, radius: 10, emoji: "🖼" });
  };
  $("#genBanner").onclick = (e) => busy(e.currentTarget, () => genImage("banner"));
  $("#genArt").onclick = (e) => busy(e.currentTarget, () => genImage("art"));
  $("#genIcon").onclick = (e) => busy(e.currentTarget, () => genImage("icon"));
  $("#emExact").onchange = (e) => { S.exact = e.target.checked; refreshExact(); };
  $("#emZoom").onchange = (e) => { S.scale = +e.target.value; S.exactImg = null; drawBoard(); refreshExact(); };
  $("#emRepack").onclick = (e) => busy(e.currentTarget, repack);
  $("#emClear").onclick = () => { if (confirm("Очистить текущее полотно?")) { board().items = []; S.sel = null; changed(); } };
  $("#emTgPrev").onclick = (e) => busy(e.currentTarget, tgPreview);
  $("#emBg").oninput = (e) => { S.bg = e.target.value; $("#emTg").style.background = S.bg; };
  $("#exOne").onclick = () => exportPacks([S.cur]);
  $("#exAll").onclick = () => exportPacks(S.boards.map((_, i) => i));
  for (const [id, key, ev] of [["bTitle", "title", "input"], ["bShort", "short_name", "input"], ["bEmoji", "emoji", "input"], ["bRepaint", "needs_repainting", "change"], ["bSkip", "skip_empty_rows", "change"]]) {
    $("#" + id).addEventListener(ev, (e) => { board()[key] = e.target.type === "checkbox" ? e.target.checked : e.target.value; save(); drawTabs(); });
  }
  document.addEventListener("keydown", (e) => {
    if (!$("#page-emoji").classList.contains("active") || ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
    if ((e.key === "Delete" || e.key === "Backspace") && S.sel) { removeItem(S.sel); }
  });
  root.addEventListener("shown", drawLib);
  drawLib();
  drawAll();
}

// ---------------- библиотека ----------------
const libSel = new Set();
async function drawLib() {
  await library.refresh();
  const g = $("#emLib");
  g.innerHTML = library.files.length ? "" : `<div class="empty" style="grid-column:1/-1">пусто</div>`;
  for (const f of library.files) {
    const el = h(`<div class="thumb ${libSel.has(f.name) ? "sel" : ""}" title="клик — на полотно, Shift — выбрать для ИИ"><img loading="lazy" src="${f.url}">${f.animated ? '<span class="badge">GIF</span>' : ""}</div>`);
    el.onclick = (e) => {
      if (e.shiftKey || e.ctrlKey || e.metaKey) { libSel.has(f.name) ? libSel.delete(f.name) : libSel.add(f.name); el.classList.toggle("sel"); }
      else addImage(f);
    };
    g.append(el);
  }
}

function addImage(f) {
  const a = f.w && f.h ? f.w / f.h : 1;
  let w = 1, hh = 1, kind = "single";
  if (a >= 1.8) { kind = "banner"; w = a >= 3.4 ? 4 : a >= 2.5 ? 3 : 2; }
  else if (a <= 0.55) { kind = "tall"; hh = a <= 0.3 ? 4 : a <= 0.42 ? 3 : 2; }
  addItem({ src: f.name, kind, w, h: hh, fit: "cover", emoji: board().emoji || "✨" });
}

// ---------------- элементы ----------------
function occupied(except) {
  const g = Array.from({ length: S.rows }, () => Array(S.cols).fill(false));
  for (const it of items()) {
    if (it.id === except || it.x === undefined) continue;
    for (let y = it.y; y < Math.min(S.rows, it.y + it.h); y++) for (let x = it.x; x < Math.min(S.cols, it.x + it.w); x++) g[y][x] = true;
  }
  return g;
}
function findFree(w, hh, except) {
  const g = occupied(except);
  for (let y = 0; y <= S.rows - hh; y++) for (let x = 0; x <= S.cols - w; x++) {
    let ok = true;
    for (let yy = y; yy < y + hh && ok; yy++) for (let xx = x; xx < x + w; xx++) if (g[yy][xx]) { ok = false; break; }
    if (ok) return { x, y };
  }
  return null;
}

function addItem(it) {
  it.id = "i" + uid++;
  it.w = Math.min(S.cols, it.w || 1);
  it.h = it.h || 1;
  const pos = findFree(it.w, it.h);
  if (!pos) return toast("На полотне нет места такого размера", "err");
  Object.assign(it, pos);
  items().push(it);
  S.sel = it.id;
  changed();
}

function removeItem(id) {
  board().items = items().filter((i) => i.id !== id);
  if (S.sel === id) S.sel = null;
  changed();
}

function changed() {
  save();
  S.exactImg = null;
  drawAll();
  refreshExact();
}

const refreshExact = debounce(async () => {
  if (!S.exact) { drawBoard(); return; }
  try {
    const r = await api("/api/emoji/preview", { items: items(), cols: S.cols, rows: S.rows, scale: S.scale });
    S.exactImg = r.image;
    S.rowsUsed = r.rows_used;
  } catch (e) { toast(e.message, "err"); }
  drawBoard();
}, 600);

function drawAll() { drawTabs(); drawBoard(); drawInspector(); drawBoardForm(); }

function drawTabs() {
  const box = $("#emTabs");
  box.innerHTML = "";
  S.boards.forEach((b, i) => {
    const t = h(`<button class="chip ${i === S.cur ? "on" : ""}">${esc(b.title || b.name)} <span class="muted">${b.items.length}</span></button>`);
    t.onclick = () => { S.cur = i; S.sel = null; S.exactImg = null; drawAll(); refreshExact(); };
    t.ondblclick = () => { if (S.boards.length > 1 && confirm(`Удалить вкладку «${b.title}»?`)) { S.boards.splice(i, 1); S.cur = 0; changed(); } };
    box.append(t);
  });
  const plus = h(`<button class="chip" title="Новый пак">＋</button>`);
  plus.onclick = () => { S.boards.push({ id: "b" + uid++, name: "pack" + S.boards.length, title: "Новый пак", emoji: "✨", items: [] }); S.cur = S.boards.length - 1; changed(); };
  box.append(plus);
}

function drawBoardForm() {
  const b = board();
  $("#bTitle").value = b.title || "";
  $("#bShort").value = b.short_name || "";
  $("#bEmoji").value = b.emoji || "";
  $("#bRepaint").checked = !!b.needs_repainting;
  $("#bSkip").checked = !!b.skip_empty_rows;
}

function bgFor(it) {
  if (it.kind === "text" || (!it.src && !it.srcs)) {
    const c = it.bg_colors || ["#1b1b1f", "#3a2d4f"];
    return `linear-gradient(90deg, ${c.join(",")})`;
  }
  if (it.kind === "spacer") return "none";
  return `url("/uploads/${encodeURIComponent(it.src)}")`;
}

function drawBoard() {
  const el = $("#emBoard");
  const c = CELL * S.scale;
  el.style.width = S.cols * c + "px";
  el.style.height = S.rows * c + "px";
  el.innerHTML = "";
  for (let y = 0; y < S.rows; y++) for (let x = 0; x < S.cols; x++) {
    el.append(h(`<div class="cell" style="left:${x * c}px;top:${y * c}px;width:${c}px;height:${c}px"></div>`));
  }
  if (S.exact && S.exactImg) el.append(h(`<img class="server" src="${S.exactImg}" style="width:${S.cols * c}px">`));
  for (const it of items()) {
    if (it.x === undefined) continue;
    const d = h(`<div class="item ${it.fit === "contain" ? "contain" : ""} ${S.sel === it.id ? "sel" : ""} ${it.mask === "heart" && it.mask_mode !== "erase" && !S.exact ? "heartmask" : ""}"
      style="left:${it.x * c}px;top:${it.y * c}px;width:${it.w * c}px;height:${it.h * c}px;${S.exact && S.exactImg ? "background:transparent" : `background-image:${bgFor(it)}`};${it.bw && !S.exact ? "filter:grayscale(1)" : ""}">
      <span class="lbl">${it.locked ? "🔒" : ""}${KIND_LABEL[it.kind] || it.kind} ${it.w}×${it.h} ${esc(it.emoji || "")}</span>
      ${it.text?.content && !(S.exact && S.exactImg) ? `<div class="txt" style="color:${it.text.color || "#fff"};font-size:${(it.text.size || 40) * S.scale * 0.8}px">${esc(it.text.content)}</div>` : ""}
      <div class="rs"></div></div>`);
    d.addEventListener("pointerdown", (e) => startDrag(e, it, e.target.classList.contains("rs")));
    el.append(d);
  }
}

function startDrag(e, it, resize) {
  e.preventDefault();
  S.sel = it.id;
  const c = CELL * S.scale;
  const sx = e.clientX, sy = e.clientY;
  const o = { x: it.x, y: it.y, w: it.w, h: it.h };
  const node = e.currentTarget;
  $$(".item.sel", $("#emBoard")).forEach((n) => n.classList.remove("sel"));
  node.classList.add("sel");
  const move = (ev) => {
    const dx = Math.round((ev.clientX - sx) / c), dy = Math.round((ev.clientY - sy) / c);
    if (resize) {
      it.w = Math.max(1, Math.min(S.cols - it.x, o.w + dx));
      it.h = Math.max(1, Math.min(S.rows - it.y, o.h + dy));
    } else {
      it.x = Math.max(0, Math.min(S.cols - it.w, o.x + dx));
      it.y = Math.max(0, Math.min(S.rows - it.h, o.y + dy));
    }
    Object.assign(node.style, { left: it.x * c + "px", top: it.y * c + "px", width: it.w * c + "px", height: it.h * c + "px" });
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    const g = occupied(it.id);
    let clash = false;
    for (let y = it.y; y < it.y + it.h; y++) for (let x = it.x; x < it.x + it.w; x++) if (g[y]?.[x]) clash = true;
    if (clash) toast("Блоки перекрываются — верхний закроет нижний");
    if (o.x !== it.x || o.y !== it.y || o.w !== it.w || o.h !== it.h) changed(); else drawInspector();
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

// ---------------- инспектор ----------------
function drawInspector() {
  const box = $("#emInsp");
  const it = selItem();
  if (!it) { box.innerHTML = `<div class="empty">Выбери блок на полотне</div>`; return; }
  const t = it.text || {};
  box.innerHTML = `
    <div class="stack" style="gap:10px">
      <div class="kv3">
        <label class="field">Тип<select data-k="kind">${Object.entries(KIND_LABEL).map(([k, v]) => `<option value="${k}" ${it.kind === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        <label class="field">Ширина<input type="number" min="1" max="8" data-k="w" value="${it.w}"></label>
        <label class="field">Высота<input type="number" min="1" max="25" data-k="h" value="${it.h}"></label>
      </div>
      <div class="kv">
        <label class="field">Вписать<select data-k="fit"><option value="cover" ${it.fit !== "contain" ? "selected" : ""}>заполнить (кроп)</option><option value="contain" ${it.fit === "contain" ? "selected" : ""}>целиком</option><option value="stretch" ${it.fit === "stretch" ? "selected" : ""}>растянуть</option></select></label>
        <label class="field">Эмодзи<input type="text" data-k="emoji" value="${esc(it.emoji || "")}"></label>
      </div>
      <div class="row">
        <label class="check small"><input type="checkbox" data-k="remove_bg" ${it.remove_bg ? "checked" : ""}> убрать фон</label>
        <label class="check small"><input type="checkbox" data-k="bw" ${it.bw ? "checked" : ""}> ч/б</label>
        <label class="check small"><input type="checkbox" data-k="locked" ${it.locked ? "checked" : ""}> 🔒</label>
      </div>
      <div class="kv" ${it.remove_bg ? "" : "hidden"}>
        <label class="field">Чем резать фон<select data-k="bg_engine"><option value="">как в настройках</option><option value="ai" ${it.bg_engine === "ai" ? "selected" : ""}>нейросеть</option><option value="algo" ${it.bg_engine === "algo" ? "selected" : ""}>алгоритм</option></select></label>
        <label class="field">Допуск алгоритма<input type="number" min="5" max="120" data-k="bg_tolerance" value="${it.bg_tolerance || 38}"></label>
      </div>
      <div class="kv">
        <label class="field">Форма<select data-k="mask">${["none", "heart", "circle", "star", "rounded", "arch", "flower", "cloud", "diamond"].map((m) => `<option ${it.mask === m || (!it.mask && m === "none") ? "selected" : ""}>${m}</option>`).join("")}</select></label>
        <label class="field">Режим формы<select data-k="mask_mode"><option value="inside" ${it.mask_mode !== "erase" ? "selected" : ""}>картинка внутри</option><option value="erase" ${it.mask_mode === "erase" ? "selected" : ""}>рамка (стирает центр)</option></select></label>
      </div>
      <div class="kv3">
        <label class="field">Обводка<input type="number" min="0" max="12" data-k="outline" value="${it.outline || 0}"></label>
        <label class="field">Цвет<input type="color" data-k="outline_color" value="${it.outline_color || "#ffffff"}"></label>
        <label class="field">Скругление<input type="number" min="0" max="80" data-k="radius" value="${it.radius || 0}"></label>
      </div>
      <div class="sep"></div>
      <label class="field">Текст на блоке<textarea data-t="content" rows="2">${esc(t.content || "")}</textarea></label>
      <div class="kv3">
        <label class="field">Размер<input type="number" data-t="size" value="${t.size || 40}"></label>
        <label class="field">Цвет<input type="color" data-t="color" value="${t.color || "#ffffff"}"></label>
        <label class="field">Позиция<select data-t="pos">${["center", "top", "bottom"].map((p) => `<option ${t.pos === p ? "selected" : ""}>${p}</option>`).join("")}</select></label>
      </div>
      <div class="kv">
        <label class="field">Контур текста<input type="number" min="0" max="8" data-t="stroke" value="${t.stroke || 0}"></label>
        <label class="field">Шрифт<select data-t="font" id="emFont"><option value="">по умолчанию</option></select></label>
      </div>
      ${it.kind === "text" ? `<div class="kv"><label class="field">Фон 1<input type="color" data-bg="0" value="${(it.bg_colors || ["#ff9ac1"])[0]}"></label><label class="field">Фон 2<input type="color" data-bg="1" value="${(it.bg_colors || ["", "#a18cd1"])[1] || "#a18cd1"}"></label></div>` : ""}
      ${it.kind === "collage" ? `<button class="btn small" id="emColl">Картинки коллажа (${(it.srcs || []).length})</button>` : ""}
      <div class="row">
        <button class="btn small" id="emItemPrev" data-busy="…">👁 Точно</button>
        <button class="btn small" id="emMove">⇄ В другой пак</button>
        <button class="btn small" id="emDup">⧉</button>
        <button class="btn small danger" id="emDel">🗑</button>
      </div>
      <img id="emItemImg" style="max-width:100%;border-radius:10px;display:none;background:repeating-conic-gradient(#232030 0 25%,#1a1824 0 50%) 0 0/16px 16px">
    </div>`;
  const upd = debounce(() => changed(), 250);
  $$("[data-k]", box).forEach((inp) => inp.addEventListener(inp.type === "checkbox" || inp.tagName === "SELECT" ? "change" : "input", () => {
    const k = inp.dataset.k;
    let v = inp.type === "checkbox" ? inp.checked : inp.type === "number" ? +inp.value : inp.value;
    if (k === "w") v = Math.max(1, Math.min(S.cols - it.x, v));
    if (k === "h") v = Math.max(1, Math.min(S.rows - it.y, v));
    it[k] = v;
    if (k === "kind" && v === "heart") Object.assign(it, { mask: "heart", bw: true });
    if (k === "remove_bg") $("[data-k=bg_engine]", box).closest(".kv").hidden = !v;
    upd();
  }));
  $$("[data-t]", box).forEach((inp) => inp.addEventListener(inp.tagName === "SELECT" ? "change" : "input", () => {
    it.text = { ...(it.text || {}), [inp.dataset.t]: inp.type === "number" ? +inp.value : inp.value };
    upd();
  }));
  $$("[data-bg]", box).forEach((inp) => inp.addEventListener("input", () => {
    it.bg_colors = it.bg_colors || ["#ff9ac1", "#a18cd1"];
    it.bg_colors[+inp.dataset.bg] = inp.value;
    upd();
  }));
  fillFonts($("#emFont"), t.font);
  $("#emDel").onclick = () => removeItem(it.id);
  $("#emDup").onclick = () => addItem({ ...structuredClone(it), x: undefined, y: undefined });
  $("#emMove").onclick = () => {
    if (S.boards.length < 2) return toast("Есть только один пак");
    const names = S.boards.map((b, i) => `${i + 1}. ${b.title}`).join("\n");
    const n = +prompt(`В какой пак перенести?\n${names}`, S.cur === 0 ? 2 : 1) - 1;
    if (!(n >= 0 && n < S.boards.length) || n === S.cur) return;
    board().items = items().filter((i) => i.id !== it.id);
    S.cur = n;
    const pos = findFree(it.w, it.h);
    if (!pos) return toast("В том паке нет места", "err");
    Object.assign(it, pos);
    items().push(it);
    changed();
  };
  const coll = $("#emColl");
  if (coll) coll.onclick = async () => { const r = await pickImages({ multi: true, selected: it.srcs || [] }); if (r?.length) { it.srcs = r; it.src = r[0]; changed(); } };
  $("#emItemPrev").onclick = (e) => busy(e.currentTarget, async () => {
    const r = await api("/api/emoji/render_item", { item: it });
    const img = $("#emItemImg");
    img.src = r.image;
    img.style.display = "block";
  });
}

let fontsCache = null;
async function fillFonts(sel, cur) {
  if (!sel) return;
  fontsCache = fontsCache || (await api("/api/fonts")).fonts;
  for (const f of fontsCache) sel.append(h(`<option value="${esc(f.name)}" ${f.name === cur ? "selected" : ""}>${esc(f.name)}</option>`));
}

// ---------------- раскладка ----------------
async function layout(mode) {
  let files = [...libSel];
  if (!files.length) files = [...new Set(items().filter((i) => i.src && i.kind !== "collage").map((i) => i.src))];
  if (!files.length) return toast("Выбери картинки в библиотеке (Shift+клик) или добавь их на полотно", "err");
  const r = await api("/api/emoji/layout", { files, mode, style: $("#emStyle").value, description: $("#emDesc").value, cols: S.cols, rows: S.rows });
  const main = r.items.filter((i) => i.pack !== "hearts");
  const hearts = r.items.filter((i) => i.pack === "hearts");
  main.forEach((i) => (i.id = "i" + uid++));
  board().items = main;
  if (hearts.length) {
    let hb = S.boards.find((b) => b.id === "hearts");
    if (!hb) { hb = { id: "hearts", name: "hearts", title: board().title + " ♡", emoji: "🖤", needs_repainting: true, items: [] }; S.boards.push(hb); }
    hearts.forEach((i) => { i.id = "i" + uid++; delete i.x; delete i.y; });
    const cur = S.cur;
    S.cur = S.boards.indexOf(hb);
    hearts.forEach((i) => { const p = findFree(i.w, i.h); if (p) { Object.assign(i, p); hb.items.push(i); } });
    S.cur = cur;
    toast(`Сердечки (${hearts.length}) отправлены в отдельный пак`);
  }
  const over = main.filter((i) => i.overflow).length;
  if (over) toast(`${over} элемент(ов) не поместились на полотно`, "err");
  libSel.clear();
  drawLib();
  changed();
}

async function repack() {
  const r = await api("/api/emoji/pack", { items: items().map((i) => (i.locked ? i : { ...i, x: undefined, y: undefined })), cols: S.cols, rows: S.rows });
  board().items = r.items;
  changed();
}

async function genImage(kind) {
  const prompt = $("#emGenPrompt").value.trim();
  if (!prompt) return toast("Опиши, что нарисовать", "err");
  if (kind === "banner") {
    const r = await api("/api/emoji/banner", { prompt, w: 4, h: 1, text: "" });
    addItem({ src: r.file.name, kind: "banner", w: 4, h: 1, fit: "cover", emoji: board().emoji, radius: 14 });
  } else {
    const size = kind === "art" ? 1024 : 512;
    const r = await api("/api/emoji/aiimage", { prompt: prompt + (kind === "icon" ? ", single cute icon, centered, plain white background" : ", aesthetic art"), width: size, height: size });
    addItem(kind === "art" ? { src: r.file.name, kind: "big", w: 4, h: 4, fit: "cover", emoji: board().emoji }
      : { src: r.file.name, kind: "single", w: 1, h: 1, fit: "contain", remove_bg: true, emoji: board().emoji });
  }
  drawLib();
}

async function tgPreview() {
  const r = await api("/api/emoji/preview", { items: items(), cols: S.cols, rows: S.rows, scale: 0.5 });
  const box = $("#emTg");
  box.style.background = S.bg;
  box.innerHTML = "";
  const R = r.rows_used;
  for (let y = 0; y < R; y++) for (let x = 0; x < S.cols; x++) {
    const px = S.cols > 1 ? (x / (S.cols - 1)) * 100 : 0, py = R > 1 ? (y / (R - 1)) * 100 : 0;
    box.append(h(`<div style="aspect-ratio:1;background:url(${r.image}) ${px}% ${py}% / ${S.cols * 100}% ${R * 100}% no-repeat;border-radius:4px"></div>`));
  }
}

async function exportPacks(idx) {
  const boards = idx.map((i) => S.boards[i]).filter((b) => b.items.length);
  if (!boards.length) return toast("Полотно пустое", "err");
  const upload = $("#exUp").value;
  await busy($("#exOne"), async () => {
    const { job } = await api("/api/emoji/export", { boards, svg: $("#exSvg").checked, tgs: $("#exTgs").checked, upload });
    await runJob(job, "Сборка эмодзи-пака", (r) => r.packs.map((p) => `
      <div class="card" style="padding:12px"><b>${esc(p.title)}</b> · ${p.count} эмодзи
        <div class="links" style="margin:8px 0">${linkify(p.zip, "📦 Архив")}${linkify(p.canvas, "🖼 Полотно")}${p.link ? linkify(p.link, "✨ Открыть пак в Telegram") : ""}</div>
        <div class="tg-emoji-panel" style="background:${S.bg}">${p.tiles.slice(0, 64).map((t) => `<img src="${t.url}" title="${esc(t.emoji)}">`).join("")}</div>
      </div>`).join(""));
  });
}
