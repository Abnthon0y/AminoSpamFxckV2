import { $, $$, api, busy, color, debounce, dropZone, esc, h, linkify, pickImages, store, toast, uploadFiles } from "./api.js";

const S = {
  wallpaper: null, wallUrl: null, base: [], palette: [], brightness: null,
  adj: { hue: 0, sat: 0, light: 0, contrast: 0 }, mode: "auto",
  variants: [], roles: null, report: [], selRole: null, meta: null, name: "Моя тема",
};

export async function initThemes(root) {
  S.meta = await api("/api/theme/meta");
  root.innerHTML = `
  <div class="page-head">
    <div><h1>🎨 Темы Telegram</h1>
    <p>Загрузи обои — программа вытащит палитру до 15 цветов, а алгоритм или нейросеть соберут уникальные контрастные темы
    с читаемым текстом. Правь в редакторе с живым предпросмотром и создавай темы прямо в аккаунте.</p></div>
  </div>
  <div class="grid cols-3">
    <div class="stack">
      <div class="card">
        <h3>🖼️ Обои</h3>
        <div class="drop" id="thDrop">Перетащи обои сюда или нажми<br><span class="small">JPG / PNG</span></div>
        <div class="row" style="margin-top:10px">
          <button class="btn small" id="thFromLib">Из библиотеки</button>
          <label class="check small"><input type="checkbox" id="thUseWp" checked> обои в теме</label>
        </div>
      </div>
      <div class="card">
        <h3>🎯 Палитра <span class="hint" id="thPalInfo"></span></h3>
        <div class="slider-row"><span>Цветов</span><input type="range" id="thCount" min="2" max="15" value="12"><output id="thCountO">12</output></div>
        <div class="row" style="margin:8px 0 4px"><button class="btn small" id="thExtract" data-busy="Анализ…">Извлечь заново</button>
          <button class="btn small ghost" id="thShuffle" title="Другие кластеры">🎲</button>
          <button class="btn small ghost" id="thAddColor">＋ цвет</button></div>
        <div class="palette big" id="thPalette"></div>
        <div class="sep"></div>
        <div class="stack" style="gap:6px">
          <div class="slider-row"><span>Оттенок</span><input type="range" id="adjHue" min="-180" max="180" value="0"><output>0</output></div>
          <div class="slider-row"><span>Насыщенность</span><input type="range" id="adjSat" min="-100" max="100" value="0"><output>0</output></div>
          <div class="slider-row"><span>Светлота</span><input type="range" id="adjLight" min="-100" max="100" value="0"><output>0</output></div>
          <div class="slider-row"><span>Контраст</span><input type="range" id="adjContrast" min="-100" max="100" value="0"><output>0</output></div>
          <div class="row"><button class="btn small ghost" id="adjReset">Сброс</button><span class="muted small">клик по цвету — изменить, ПКМ — удалить</span></div>
        </div>
      </div>
      <div class="card">
        <h3>⚡ Генерация</h3>
        <div class="seg" id="thMode"><button data-v="auto" class="on">Авто</button><button data-v="dark">Тёмная</button><button data-v="light">Светлая</button></div>
        <div class="row" style="margin-top:10px"><button class="btn" id="thGen" data-busy="Генерирую…">🎛 Варианты алгоритмом</button></div>
        <div class="sep" style="margin:12px 0"></div>
        <label class="field">Пожелания для нейросети
          <textarea id="thDesc" rows="3" placeholder="например: нежная пастельная, пузыри как стекло, акцент вишнёвый, как в Pinterest"></textarea></label>
        <div class="row" style="margin-top:8px"><button class="btn primary" id="thAI" data-busy="ИИ думает…">✨ Уникальные темы ИИ</button>
          <select id="thAICount" style="width:auto"><option>2</option><option selected>3</option><option>4</option></select></div>
      </div>
    </div>

    <div class="stack">
      <div class="card"><h3>💫 Варианты <span class="hint">клик — открыть в редакторе</span></h3><div class="variants" id="thVariants"><div class="empty">Загрузи обои и нажми «Варианты»</div></div></div>
      <div class="card"><h3>📱 Предпросмотр</h3><div class="phones" id="thPhones"></div>
        <div class="row" style="margin-top:12px;justify-content:center" id="thReportSum"></div></div>
    </div>

    <div class="stack">
      <div class="card">
        <h3>🛠 Редактор темы</h3>
        <label class="field">Название<input type="text" id="thName" value="Моя тема"></label>
        <div class="row" style="margin:10px 0">
          <button class="btn small" id="thFix">🪄 Авто-контраст</button>
          <button class="btn small ghost" id="thApplyAdj" title="Применить ползунки палитры ко всей теме">↻ Ползунки → тема</button>
          <button class="btn small ghost" id="thUndo">↶</button>
        </div>
        <div class="muted small" style="margin-bottom:6px">Выбери роль, затем кликни цвет палитры ниже — или используй пипетку.</div>
        <div class="palette" id="thMiniPal" style="margin-bottom:10px"></div>
        <div class="roles" id="thRoles"><div class="empty">Тема ещё не выбрана</div></div>
      </div>
      <div class="card">
        <h3>🚀 Экспорт и публикация</h3>
        <div class="chips" id="thPlatforms">
          <span class="chip on" data-v="cloud" title="Облачная тема по настройкам — работает на всех устройствах">☁️ Облачная (все)</span>
          <span class="chip on" data-v="android">🤖 Android</span>
          <span class="chip on" data-v="tdesktop">💻 Desktop</span>
          <span class="chip" data-v="ios">🍏 iOS-файл</span>
        </div>
        <div class="row" style="margin-top:12px">
          <button class="btn" id="thExport" data-busy="Собираю…">⬇ Скачать файлы</button>
          <button class="btn primary" id="thPublish" data-busy="Создаю в Telegram…">📤 Создать в аккаунте</button>
        </div>
        <div class="job-result" id="thOut"></div>
      </div>
    </div>
  </div>`;

  const drop = $("#thDrop");
  drop.onclick = () => { const i = h(`<input type="file" accept="image/*">`); i.onchange = () => setWall(i.files); i.click(); };
  dropZone(drop, setWall);
  $("#thFromLib").onclick = async () => { const r = await pickImages({ multi: false }); if (r?.length) useWallpaper(r[0]); };
  $("#thCount").oninput = (e) => ($("#thCountO").textContent = e.target.value);
  $("#thExtract").onclick = (e) => busy(e.currentTarget, () => extract(0));
  $("#thShuffle").onclick = (e) => busy(e.currentTarget, () => extract(Math.floor(Math.random() * 1000)));
  $("#thAddColor").onclick = () => { S.base.push({ hex: "#ff8fc4", share: 0.02 }); applyAdj(); };
  for (const [id, key] of [["adjHue", "hue"], ["adjSat", "sat"], ["adjLight", "light"], ["adjContrast", "contrast"]]) {
    $("#" + id).oninput = (e) => {
      e.target.nextElementSibling.textContent = e.target.value;
      S.adj[key] = key === "hue" ? +e.target.value : +e.target.value / 100;
      applyAdj();
      regen();
    };
  }
  $("#adjReset").onclick = () => {
    for (const id of ["adjHue", "adjSat", "adjLight", "adjContrast"]) { $("#" + id).value = 0; $("#" + id).nextElementSibling.textContent = 0; }
    S.adj = { hue: 0, sat: 0, light: 0, contrast: 0 };
    applyAdj(); regen();
  };
  $$("#thMode button").forEach((b) => (b.onclick = () => {
    $$("#thMode button").forEach((x) => x.classList.toggle("on", x === b));
    S.mode = b.dataset.v;
    if (S.palette.length) generate();
  }));
  $("#thGen").onclick = (e) => busy(e.currentTarget, generate);
  $("#thAI").onclick = (e) => busy(e.currentTarget, aiGenerate);
  $("#thName").oninput = (e) => (S.name = e.target.value);
  $("#thFix").onclick = (e) => busy(e.currentTarget, async () => { pushUndo(); const r = await api("/api/theme/fix", { roles: S.roles }); setRoles(r.roles); toast("Контраст исправлен ✓", "ok"); });
  $("#thApplyAdj").onclick = () => {
    if (!S.roles) return;
    pushUndo();
    const r = { ...S.roles };
    for (const k of S.meta.roles) r[k] = color.adjust(r[k], S.adj);
    setRoles(r);
  };
  $("#thUndo").onclick = () => { const u = undo.pop(); if (u) setRoles(u, false); };
  $$("#thPlatforms .chip").forEach((c) => (c.onclick = () => c.classList.toggle("on")));
  $("#thExport").onclick = (e) => busy(e.currentTarget, exportFiles);
  $("#thPublish").onclick = (e) => busy(e.currentTarget, publish);

  const saved = store.get("theme:last");
  if (saved?.roles) { S.name = saved.name || S.name; $("#thName").value = S.name; setRoles(saved.roles, false); }
  renderPhones();
}

const regen = debounce(() => { if (S.palette.length && S.variants.length) generate(); }, 450);
const undo = [];
function pushUndo() { if (S.roles) undo.push({ ...S.roles }); if (undo.length > 40) undo.shift(); }

async function setWall(files) {
  const res = await uploadFiles(files);
  useWallpaper(res.files[0].name);
}

async function useWallpaper(name) {
  S.wallpaper = name;
  S.wallUrl = `/uploads/${encodeURIComponent(name)}`;
  $("#thDrop").innerHTML = `<img src="${S.wallUrl}">`;
  await busy($("#thExtract"), () => extract(0));
  await generate();
}

async function extract(seed) {
  if (!S.wallpaper) return toast("Сначала выбери обои", "err");
  const r = await api("/api/theme/palette", { file: S.wallpaper, count: +$("#thCount").value, seed });
  S.base = r.palette;
  S.brightness = r.brightness;
  $("#thPalInfo").textContent = `${r.palette.length} цв. · яркость ${(r.brightness * 100) | 0}%`;
  applyAdj();
}

function applyAdj() {
  S.palette = S.base.map((p) => ({ ...p, hex: color.adjust(p.hex, S.adj) }));
  drawPalette();
}

function drawPalette() {
  const box = $("#thPalette");
  box.innerHTML = "";
  S.palette.forEach((p, i) => {
    const sw = h(`<div class="swatch" style="background:${p.hex}" title="${p.hex} · ${Math.round(p.share * 100)}%"><span>${p.hex.slice(1)}</span></div>`);
    sw.onclick = () => {
      const inp = h(`<input type="color" value="${S.base[i].hex}">`);
      inp.oninput = () => { S.base[i].hex = inp.value; applyAdj(); };
      inp.onchange = () => regen();
      inp.click();
    };
    sw.oncontextmenu = (e) => { e.preventDefault(); S.base.splice(i, 1); applyAdj(); regen(); };
    box.append(sw);
  });
  drawMiniPal();
}

function drawMiniPal() {
  const box = $("#thMiniPal");
  if (!box) return;
  box.innerHTML = "";
  const cols = [...new Set([...S.palette.map((p) => p.hex), "#ffffff", "#000000"])];
  for (const c of cols) {
    const sw = h(`<div class="swatch" style="background:${c};width:26px;height:26px;border-radius:8px" title="${c}"></div>`);
    sw.onclick = () => { if (!S.selRole) return toast("Сначала выбери роль в списке"); pushUndo(); setRoles({ ...S.roles, [S.selRole]: c }); };
    box.append(sw);
  }
}

async function generate() {
  if (!S.palette.length) return toast("Нет палитры — загрузи обои", "err");
  const r = await api("/api/theme/generate", { palette: S.palette, mode: S.mode, count: 6, brightness: S.brightness });
  S.variants = r.themes;
  drawVariants();
  setRoles(S.variants[0].roles, false);
}

async function aiGenerate() {
  if (!S.palette.length) return toast("Нет палитры — загрузи обои", "err");
  const r = await api("/api/theme/ai", { palette: S.palette, mode: S.mode, description: $("#thDesc").value, count: +$("#thAICount").value });
  S.variants = [...r.themes, ...S.variants].slice(0, 12);
  drawVariants();
  setRoles(r.themes[0].roles);
  if (r.themes[0].roles._meta?.name) { S.name = r.themes[0].roles._meta.name; $("#thName").value = S.name; }
}

function drawVariants() {
  const box = $("#thVariants");
  box.innerHTML = "";
  S.variants.forEach((v, i) => {
    const t = v.roles;
    const bad = v.report.filter((x) => !x.ok).length;
    const el = h(`<div class="variant" style="background:${t.chat_bg}">
      <div class="vname" style="color:${t.text}">${esc(t._meta?.name || t._meta?.style || "вариант")} ${bad ? "⚠" : "✓"}</div>
      <div class="vb" style="background:${t.in_bubble};color:${t.in_text}">Привет! ♡</div>
      <div class="vb" style="background:linear-gradient(160deg,${t.out_bubble},${t.out_bubble2});color:${t.out_text};margin-left:auto">Хай ✦ <span style="color:${t.out_secondary}">12:04</span></div>
      <div style="height:6px;border-radius:4px;background:${t.accent};margin-top:6px"></div></div>`);
    if (S.wallUrl && $("#thUseWp")?.checked) el.style.background = `center/cover url("${S.wallUrl}")`;
    el.onclick = () => { $$(".variant", box).forEach((x) => x.classList.remove("sel")); el.classList.add("sel"); pushUndo(); setRoles(t); };
    box.append(el);
  });
}

function setRoles(roles, save = true) {
  S.roles = { ...roles };
  if (save) store.set("theme:last", { name: S.name, roles: S.roles });
  drawRoles();
  renderPhones();
}

function report() {
  return S.meta.rules.map(([fg, bg, need]) => {
    const r = color.contrast(S.roles[fg], S.roles[bg]);
    return { fg, bg, need, ratio: r, ok: r >= need - 0.01 };
  });
}

function drawRoles() {
  const box = $("#thRoles");
  box.innerHTML = "";
  const rep = report();
  for (const k of S.meta.roles) {
    const mine = rep.filter((r) => r.fg === k);
    const worst = mine.sort((a, b) => a.ratio / a.need - b.ratio / b.need)[0];
    const badge = worst ? `<span class="badge-c ${worst.ok ? "" : "bad"}" title="контраст с ${worst.bg}, нужно ≥ ${worst.need}">${worst.ratio.toFixed(1)}</span>` : "<span></span>";
    const row = h(`<div class="role ${S.selRole === k ? "target" : ""}">
      <input type="color" value="${S.roles[k]}"><div>${esc(S.meta.labels[k])}<br><code>${k}</code></div>
      <input type="text" value="${S.roles[k]}" style="font:11px var(--mono);padding:4px 6px">${badge}</div>`);
    const ci = $("input[type=color]", row);
    const ti = $("input[type=text]", row);
    ci.oninput = () => { S.roles[k] = ci.value; ti.value = ci.value; renderPhones(); };
    ci.onchange = () => { pushUndo(); setRoles(S.roles); };
    ti.onchange = () => { if (/^#[0-9a-f]{6}$/i.test(ti.value)) { pushUndo(); setRoles({ ...S.roles, [k]: ti.value.toLowerCase() }); } };
    row.onclick = (e) => { if (e.target.tagName !== "INPUT") { S.selRole = k; drawRoles(); } };
    box.append(row);
  }
  const bad = rep.filter((r) => !r.ok);
  $("#thReportSum").innerHTML = bad.length
    ? `<span class="badge-c bad">⚠ ${bad.length} пар с низким контрастом</span> <button class="btn small" id="thFix2">исправить</button>`
    : `<span class="badge-c">✓ все тексты читаемы (WCAG)</span>`;
  const f2 = $("#thFix2");
  if (f2) f2.onclick = () => $("#thFix").click();
}

function renderPhones() {
  const box = $("#thPhones");
  if (!box) return;
  const t = S.roles;
  if (!t) { box.innerHTML = `<div class="empty">Здесь появится предпросмотр темы</div>`; return; }
  const vars = S.meta.roles.map((k) => `--t-${k}:${t[k]}`).join(";");
  const wp = S.wallUrl && $("#thUseWp")?.checked ? `background-image:url('${S.wallUrl}')` : "";
  box.innerHTML = `
  <div class="phone" style="${vars}"><div class="screen">
    <div class="tg-head"><span class="ic">☰</span><div>Telegram<small>в сети</small></div><span class="ic" style="margin-left:auto">⌕</span></div>
    <div class="tg-list">
      ${[["Mia ♡", "голосовое сообщение", "12:04", 3], ["Канал ✦ aesthetic", "новый пост: обои ˖ ࣪", "11:50", 12], ["Лиза", "ахах да 😭", "10:12", 0], ["Избранное", "📎 theme.attheme", "вчера", 0], ["Kpop chat", "Ари: ты видела?", "пн", 99]]
        .map(([n, m, d, c], i) => `<div class="tg-item"><div class="tg-ava" style="${i % 2 ? "filter:hue-rotate(40deg)" : ""}">${n[0]}</div><div><b>${n}</b><span>${m}</span></div><i>${d}<br>${c ? `<span class="tg-badge ${i === 4 ? "m" : ""}">${c}</span>` : ""}</i></div>`).join("")}
    </div>
    <div class="tg-tabs"><span class="on">💬<br>Чаты</span><span>👤<br>Контакты</span><span>⚙︎<br>Настройки</span></div>
  </div></div>
  <div class="phone" style="${vars}"><div class="screen">
    <div class="tg-head"><span class="ic">←</span><div>Mia ♡<small>печатает…</small></div><span class="ic" style="margin-left:auto">⋮</span></div>
    <div class="tg-chat" style="${wp}">
      <div class="tg-date">Сегодня</div>
      <div class="bub in"><div class="nm">Mia</div>смотри какую тему сделала ✦<span class="t">12:01</span></div>
      <div class="bub out"><div class="rp">Mia: смотри какую…</div>очень красиво!! <span class="lk">t.me/addtheme</span><span class="t">12:02 ✓✓</span></div>
      <div class="bub in">а текст хорошо читается? 👀<span class="t">12:03</span></div>
      <div class="bub out">да, контраст как надо ˖ ࣪ ⊹<span class="t">12:04 ✓✓</span></div>
    </div>
    <div class="tg-input">😊 Сообщение<span class="send">➤</span></div>
  </div></div>`;
}

async function exportFiles() {
  if (!S.roles) return toast("Нет темы", "err");
  const r = await api("/api/theme/export", { roles: S.roles, name: S.name, wallpaper: S.wallpaper, use_wallpaper: $("#thUseWp").checked, palette: S.palette });
  $("#thOut").innerHTML = `<div class="links">${linkify(r.zip, "📦 Всё архивом")}
    ${linkify(r.files.android, "Android .attheme")}${linkify(r.files.tdesktop, "Desktop .tdesktop-theme")}
    ${linkify(r.files.ios, "iOS .tgios-theme")}${linkify(r.files.tdesktop_palette, "Desktop палитра")}
    ${r.files.palette ? linkify(r.files.palette, "Палитра PNG") : ""}</div>
    <div class="muted small">Файл темы можно просто отправить себе в «Избранное» и нажать на него в Telegram.</div>`;
}

async function publish() {
  if (!S.roles) return toast("Нет темы", "err");
  const platforms = $$("#thPlatforms .chip.on").map((c) => c.dataset.v);
  if (!platforms.length) return toast("Выбери платформы", "err");
  const r = await api("/api/theme/publish", { roles: S.roles, name: S.name, wallpaper: S.wallpaper, use_wallpaper: $("#thUseWp").checked, platforms });
  $("#thOut").innerHTML = `<div class="links">${r.links.map((l) => linkify(l.link, `${l.platform}: ${l.link}`)).join("")}</div>
    <div class="muted small">Ссылки t.me/addtheme/… — открой на устройстве, тема установится.</div>`;
  toast("Темы созданы в аккаунте ✓", "ok");
}
