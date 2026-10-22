import { $, $$, api, busy, color, debounce, dropZone, esc, h, linkify, pickImages, store, toast, uploadFiles } from "./api.js";

const S = {
  openGroups: new Set(["Основа", "Входящие сообщения", "Исходящие сообщения"]), keysPf: "android", keys: [],
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
        <h3>✨ ИИ сама создаст тему</h3>
        <textarea id="thFullDesc" rows="3" placeholder="опиши идею: «клубничное молоко», «ночной Токио в неоне», «старая библиотека и тёплый свет»"></textarea>
        <div class="row small" style="margin:8px 0">
          <label class="check"><input type="checkbox" id="thFullWp" checked> нарисовать обои</label>
          <label class="check"><input type="checkbox" id="thFullPal"> учитывать мои обои</label>
        </div>
        <button class="btn primary" id="thFull" data-busy="ИИ создаёт тему…">✨ Создать тему целиком</button>
        <div class="muted small" id="thFullInfo" style="margin-top:8px">Нейросеть придумает название, все ${S.meta.roles.length} цветов интерфейса и обои.</div>
      </div>
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
          <button class="btn small ghost" id="thCharts" title="Все 10 линий статистики — в оттенках темы, различимые и контрастные">📊 Статистика в цвет темы</button>
          <button class="btn small ghost" id="thUndo">↶</button>
        </div>
        <div class="row" style="margin-bottom:10px">
          <input type="text" id="thEditTxt" placeholder="🪄 скажи ИИ: «пузыри темнее», «акцент мятный», «шапка как фон»" style="flex:1">
          <button class="btn small primary" id="thEdit" data-busy="Меняю…">Изменить</button>
        </div>
        <div class="chips small" id="thEditChips" style="margin-bottom:8px">
          <span class="chip">📊 раскрась статистику в цвета темы, линии различимы</span>
          <span class="chip">🫧 сделай сообщения стеклянными с мягкой тенью</span>
          <span class="chip">⭕ кольца историй в цвет акцента, близкие друзья — второй акцент</span>
          <span class="chip">🌫 тень под сообщениями в цвет акцента</span>
          <span class="chip">✨ переливающийся градиент исходящих</span>
          <span class="chip">🧱 убери прозрачность и тени</span>
        </div>
        <div class="muted small" id="thEditInfo" style="margin-bottom:8px"></div>
        <div class="muted small" style="margin-bottom:6px">Выбери роль, затем кликни цвет палитры ниже — или используй пипетку.</div>
        <div class="palette" id="thMiniPal" style="margin-bottom:10px"></div>
        <input type="text" id="thRoleQ" placeholder="🔍 найти: пузырь, шапка, счётчик…" style="margin-bottom:8px">
        <div class="roles" id="thRoles" style="max-height:640px"><div class="empty">Тема ещё не выбрана</div></div>
      </div>
      <div class="card"><h3>🫧 Эффекты сообщений <span class="hint">прозрачность, тени, градиент</span></h3>
        <div class="chips small" id="thFxPresets" style="margin-bottom:10px">
          <span class="chip" data-p="solid">🧱 Сплошные</span>
          <span class="chip" data-p="glass">🫧 Стекло</span>
          <span class="chip" data-p="shadow">🌫 Тень</span>
          <span class="chip" data-p="glass_shadow">💎 Стекло + тень</span>
          <span class="chip" data-p="glow">✨ Свечение акцентом</span>
        </div>
        <div id="thFx"></div>
        <label class="check small" style="margin-top:8px"><input type="checkbox" id="fxAnim"> переливающийся градиент исходящих (облачная тема)</label>
        <div class="muted small" style="margin-top:8px">Прозрачность и тени попадают в .attheme / .tdesktop-theme. Если текст на «стекле» станет плохо читаться — «Авто-контраст» сам поднимет непрозрачность. Облачная тема Telegram прозрачность не хранит.</div>
      </div>
      <div class="card"><details id="thKeysDet"><summary style="cursor:pointer"><b>🔬 Тонкая настройка — все ключи Android / Desktop</b></summary>
        <div class="row" style="margin:10px 0">
          <div class="seg" id="thKeysPf"><button data-v="android" class="on">Android</button><button data-v="tdesktop">Desktop</button></div>
          <label class="check small"><input type="checkbox" id="thKeysOnly"> только изменённые</label>
        </div>
        <input type="text" id="thKeysQ" placeholder="поиск ключа: Bubble, chats_, msgIn, actionBar…">
        <div class="row small" style="margin:8px 0">
          <input type="text" id="thKeyNew" placeholder="добавить свой ключ" style="flex:1">
          <button class="btn small" id="thKeyAdd">＋</button>
          <button class="btn small ghost danger" id="thKeysReset">сбросить ручные</button>
        </div>
        <div class="roles" id="thKeys" style="max-height:420px"></div>
        <div class="muted small" style="margin-top:8px">Эти значения важнее ролей. Облачная тема Telegram берёт только акцент и цвета сообщений — все ключи попадают в файлы .attheme и .tdesktop-theme.</div>
      </details></div>
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
  $("#thFull").onclick = (e) => busy(e.currentTarget, aiFull);
  $("#thEdit").onclick = (e) => busy(e.currentTarget, aiEdit);
  $("#thEditTxt").onkeydown = (e) => { if (e.key === "Enter") $("#thEdit").click(); };
  $$("#thEditChips .chip").forEach((c) => (c.onclick = () => { $("#thEditTxt").value = c.textContent.replace(/^\S+\s/, ""); $("#thEdit").click(); }));
  $$("#thFxPresets .chip").forEach((c) => (c.onclick = () => applyFxPreset(c.dataset.p)));
  $("#fxAnim").onchange = (e) => setFx({ animated_gradient: e.target.checked }, true);
  $("#thUseWp").addEventListener("change", () => S.roles && setRoles(S.roles, false));
  $("#thRoleQ").oninput = () => drawRoles();
  $$("#thKeysPf button").forEach((b) => (b.onclick = () => { $$("#thKeysPf button").forEach((x) => x.classList.toggle("on", x === b)); S.keysPf = b.dataset.v; loadKeys(); }));
  $("#thKeysQ").oninput = () => drawKeys();
  $("#thKeysOnly").onchange = () => drawKeys();
  $("#thKeysDet").addEventListener("toggle", () => { if ($("#thKeysDet").open) loadKeys(); });
  $("#thKeyAdd").onclick = () => {
    const k = $("#thKeyNew").value.trim();
    if (!k || !S.roles) return;
    setOverride(k, S.roles.accent);
    $("#thKeyNew").value = "";
  };
  $("#thKeysReset").onclick = () => {
    if (!S.roles?._overrides?.[S.keysPf]) return;
    pushUndo();
    const ov = { ...(S.roles._overrides || {}) };
    delete ov[S.keysPf];
    setRoles({ ...S.roles, _overrides: ov });
  };
  $("#thFix").onclick = (e) => busy(e.currentTarget, async () => { pushUndo(); const r = await api("/api/theme/fix", { roles: S.roles }); setRoles(r.roles); toast("Контраст исправлен ✓", "ok"); });
  $("#thApplyAdj").onclick = () => {
    if (!S.roles) return;
    pushUndo();
    const r = { ...S.roles };
    for (const k of S.meta.roles) r[k] = color.adjust(r[k], S.adj);
    setRoles(r);
  };
  $("#thCharts").onclick = (e) => busy(e.currentTarget, async () => {
    if (!S.roles) return toast("Сначала создай или выбери тему", "err");
    pushUndo();
    setRoles((await api("/api/theme/charts", { roles: S.roles })).roles);
    S.openGroups.add("Статистика"); drawRoles();
  });
  $("#thUndo").onclick = () => { const u = undo.pop(); if (u) setRoles(u, false); };
  $$("#thPlatforms .chip").forEach((c) => (c.onclick = () => c.classList.toggle("on")));
  $("#thExport").onclick = (e) => busy(e.currentTarget, exportFiles);
  $("#thPublish").onclick = (e) => busy(e.currentTarget, publish);

  root.addEventListener("shown", async () => { S.meta = await api("/api/theme/meta"); if (S.roles) drawRoles(); });
  const saved = store.get("theme:last");
  if (saved?.roles) {
    S.name = saved.name || S.name;
    $("#thName").value = S.name;
    // старые сохранённые темы — достраиваем новые детальные роли
    const missing = S.meta.roles.some((k) => !saved.roles[k]);
    if (missing) { try { saved.roles = (await api("/api/theme/fix", { roles: saved.roles, fix: false })).roles; } catch { /* оффлайн */ } }
    setRoles(saved.roles, false);
  }
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
  if (S.roles._fx || S.wallUrl) S.roles._fx = { ...fx(), wall: wallHex() };
  if (save) store.set("theme:last", { name: S.name, roles: S.roles });
  drawRoles();
  drawFx();
  renderPhones();
}

function report() {
  return S.meta.rules.map(([fg, bg, need]) => {
    const r = color.contrast(S.roles[fg], effBg(bg));
    return { fg, bg, need, ratio: r, ok: r >= need - 0.01 };
  });
}

function drawRoles() {
  const box = $("#thRoles");
  if (!S.roles) return;
  box.innerHTML = "";
  const rep = report();
  const q = ($("#thRoleQ")?.value || "").trim().toLowerCase();
  for (const [group, keys] of S.meta.groups) {
    const shown = keys.filter((k) => !q || k.includes(q) || S.meta.labels[k].toLowerCase().includes(q) || group.toLowerCase().includes(q));
    if (!shown.length) continue;
    const badN = rep.filter((r) => keys.includes(r.fg) && !r.ok).length;
    const det = h(`<details ${S.openGroups.has(group) || q ? "open" : ""} style="margin-bottom:4px">
      <summary style="cursor:pointer;padding:6px 4px;font-weight:700;font-size:13px">${esc(group)}
        <span class="muted small">${keys.length}</span> ${badN ? `<span class="badge-c bad">⚠ ${badN}</span>` : ""}
        <span style="display:inline-flex;gap:2px;margin-left:6px;vertical-align:middle">${keys.slice(0, 8).map((k) => `<i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${S.roles[k]}"></i>`).join("")}</span>
      </summary></details>`);
    det.addEventListener("toggle", () => { det.open ? S.openGroups.add(group) : S.openGroups.delete(group); });
    for (const k of shown) det.append(roleRow(k, rep));
    box.append(det);
  }
  const bad = rep.filter((r) => !r.ok);
  $("#thReportSum").innerHTML = bad.length
    ? `<span class="badge-c bad">⚠ ${bad.length} пар с низким контрастом</span> <button class="btn small" id="thFix2">исправить</button>`
    : `<span class="badge-c">✓ все тексты читаемы (WCAG)</span>`;
  const f2 = $("#thFix2");
  if (f2) f2.onclick = () => $("#thFix").click();
  if ($("#thKeysDet")?.open) loadKeys();
}

function roleRow(k, rep) {
  const mine = rep.filter((r) => r.fg === k);
  const worst = mine.sort((a, b) => a.ratio / a.need - b.ratio / b.need)[0];
  const badge = worst ? `<span class="badge-c ${worst.ok ? "" : "bad"}" title="контраст с ${worst.bg}, нужно ≥ ${worst.need}">${worst.ratio.toFixed(1)}</span>` : "<span></span>";
  const row = h(`<div class="role ${S.selRole === k ? "target" : ""}">
    <input type="color" value="${S.roles[k]}"><div>${S.meta.locked?.[k] ? "🔒 " : ""}${esc(S.meta.labels[k])}<br><code>${k}</code></div>
    <input type="text" value="${S.roles[k]}" style="font:11px var(--mono);padding:4px 6px">${badge}</div>`);
  const ci = $("input[type=color]", row);
  const ti = $("input[type=text]", row);
  ci.oninput = () => { S.roles[k] = ci.value; ti.value = ci.value; renderPhones(); };
  ci.onchange = () => { pushUndo(); setRoles(S.roles); };
  ti.onchange = () => { if (/^#[0-9a-f]{6}$/i.test(ti.value)) { pushUndo(); setRoles({ ...S.roles, [k]: ti.value.toLowerCase() }); } };
  row.onclick = (e) => { if (e.target.tagName !== "INPUT") { S.selRole = k; drawRoles(); } };
  return row;
}

// ---------- эффекты: прозрачность и тени ----------
const FX_ROWS = [
  ["in_alpha", "Входящие — непрозрачность", 15], ["out_alpha", "Исходящие — непрозрачность", 15],
  ["service_alpha", "Плашки дат и сервисные", 0], ["input_alpha", "Панель ввода", 0], ["selection_alpha", "Выделение сообщений", 0],
];
const FX_PRESETS = {
  solid: { in_alpha: 100, out_alpha: 100, service_alpha: 80, input_alpha: 100, shadow_in_alpha: 0, shadow_out_alpha: 0 },
  glass: { in_alpha: 62, out_alpha: 70, service_alpha: 55, input_alpha: 80, shadow_in_alpha: 0, shadow_out_alpha: 0 },
  shadow: { in_alpha: 100, out_alpha: 100, shadow_in: "#000000", shadow_in_alpha: 30, shadow_out: "#000000", shadow_out_alpha: 30 },
  glass_shadow: { in_alpha: 65, out_alpha: 72, service_alpha: 55, input_alpha: 82, shadow_in: "#000000", shadow_in_alpha: 22, shadow_out: "#000000", shadow_out_alpha: 22 },
  glow: () => ({ shadow_in: S.roles.accent, shadow_in_alpha: 35, shadow_out: S.roles.accent2 || S.roles.accent, shadow_out_alpha: 45 }),
};

function fx() { return { ...(S.meta?.fx_default || {}), ...(S.roles?._fx || {}) }; }

// средний цвет обоев по палитре — под полупрозрачными пузырями лежат именно они
function wallHex() {
  if (!S.wallUrl || !$("#thUseWp")?.checked || !S.base.length) return "";
  let w = 0;
  const acc = [0, 0, 0];
  for (const c of S.base) { const rgb = color.toRgb(c.hex); const k = c.share || 0.01; rgb.forEach((v, i) => (acc[i] += v * k)); w += k; }
  return color.toHex(acc.map((v) => v / w));
}

function mixHex(a, b, t) {
  const [x, y] = [color.toRgb(a), color.toRgb(b)];
  return color.toHex(x.map((v, i) => v + (y[i] - v) * t));
}

function effBg(role) {
  const key = S.meta.alpha_bg?.[role];
  if (!key) return S.roles[role];
  const f = fx();
  return mixHex(f.wall || S.roles.chat_bg || S.roles.bg, S.roles[role], (f[key] ?? 100) / 100);
}

function rgba(hex, a) { const [r, g, b] = color.toRgb(hex); return `rgba(${r},${g},${b},${(a / 100).toFixed(2)})`; }

function setFx(patch, commit) {
  if (!S.roles) return toast("Сначала создай или выбери тему", "err");
  if (commit) pushUndo();
  S.roles._fx = { ...fx(), ...patch };
  if (commit) setRoles(S.roles); else { renderPhones(); }
}

function applyFxPreset(name) {
  if (!S.roles) return toast("Сначала создай или выбери тему", "err");
  const p = typeof FX_PRESETS[name] === "function" ? FX_PRESETS[name]() : FX_PRESETS[name];
  setFx(p, true);
}

function drawFx() {
  const box = $("#thFx");
  if (!box) return;
  if (!S.roles) { box.innerHTML = `<div class="empty">Тема ещё не выбрана</div>`; return; }
  const f = fx();
  $("#fxAnim").checked = !!f.animated_gradient;
  box.innerHTML = FX_ROWS.map(([k, label, min]) => `<div class="slider-row"><span>${label}</span><input type="range" min="${min}" max="100" data-fx="${k}" value="${f[k]}"><output>${f[k]}%</output></div>`).join("")
    + [["in", "Тень входящих"], ["out", "Тень исходящих"]].map(([s, label]) => `<div class="slider-row"><span>${label}</span>
        <input type="range" min="0" max="100" data-fx="shadow_${s}_alpha" value="${f[`shadow_${s}_alpha`]}"><output>${f[`shadow_${s}_alpha`]}%</output>
        <input type="color" data-fx="shadow_${s}" value="${f[`shadow_${s}`]}" title="цвет тени" style="width:34px;height:26px;padding:0;margin-left:6px"></div>`).join("");
  $$("[data-fx]", box).forEach((inp) => {
    const k = inp.dataset.fx;
    const val = () => (inp.type === "range" ? +inp.value : inp.value);
    inp.oninput = () => {
      if (inp.type === "range") inp.nextElementSibling.textContent = inp.value + "%";
      setFx({ [k]: val() }, false);
    };
    inp.onchange = () => setFx({ [k]: val() }, true);
  });
}

// ---------- тонкая настройка ключей ----------
const loadKeys = debounce(async () => {
  if (!S.roles) return;
  try { S.keys = (await api("/api/theme/keys", { roles: S.roles, platform: S.keysPf })).keys; } catch (e) { toast(e.message, "err"); return; }
  drawKeys();
}, 300);

function setOverride(key, hex8) {
  pushUndo();
  const ov = { ...(S.roles._overrides || {}) };
  ov[S.keysPf] = { ...(ov[S.keysPf] || {}), [key]: hex8 };
  setRoles({ ...S.roles, _overrides: ov });
}

function drawKeys() {
  const box = $("#thKeys");
  const q = $("#thKeysQ").value.trim().toLowerCase();
  const only = $("#thKeysOnly").checked;
  const list = (S.keys || []).filter((k) => (!q || k.key.toLowerCase().includes(q) || k.expr.includes(q)) && (!only || k.override));
  box.innerHTML = list.length ? "" : `<div class="empty">Ничего не найдено</div>`;
  for (const k of list.slice(0, 200)) {
    const row = h(`<div class="role" style="grid-template-columns:30px 1fr 58px auto">
      <input type="color" value="${k.color}">
      <div style="overflow:hidden">${k.override ? "✎ " : ""}<code style="color:var(--text)">${esc(k.key)}</code><br><code>${esc(k.expr)}</code></div>
      <input type="number" min="0" max="100" value="${k.alpha}" title="непрозрачность %" style="padding:4px">
      ${k.override ? '<button class="icon-btn" title="вернуть как в роли">↺</button>' : "<span></span>"}</div>`);
    const [ci, ai] = [row.querySelector("input[type=color]"), row.querySelector("input[type=number]")];
    const commit = () => {
      const a = Math.round(Math.max(0, Math.min(100, +ai.value)) * 2.55);
      setOverride(k.key, ci.value + (a === 255 ? "" : a.toString(16).padStart(2, "0")));
    };
    ci.onchange = commit;
    ai.onchange = commit;
    const rb = row.querySelector("button");
    if (rb) rb.onclick = () => {
      pushUndo();
      const ov = structuredClone(S.roles._overrides || {});
      delete ov[S.keysPf][k.key];
      setRoles({ ...S.roles, _overrides: ov });
    };
    box.append(row);
  }
  if (list.length > 200) box.append(h(`<div class="muted small" style="padding:6px">…ещё ${list.length - 200}, уточни поиск</div>`));
}

// ---------- ИИ: тема целиком и правка словами ----------
async function aiFull() {
  const desc = $("#thFullDesc").value.trim();
  const r = await api("/api/theme/ai_full", {
    description: desc, mode: S.mode, wallpaper: $("#thFullWp").checked,
    use_palette: $("#thFullPal").checked && S.palette.length > 0, palette: S.palette,
  });
  const t = r.theme.roles;
  pushUndo();
  S.name = t._meta?.name || S.name;
  $("#thName").value = S.name;
  if (r.wallpaper) {
    S.wallpaper = r.wallpaper;
    S.wallUrl = `/uploads/${encodeURIComponent(r.wallpaper)}`;
    $("#thDrop").innerHTML = `<img src="${S.wallUrl}">`;
    S.base = r.palette;
    S.brightness = r.brightness;
    applyAdj();
  }
  S.variants = [r.theme, ...S.variants].slice(0, 12);
  drawVariants();
  setRoles(t);
  $("#thFullInfo").innerHTML = `✓ «${esc(S.name)}»: ИИ заполнил ${t._meta?.filled_by_ai ?? "?"} из ${t._meta?.total ?? S.meta.roles.length} цветов, остальные рассчитаны программой.`
    + (r.wallpaper_error ? `<br>⚠ обои не нарисовались: ${esc(r.wallpaper_error)}` : "")
    + (r.wallpaper_prompt && !r.wallpaper ? `<br><span class="muted">идея обоев: ${esc(r.wallpaper_prompt)}</span>` : "");
}

async function aiEdit() {
  if (!S.roles) return toast("Сначала создай или выбери тему", "err");
  const instruction = $("#thEditTxt").value.trim();
  if (!instruction) return toast("Напиши, что поменять", "err");
  const r = await api("/api/theme/ai_edit", { roles: S.roles, instruction });
  pushUndo();
  setRoles(r.roles);
  $("#thEditInfo").textContent = r.changed.length
    ? `✓ изменено: ${r.changed.map((k) => S.meta.labels[k] || k).join(", ")}${r.comment ? " — " + r.comment : ""}`
    : "ИИ ничего не поменял — попробуй сформулировать иначе";
}

function renderPhones() {
  const box = $("#thPhones");
  if (!box) return;
  const t = S.roles;
  if (!t) { box.innerHTML = `<div class="empty">Здесь появится предпросмотр темы</div>`; return; }
  const f = fx();
  const sh = (s) => (f[`shadow_${s}_alpha`] ? `0 2px ${4 + f[`shadow_${s}_alpha`] / 8}px ${rgba(f[`shadow_${s}`], Math.min(100, f[`shadow_${s}_alpha`] * 1.6))}` : "none");
  const vars = S.meta.roles.map((k) => `--t-${k}:${t[k]}`).join(";")
    + `;--b-in:${rgba(t.in_bubble, f.in_alpha)};--b-out:${rgba(t.out_bubble, f.out_alpha)};--b-out2:${rgba(t.out_bubble2, f.out_alpha)}`
    + `;--b-svc:${rgba(t.service_bg, f.service_alpha)};--b-inp:${rgba(t.input_bg, f.input_alpha)};--sh-in:${sh("in")};--sh-out:${sh("out")}`;
  const stories = [["Ты", 0], ["Mia", 1], ["Лиза", 2], ["Ари", 1], ["Канал", 3]]
    .map(([n, k]) => `<div class="tg-story"><i style="background:${k === 2 ? `linear-gradient(135deg,${t.story_close1},${t.story_close2})` : k === 3 ? t.divider : `linear-gradient(135deg,${t.story1},${t.story2})`}"><b>${k ? n[0] : "+"}</b></i><span>${n}</span></div>`).join("");
  const wp = S.wallUrl && $("#thUseWp")?.checked ? `background-image:url('${S.wallUrl}')` : "";
  box.innerHTML = `
  <div class="phone" style="${vars}"><div class="screen">
    <div class="tg-head"><span class="ic">☰</span><div>Telegram<small>в сети</small></div><span class="ic" style="margin-left:auto">⌕</span></div>
    <div class="tg-list">
      <div class="tg-stories">${stories}</div>
      ${[["Mia ♡", "голосовое сообщение", "12:04", 3], ["Канал ✦ aesthetic", "новый пост: обои ˖ ࣪", "11:50", 12], ["Лиза", "ахах да 😭", "10:12", 0], ["Избранное", "📎 theme.attheme", "вчера", 0], ["Kpop chat", "Ари: ты видела?", "пн", 99]]
        .map(([n, m, d, c], i) => `<div class="tg-item" style="${i === 0 ? "background:var(--t-pinned_bg)" : ""}"><div class="tg-ava" style="${i % 2 ? "filter:hue-rotate(40deg)" : ""}">${n[0]}</div><div><b>${n}</b><span>${m}</span></div><i>${i === 3 ? '<span style="color:var(--t-online)">✓✓</span> ' : ""}${d}<br>${c ? `<span class="tg-badge ${i === 4 ? "m" : ""}">${c}</span>` : ""}</i></div>`).join("")}
      <div class="tg-fab">✎</div>
    </div>
    <div class="tg-tabs"><span class="on">💬<br>Чаты</span><span>👤<br>Контакты</span><span>⚙︎<br>Настройки</span></div>
  </div></div>
  <div class="phone" style="${vars}"><div class="screen">
    <div class="tg-head"><span class="ic">←</span><div>Mia ♡<small>печатает…</small></div><span class="ic" style="margin-left:auto">⋮</span></div>
    <div class="tg-chat" style="${wp}">
      <div class="tg-date">Сегодня</div>
      <div class="bub in"><div class="nm">Mia</div>смотри какую тему сделала ✦<span class="t">12:01</span></div>
      <div class="bub out"><div class="rp">Mia: смотри какую…</div>очень красиво!! <span class="lk">t.me/addtheme</span><span class="t">12:02 <b class="ck">✓✓</b></span></div>
      <div class="bub in">а текст хорошо читается? 👀 <span class="lk">#тема</span><span class="t">12:03</span></div>
      <div class="bub out">да, контраст как надо ˖ ࣪ ⊹<span class="t">12:04 <b class="ck">✓✓</b></span></div>
    </div>
    <div class="tg-input"><span class="ic">😊</span>Сообщение<span class="ic" style="margin-left:auto">📎</span><span class="send" style="margin-left:8px">➤</span></div>
  </div></div>
  <div class="phone short" style="${vars}"><div class="screen">
    <div class="tg-head"><span class="ic">←</span><div>Статистика<small>канал ✦ aesthetic</small></div></div>
    <div class="tg-list" style="padding:10px 12px">${statsChart(t)}</div>
  </div></div>`;
}

function statsChart(t) {
  const keys = S.meta.charts || [];
  const W = 220, H = 120;
  const lines = keys.slice(0, 6).map((k, i) => {
    const pts = Array.from({ length: 12 }, (_, x) => {
      const y = 0.5 + 0.32 * Math.sin(x * 0.7 + i * 1.3) * (1 - i * 0.08) + (i - 2.5) * 0.06;
      return `${(x / 11) * W},${(H * Math.min(0.95, Math.max(0.05, y))).toFixed(1)}`;
    }).join(" ");
    return `<polyline points="${pts}" fill="none" stroke="${t[k]}" stroke-width="2" stroke-linejoin="round"/>`;
  }).join("");
  const grid = [0.25, 0.5, 0.75].map((y) => `<line x1="0" x2="${W}" y1="${H * y}" y2="${H * y}" stroke="${t.chart_grid}"/>`).join("");
  const legend = keys.map((k, i) => `<span title="${esc(S.meta.labels[k] || k)}"><i style="background:${t[k]}"></i>${i + 1}</span>`).join("");
  return `<div style="color:var(--t-chart_text);font-size:11px;margin-bottom:6px">Подписчики · просмотры</div>
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;display:block">${grid}${lines}</svg>
    <div style="display:flex;justify-content:space-between;color:var(--t-chart_text);font-size:9.5px;margin:2px 0 8px"><span>1 окт</span><span>15 окт</span><span>22 окт</span></div>
    <div class="tg-legend">${legend}</div>`;
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
