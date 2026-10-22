import { $, $$, api, busy, debounce, esc, h, toast } from "./api.js";

const EXAMPLES = {
  general: ["Пиши по-русски, без англицизмов", "Никакой грубой лексики", "Общий вайб — нежный, пастельный, coquette",
    "Не используй эмодзи 💀 и 🤡", "Отвечай коротко, без пояснений"],
  themes: ["Только пастельные цвета", "Исходящие сообщения — мягкий градиент", "Акцент всегда розовый",
    "Без чисто чёрного фона", "Шапка в цвет фона, без яркой плашки", "Входящие — почти белые"],
  lang: ["Кнопки не длиннее 12 символов", "Обращайся на «ты»", "Добавляй котиковые словечки (мур, мяу)",
    "Не меняй слова Telegram, Premium, Stories", "Без эмодзи в строках", "Сохраняй смысл — язык должен быть понятным"],
  emoji: ["Крупный арт всегда сверху", "Баннеры только 4×1", "После каждого баннера — ряд из 8 мелких эмодзи",
    "Эмодзи только из набора 🎀 🤍 🩰 🥛", "Подписи на баннерах — маленькими буквами", "Фон убирать только у объектов на белом"],
  pixel: ["Только милые персонажи", "Чёрный контур в 1 пиксель", "Не больше 6 цветов", "Большие глаза-бусинки",
    "Объект всегда по центру"],
  stickers: ["Эмодзи подбирай по эмоции лица", "Только 🥺 😭 ❤️ 😊 😡", "Для еды — 🍓 🍰 🥛"],
  text: ["Заголовок всегда шрифтом 𝗯𝗼𝗹𝗱", "Без хэштегов", "Максимум 3 эмодзи на пост", "Абзацы не длиннее 2 строк",
    "Тон — тёплый и дружеский", "Всегда заканчивай вопросом к подписчикам"],
};

const HINTS = {
  general: "Действуют во всех разделах: добавляются к каждому запросу нейросети.",
  themes: "Правила для генерации тем — и алгоритмом, и нейросетью.",
  lang: "Правила для создания языков: замены слов, длина строк, точные значения по ключам.",
  emoji: "Правила для композиции эмодзи-паков (авто- и ИИ-раскладка, баннеры, сердечки).",
  pixel: "Правила для пиксельных GIF: палитра, контур, стиль персонажей.",
  stickers: "Правила для стикер-паков (подбор эмодзи нейросетью и т.п.).",
  text: "Правила для текстов постов: применяются к результатам ИИ и по кнопке «📜 Применить правила» в редакторе.",
};

const S = { data: null, tab: "general", fonts: null };
const save = debounce(async () => {
  try { await api("/api/rules", { rules: S.data.rules }); $("#ruSaved").textContent = "✓ сохранено"; }
  catch (e) { toast(e.message, "err"); }
}, 500);

export async function initRules(root) {
  S.data = await api("/api/rules");
  if (window.__rulesTab) S.tab = window.__rulesTab;
  root.innerHTML = `
  <div class="page-head"><div><h1>📜 Правила</h1>
    <p>Пропиши свои правила для каждого раздела. <b>Правила для нейросети</b> добавляются к каждому её запросу,
    а <b>жёсткие правила</b> программа соблюдает сама — даже без ИИ. Наборы правил можно сохранять и переключать.</p></div>
    <div class="row"><select id="ruPreset" style="width:auto"></select>
      <button class="btn small" id="ruSaveAs">💾 Сохранить как набор</button>
      <button class="btn small ghost danger" id="ruDel" title="Удалить набор">🗑</button>
      <span class="muted small" id="ruSaved"></span></div>
  </div>
  <div class="tabs" id="ruTabs"></div>
  <div class="grid cols-2" id="ruBody"></div>`;
  drawPresets();
  $("#ruPreset").onchange = (e) => busy(null, async () => {
    if (!e.target.value) return;
    S.data = { ...S.data, ...(await api("/api/rules/preset", { action: "load", name: e.target.value })) };
    toast(`Набор «${e.target.value}» включён ✓`, "ok");
    draw();
  });
  $("#ruSaveAs").onclick = (e) => busy(e.currentTarget, async () => {
    const name = prompt("Название набора правил (например: «нежный пак», «тёмный канал»):", S.data.active || "");
    if (!name) return;
    await api("/api/rules", { rules: S.data.rules });
    S.data = { ...S.data, ...(await api("/api/rules/preset", { action: "save", name })) };
    drawPresets();
    toast("Набор сохранён ✓", "ok");
  });
  $("#ruDel").onclick = (e) => busy(e.currentTarget, async () => {
    const name = $("#ruPreset").value;
    if (!name || !confirm(`Удалить набор «${name}»? Текущие правила останутся.`)) return;
    S.data = { ...S.data, ...(await api("/api/rules/preset", { action: "delete", name })) };
    drawPresets();
  });
  root.addEventListener("shown", () => { if (window.__rulesTab) { S.tab = window.__rulesTab; draw(); } });
  draw();
}

function drawPresets() {
  const sel = $("#ruPreset");
  const names = Object.keys(S.data.presets || {});
  sel.innerHTML = `<option value="">— наборы правил (${names.length}) —</option>` +
    names.map((n) => `<option ${n === S.data.active ? "selected" : ""}>${esc(n)}</option>`).join("");
}

function count(sec) {
  const r = S.data.rules[sec] || {};
  return Object.entries(r).filter(([k, v]) => {
    if (typeof v === "string") return v.trim() && !(k === "remove_bg" && v === "auto");
    if (typeof v === "number") return v > 0 && !["banner_max_w", "tall_max_h"].includes(k);
    if (Array.isArray(v)) return v.length;
    return false;
  }).length;
}

function draw() {
  const tabs = $("#ruTabs");
  tabs.innerHTML = "";
  for (const [k, label] of Object.entries(S.data.sections)) {
    const n = count(k);
    const b = h(`<button class="${k === S.tab ? "on" : ""}">${esc(label)}${n ? ` <span class="pill">${n}</span>` : ""}</button>`);
    b.onclick = () => { S.tab = k; window.__rulesTab = k; draw(); };
    tabs.append(b);
  }
  const r = S.data.rules[S.tab];
  const body = $("#ruBody");
  body.innerHTML = `
    <div class="card"><h3>🧠 Правила для нейросети</h3>
      <div class="muted small" style="margin-bottom:8px">${esc(HINTS[S.tab])} Пиши обычным языком, по одному правилу на строку.</div>
      <textarea id="ruText" rows="9" placeholder="${esc(EXAMPLES[S.tab].slice(0, 3).join("\n"))}">${esc(r.text || "")}</textarea>
      <div class="muted small" style="margin:10px 0 6px">Примеры — клик добавит:</div>
      <div class="chips" id="ruEx"></div>
    </div>
    <div class="card"><h3>⚙️ Жёсткие правила <span class="hint">программа соблюдает сама</span></h3><div class="stack" id="ruHard"></div></div>`;
  const ta = $("#ruText");
  ta.oninput = () => { r.text = ta.value; changed(); };
  for (const ex of EXAMPLES[S.tab]) {
    const c = h(`<span class="chip">${esc(ex)}</span>`);
    c.onclick = () => { ta.value = (ta.value.trim() ? ta.value.trim() + "\n" : "") + ex; ta.oninput(); };
    $("#ruEx").append(c);
  }
  HARD[S.tab]($("#ruHard"), r);
}

function changed() { $("#ruSaved").textContent = "…"; save(); }

// ---------- поля ----------
function field(box, r, key, label, { type = "text", ph = "", rows = 0, help = "" } = {}) {
  const el = rows
    ? h(`<label class="field"><span>${label}</span><textarea rows="${rows}" placeholder="${esc(ph)}">${esc(r[key] ?? "")}</textarea>${help ? `<span class="muted small">${help}</span>` : ""}</label>`)
    : h(`<label class="field"><span>${label}</span><input type="${type}" placeholder="${esc(ph)}" value="${esc(r[key] ?? "")}">${help ? `<span class="muted small">${help}</span>` : ""}</label>`);
  const inp = el.querySelector("input,textarea");
  inp.addEventListener("input", () => { r[key] = type === "number" ? +inp.value : inp.value; changed(); });
  box.append(el);
  return inp;
}

function range(box, r, key, label, min, max, step, fmt) {
  const el = h(`<div class="slider-row" style="grid-template-columns:170px 1fr 60px"><span>${label}</span><input type="range" min="${min}" max="${max}" step="${step}" value="${r[key] || 0}"><output>${fmt(r[key] || 0)}</output></div>`);
  const inp = el.querySelector("input");
  inp.oninput = () => { r[key] = +inp.value; el.querySelector("output").textContent = fmt(+inp.value); changed(); };
  box.append(el);
}

function select(box, r, key, label, opts) {
  const el = h(`<label class="field"><span>${label}</span><select>${Object.entries(opts).map(([v, t]) => `<option value="${v}" ${String(r[key] ?? "") === v ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`);
  el.querySelector("select").onchange = (e) => { r[key] = e.target.value; changed(); };
  box.append(el);
}

function check(box, r, key, label) {
  const el = h(`<label class="check"><input type="checkbox" ${r[key] ? "checked" : ""}> ${label}</label>`);
  el.querySelector("input").onchange = (e) => { r[key] = e.target.checked; changed(); };
  box.append(el);
}

const HARD = {
  general(box, r) {
    field(box, r, "ai_lang", "Язык ответов нейросети", { ph: "русский" });
    field(box, r, "banned", "Запрещённые символы / слова (через пробел)", { ph: "💀 🤡 кринж",
      help: "Убираются из текстов и языков, нейросеть их не использует." });
  },
  themes(box, r) {
    select(box, r, "mode", "Режим тем", { "": "любой (как выбрано в разделе)", dark: "только тёмные", light: "только светлые" });
    range(box, r, "contrast_boost", "Строже контраст текста", 0, 60, 5, (v) => (v ? `+${v}%` : "WCAG"));
    const ta = field(box, r, "locked", "Закреплённые цвета (роль=#цвет)", { rows: 4, ph: "accent=#ff8fc4\nout_bubble=#ffd6e8",
      help: "Эти цвета всегда будут в теме: и у алгоритма, и у нейросети. Клик по роли ниже — вставить." });
    const chips = h(`<div class="chips"></div>`);
    for (const role of S.data.roles) {
      const c = h(`<span class="chip" style="font-size:11px">${role}</span>`);
      c.onclick = () => { ta.value = (ta.value.trim() ? ta.value.trim() + "\n" : "") + role + "=#"; ta.focus(); ta.dispatchEvent(new Event("input")); };
      chips.append(c);
    }
    box.append(chips);
    const st = h(`<div><div class="muted small" style="margin:6px 0">Разрешённые стили (пусто = все):</div><div class="chips"></div></div>`);
    r.styles = r.styles || [];
    for (const [k, v] of Object.entries(S.data.styles)) {
      const c = h(`<span class="chip ${r.styles.includes(k) ? "on" : ""}">${esc(v)}</span>`);
      c.onclick = () => { r.styles = r.styles.includes(k) ? r.styles.filter((x) => x !== k) : [...r.styles, k]; c.classList.toggle("on"); changed(); };
      st.querySelector(".chips").append(c);
    }
    box.append(st);
  },
  lang(box, r) {
    field(box, r, "replace", "Замены слов (до преобразования)", { rows: 4, ph: "Чаты => Мурчатики\nНастройки => Настроечки",
      help: "Целые слова, регистр учитывается. Плейсхолдеры не трогаются." });
    field(box, r, "keys", "Точные значения по ключам", { rows: 3, ph: "Settings => ⚙︎ настроечки\nlng_settings_title => ⚙︎ настроечки",
      help: "Ключ строки => готовый текст (ключи видно в предпросмотре и в файлах)." });
    const kv = h(`<div class="kv"></div>`);
    box.append(kv);
    field(kv, r, "prefix", "Приставка ко всем строкам", { ph: "♡ " });
    field(kv, r, "suffix", "Окончание всех строк", { ph: " ♡" });
    range(box, r, "max_growth", "ИИ: строка длиннее не более чем на", 0, 200, 10, (v) => (v ? `${v}%` : "без огр."));
  },
  emoji(box, r) {
    const kv = h(`<div class="kv"></div>`);
    box.append(kv);
    field(kv, r, "default_emoji", "Эмодзи по умолчанию", { ph: "🤍" });
    select(kv, r, "remove_bg", "Удаление фона", { auto: "решает ИИ / алгоритм", always: "всегда у одиночных и артов", never: "никогда" });
    range(box, r, "banner_max_w", "Баннер — макс. ширина", 2, 8, 1, (v) => `${v || 4} ячеек`);
    range(box, r, "tall_max_h", "Разделитель — макс. высота", 2, 8, 1, (v) => `${v || 4} ячеек`);
    check(box, r, "hearts_bw", "Сердечки всегда в ч/б");
    field(box, r, "banner_colors", "Цвета текстовых баннеров по умолчанию", { ph: "#ffc0db #c9b6ff" });
    const fl = h(`<label class="field"><span>Шрифт надписей по умолчанию</span><select><option value="">системный</option></select></label>`);
    const sel = fl.querySelector("select");
    (async () => {
      S.fonts = S.fonts || (await api("/api/fonts")).fonts;
      for (const f of S.fonts) sel.append(h(`<option ${f.name === r.font ? "selected" : ""}>${esc(f.name)}</option>`));
    })();
    sel.onchange = () => { r.font = sel.value; changed(); };
    box.append(fl);
  },
  pixel(box, r) {
    const inp = field(box, r, "palette", "Палитра — рисовать только этими цветами", { rows: 2, ph: "#ffffff #ffc0db #ff6fa5 #2b2540",
      help: "Все пиксели подгоняются к ближайшему цвету палитры." });
    const row = h(`<div class="row"><div class="palette" id="ruPal"></div><input type="color" value="#ff8fc4" title="добавить цвет"><button class="btn small">＋ цвет</button></div>`);
    const drawPal = () => {
      const pal = row.querySelector("#ruPal");
      pal.innerHTML = "";
      for (const c of (r.palette || "").match(/#[0-9a-fA-F]{6}/g) || []) pal.append(h(`<div class="swatch" style="background:${c};width:24px;height:24px;border-radius:7px"></div>`));
    };
    row.querySelector("button").onclick = () => { inp.value = (inp.value.trim() + " " + row.querySelector("input").value).trim(); inp.dispatchEvent(new Event("input")); drawPal(); };
    inp.addEventListener("input", drawPal);
    box.append(row);
    drawPal();
    field(box, r, "outline_color", "Цвет контура", { ph: "#1e1628" });
  },
  stickers(box, r) {
    field(box, r, "default_emoji", "Эмодзи по умолчанию для стикеров", { ph: "✨" });
    box.append(h(`<div class="muted small">Остальные настройки стикеров (LUT, рамка, обводка) запоминаются прямо в разделе «Стикеры».</div>`));
  },
  text(box, r) {
    field(box, r, "replace", "Замены", { rows: 3, ph: "привет => приветик\n!!! => ¡!" });
    field(box, r, "banned", "Запрещённые символы / слова", { ph: "# 💀" });
    field(box, r, "header", "Всегда начинать пост с", { ph: "˖ ࣪ ⊹ ⊹ ࣪ ˖" });
    field(box, r, "signature", "Всегда заканчивать подписью", { ph: "𓂃 @мой_канал ♡" });
    field(box, r, "width", "Ширина строки по умолчанию (0 = не менять)", { type: "number", ph: "30" });
  },
};
