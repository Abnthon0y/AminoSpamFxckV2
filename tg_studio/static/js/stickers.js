import { $, $$, api, busy, debounce, esc, h, linkify, pickImages, runJob, store, toast, uploadFiles } from "./api.js";

const S = { files: [], emojis: {}, opts: store.get("stickers:opts", null), meta: null };
const DEF = {
  remove_bg: false, fit: "smart", autocorrect: true, autocorrect_strength: 0.8, harmonize: true, harmonize_strength: 0.35,
  lut: "none", lut_strength: 1, brightness: 1, contrast: 1, saturation: 1, warmth: 0,
  frame: "rounded", outline_w: 14, outline_color: "#ffffff", padding: 8, bg_color: "",
};

export async function initStickers(root) {
  S.meta = await api("/api/stickers/meta");
  S.opts = { ...DEF, ...(S.opts || {}) };
  root.innerHTML = `
  <div class="page-head"><div><h1>🖼️ Авто-стикеры</h1>
    <p>Фото → квадрат 1:1 512×512 с умным кадрированием, автокоррекция цвета и единый стиль всего пака,
    LUT-фильтры (.cube и HALD-картинки), обводка, рамки и загрузка пака в Telegram.</p></div></div>
  <div class="grid cols-side">
    <div class="stack">
      <div class="card"><h3>📷 Фото</h3>
        <div class="row"><button class="btn" id="stPick">Выбрать из библиотеки</button>
          <label class="btn ghost">⬆ Загрузить<input type="file" id="stUp" multiple accept="image/*" hidden></label></div>
        <div class="muted small" style="margin-top:6px" id="stCount">0 фото</div>
      </div>
      <div class="card"><h3>🎨 Цвет и фильтр</h3>
        <label class="check"><input type="checkbox" data-o="autocorrect"> автокоррекция (баланс белого, уровни)</label>
        <div class="slider-row"><span>сила</span><input type="range" data-o="autocorrect_strength" min="0" max="1" step="0.05"><output></output></div>
        <label class="check"><input type="checkbox" data-o="harmonize"> единый стиль всего пака</label>
        <div class="slider-row"><span>сила</span><input type="range" data-o="harmonize_strength" min="0" max="1" step="0.05"><output></output></div>
        <label class="field" style="margin-top:8px">LUT-фильтр<select data-o="lut" id="stLut"></select></label>
        <div class="slider-row"><span>сила LUT</span><input type="range" data-o="lut_strength" min="0" max="1" step="0.05"><output></output></div>
        <label class="btn small ghost" style="margin-top:6px">⬆ Свой .cube / HALD.png<input type="file" id="stLutUp" accept=".cube,.png,.jpg" multiple hidden></label>
        <div class="sep" style="margin:10px 0"></div>
        <div class="slider-row"><span>яркость</span><input type="range" data-o="brightness" min="0.5" max="1.5" step="0.02"><output></output></div>
        <div class="slider-row"><span>контраст</span><input type="range" data-o="contrast" min="0.5" max="1.5" step="0.02"><output></output></div>
        <div class="slider-row"><span>насыщенность</span><input type="range" data-o="saturation" min="0" max="2" step="0.02"><output></output></div>
        <div class="slider-row"><span>теплота</span><input type="range" data-o="warmth" min="-1" max="1" step="0.05"><output></output></div>
      </div>
      <div class="card"><h3>✂️ Форма</h3>
        <label class="check"><input type="checkbox" data-o="remove_bg"> вырезать объект (убрать фон)</label>
        <div class="kv" style="margin-top:8px">
          <label class="field">Кадр<select data-o="fit"><option value="smart">умно</option><option value="cover">заполнить 1:1</option><option value="contain">целиком</option></select></label>
          <label class="field">Рамка<select data-o="frame" id="stFrame"></select></label>
        </div>
        <div class="slider-row" style="margin-top:8px"><span>обводка</span><input type="range" data-o="outline_w" min="0" max="30"><output></output></div>
        <div class="slider-row"><span>отступ</span><input type="range" data-o="padding" min="0" max="80"><output></output></div>
        <div class="row" style="margin-top:6px"><label class="field" style="width:auto">Цвет обводки<input type="color" data-o="outline_color"></label></div>
      </div>
    </div>
    <div class="stack">
      <div class="card"><h3>👁 Предпросмотр <span class="hint">эмодзи под каждым стикером — для поиска</span></h3>
        <div class="sticker-grid" id="stGrid"><div class="empty">Выбери фото</div></div></div>
      <div class="card"><h3>📦 Пак</h3>
        <div class="kv3">
          <label class="field">Название<input type="text" id="stTitle" value="Мои стикеры"></label>
          <label class="field">Короткое имя<input type="text" id="stShort" placeholder="auto"></label>
          <label class="field">Эмодзи по умолчанию<input type="text" id="stDefEmoji" value="✨"></label>
        </div>
        <div class="row" style="margin-top:10px">
          <label class="check small"><input type="checkbox" id="stAiEmoji"> ИИ подберёт эмодзи (нужен vision)</label>
          <select id="stUpload" style="width:auto"><option value="none">только архив</option><option value="user">от аккаунта</option><option value="bot">через бота</option></select>
          <button class="btn primary" id="stBuild" style="margin-left:auto">🚀 Собрать пак</button>
        </div>
      </div>
    </div>
  </div>`;

  fillLuts(S.meta.luts);
  $("#stFrame").innerHTML = Object.entries(S.meta.frames).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $$("[data-o]", root).forEach((inp) => {
    const k = inp.dataset.o;
    if (inp.type === "checkbox") inp.checked = !!S.opts[k];
    else inp.value = S.opts[k];
    const out = inp.nextElementSibling;
    if (out?.tagName === "OUTPUT") out.textContent = inp.value;
    inp.addEventListener(inp.type === "checkbox" || inp.tagName === "SELECT" ? "change" : "input", () => {
      S.opts[k] = inp.type === "checkbox" ? inp.checked : inp.type === "range" ? +inp.value : inp.value;
      if (out?.tagName === "OUTPUT") out.textContent = inp.value;
      store.set("stickers:opts", S.opts);
      refresh();
    });
  });
  $("#stPick").onclick = async () => { const r = await pickImages({ multi: true, selected: S.files }); if (r) { S.files = r; draw(); } };
  $("#stUp").onchange = async (e) => { const r = await uploadFiles(e.target.files); S.files.push(...r.files.map((f) => f.name)); draw(); };
  $("#stLutUp").onchange = async (e) => busy(null, async () => {
    const fd = new FormData();
    for (const f of e.target.files) fd.append("files", f);
    const r = await (await fetch("/api/stickers/lut_upload", { method: "POST", body: fd })).json();
    fillLuts(r.luts);
    toast("LUT добавлен ✓", "ok");
  });
  $("#stBuild").onclick = build;
}

function fillLuts(luts) {
  const sel = $("#stLut");
  sel.innerHTML = `<option value="none">без фильтра</option>` + luts.map((l) => `<option value="${esc(l.id)}">${esc(l.name)}</option>`).join("");
  sel.value = S.opts.lut || "none";
}

function draw() {
  $("#stCount").textContent = `${S.files.length} фото`;
  const g = $("#stGrid");
  g.innerHTML = S.files.length ? "" : `<div class="empty">Выбери фото</div>`;
  for (const f of S.files) {
    const card = h(`<div class="sticker-card" data-f="${esc(f)}"><img alt=""><div class="row" style="gap:4px">
      <input type="text" value="${esc(S.emojis[f] || "")}" placeholder="эмодзи" style="flex:1"><button class="icon-btn" title="Убрать">✕</button></div></div>`);
    $("input", card).oninput = (e) => (S.emojis[f] = e.target.value);
    $("button", card).onclick = () => { S.files = S.files.filter((x) => x !== f); draw(); };
    g.append(card);
  }
  refresh();
}

const refresh = debounce(async () => {
  for (const card of $$("#stGrid .sticker-card")) {
    const f = card.dataset.f;
    try {
      const r = await api("/api/stickers/preview", { file: f, opts: S.opts });
      $("img", card).src = r.image;
    } catch (e) { toast(e.message, "err"); break; }
  }
}, 500);

async function build() {
  if (!S.files.length) return toast("Выбери фото", "err");
  await busy($("#stBuild"), async () => {
    const { job } = await api("/api/stickers/build", {
      files: S.files, opts: S.opts, emojis: S.emojis, title: $("#stTitle").value, short_name: $("#stShort").value,
      default_emoji: $("#stDefEmoji").value, ai_emoji: $("#stAiEmoji").checked, upload: $("#stUpload").value,
    });
    await runJob(job, "Стикер-пак", (r) => `
      <div class="links">${linkify(r.zip, "📦 Архив .webp")}${linkify(r.preview, "🖼 Превью")}${r.link ? linkify(r.link, "✨ Открыть пак") : ""}</div>
      <img src="${r.preview}" style="max-width:100%;border-radius:12px">`);
  });
}
