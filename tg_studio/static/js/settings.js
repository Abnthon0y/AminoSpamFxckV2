import { $, $$, api, busy, esc, h, pickImages, runJob, toast } from "./api.js";

const FIELDS = {
  pollinations: [["model", "Модель", "openai"], ["api_key", "Токен (необязательно)", ""]],
  claude_cli: [["command", "Команда", "claude"], ["model", "Модель (пусто = по умолчанию)", ""]],
  ollama: [["base_url", "Адрес Ollama", "http://127.0.0.1:11434"], ["model", "Модель", "llama3.1"]],
  gemini: [["api_key", "API-ключ (бесплатный)", ""], ["model", "Модель", "gemini-2.5-flash"]],
  openai_compat: [["base_url", "Base URL", "https://openrouter.ai/api/v1"], ["model", "Модель", ""], ["api_key", "API-ключ", ""]],
  anthropic: [["api_key", "API-ключ Anthropic", ""], ["model", "Модель", "claude-opus-5-5"]],
  none: [],
};

const HELP = {
  pollinations: "Работает сразу, без регистрации и ключей. Бесплатно, но бывают лимиты и очереди. Хорошо для старта.",
  claude_cli: `<b>Claude без API-кредитов.</b> Если у тебя есть подписка Claude Pro или Max, поставь Claude Code:
    <code>npm install -g @anthropic-ai/claude-code</code>, затем один раз запусти <code>claude</code> в терминале и войди
    своим аккаунтом claude.ai. После этого программа вызывает <code>claude -p</code> — запросы идут в счёт подписки,
    а не платного API. Бесплатный аккаунт claude.ai так подключить нельзя: для него нет официального способа.`,
  ollama: "Нейросеть прямо на твоём ПК, полностью бесплатно и офлайн. Скачай ollama.com, затем <code>ollama pull llama3.1</code> (для картинок-подсказок — <code>ollama pull llava</code>).",
  gemini: `Бесплатный ключ: <a href="https://aistudio.google.com/apikey" target="_blank">aistudio.google.com/apikey</a>. Хорошие лимиты, умеет смотреть картинки.`,
  openai_compat: "Любой OpenAI-совместимый сервис: OpenRouter (модели с пометкой :free — бесплатно), Groq (бесплатный ключ), LM Studio (локально), DeepSeek и др.",
  anthropic: "Официальный Claude API — нужен ключ и кредиты на console.anthropic.com.",
  none: "Без нейросети: темы, раскладка эмодзи и стикеры работают на алгоритмах.",
};

const PRESETS = {
  "OpenRouter (free)": { base_url: "https://openrouter.ai/api/v1", model: "meta-llama/llama-3.3-70b-instruct:free" },
  "Groq": { base_url: "https://api.groq.com/openai/v1", model: "llama-3.3-70b-versatile" },
  "LM Studio": { base_url: "http://127.0.0.1:1234/v1", model: "local-model" },
  "DeepSeek": { base_url: "https://api.deepseek.com/v1", model: "deepseek-chat" },
};

let S = null;

export async function initSettings(root) {
  const data = await api("/api/settings");
  S = data.settings;
  root.innerHTML = `
  <div class="page-head"><div><h1>⚙️ ИИ и аккаунт</h1>
    <p>Подключи нейросеть (можно бесплатно и без API) и войди в Telegram — тогда программа сама создаёт темы, языки и паки в твоём аккаунте.</p></div></div>
  <div class="grid cols-2">
    <div class="stack">
      <div class="card"><h3>🧠 Текстовая нейросеть</h3>
        <div class="stack" id="stProviders"></div>
        <div id="stFields" class="stack" style="margin-top:12px"></div>
        <div class="help" id="stHelp" style="margin-top:12px"></div>
        <label class="check" style="margin-top:12px"><input type="checkbox" id="stVision"> Отправлять картинки нейросети (vision) — для умной раскладки и подбора эмодзи</label>
        <label class="field" style="margin-top:12px"><span>Прокси (если сайты нейросетей заблокированы) — необязательно</span>
          <input type="text" id="stProxy" placeholder="http://127.0.0.1:10809 или socks5://127.0.0.1:1080"></label>
        <div class="muted small" style="margin-top:4px">Адрес берётся из твоего VPN-клиента (v2rayN, Hiddify, Clash и т.п. — раздел «прокси/порт»). Если VPN включён на весь компьютер — оставь пустым.</div>
        <div class="row end"><button class="btn ghost" id="stDiag" data-busy="Проверяю всё…">🩺 Диагностика</button>
          <button class="btn" id="stTest" data-busy="Проверяю…">🔌 Проверить</button><button class="btn primary" id="stSaveAI">Сохранить</button></div>
        <div id="stDiagOut" class="stack" style="gap:6px;margin-top:10px"></div>
        <pre class="out" id="stTestOut" hidden></pre>
      </div>
      <div class="card"><h3>🎨 Нейросеть-художник <span class="hint">для баннеров, артов и пиксель-GIF</span></h3>
        <div class="kv">
          <label class="field">Провайдер<select id="stImgProv">
            <option value="pollinations">Pollinations — бесплатно</option>
            <option value="a1111">Stable Diffusion (AUTOMATIC1111 / Forge)</option>
            <option value="none">Выключено</option></select></label>
          <label class="field">Модель Pollinations<input type="text" id="stPolModel"></label>
        </div>
        <label class="field" style="margin-top:10px">Адрес SD WebUI (запусти с флагом --api)<input type="text" id="stA1111"></label>
        <div class="row end"><button class="btn primary" id="stSaveImg">Сохранить</button></div>
      </div>
    </div>
    <div class="stack">
      <div class="card"><h3>✈️ Аккаунт Telegram <span class="hint" id="stTgState"></span></h3>
        <div class="help">api_id и api_hash бесплатно получаются на <a href="https://my.telegram.org/apps" target="_blank">my.telegram.org → API development tools</a>.
          Сессия хранится только у тебя на компьютере в папке <code>data/</code>.</div>
        <div class="kv" style="margin-top:12px">
          <label class="field">api_id<input type="text" id="stApiId"></label>
          <label class="field">api_hash<input type="password" id="stApiHash"></label>
        </div>
        <div class="row" style="margin-top:12px"><button class="btn small ghost" id="stSaveTg2">💾 Сохранить api_id / api_hash</button></div>
        <div class="sep" style="margin:12px 0"></div>
        <h3 style="margin:0 0 8px">📱 Способ 1 — по QR-коду <span class="hint">рекомендуется, код не нужен</span></h3>
        <div class="row"><button class="btn" id="stQr" data-busy="Готовлю QR…">Показать QR-код</button></div>
        <div id="stQrBox" hidden style="margin-top:10px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
          <div id="stQrImg" style="background:#fff;padding:10px;border-radius:12px;width:220px;height:220px"></div>
          <div class="small" style="max-width:300px">На телефоне открой <b>Telegram → Настройки → Устройства → Подключить устройство</b>
            и наведи камеру на этот код. <div id="stQrState" class="muted" style="margin-top:8px"></div></div>
        </div>
        <div class="sep" style="margin:12px 0"></div>
        <h3 style="margin:0 0 8px">✉️ Способ 2 — по номеру и коду</h3>
        <label class="field">Телефон<input type="text" id="stPhone" placeholder="+79991234567"></label>
        <div class="row" style="margin-top:10px"><button class="btn" id="stSendCode" data-busy="Отправляю…">📨 Получить код</button>
          <button class="btn ghost" id="stResend" data-busy="Запрашиваю…" hidden>Код не пришёл — прислать иначе</button></div>
        <div class="help" id="stCodeInfo" style="margin-top:10px" hidden></div>
        <div class="kv" style="margin-top:10px">
          <label class="field">Код из Telegram<input type="text" id="stCode"></label>
          <label class="field">Облачный пароль (если есть)<input type="password" id="stPass"></label>
        </div>
        <div class="row end"><button class="btn danger ghost" id="stLogout">Выйти</button><button class="btn primary" id="stSignIn" data-busy="Вхожу…">Войти</button></div>
      </div>
      <div class="card"><h3>🤖 Бот для паков <span class="hint">альтернатива загрузке от аккаунта</span></h3>
        <div class="help">Создай бота у <a href="https://t.me/BotFather" target="_blank">@BotFather</a>, нажми у него /start. Свой user_id узнаешь у @userinfobot.
          Паки будут называться <code>имя_by_твойбот</code>.</div>
        <div class="kv" style="margin-top:12px">
          <label class="field">Токен бота<input type="password" id="stBot"></label>
          <label class="field">Твой user_id<input type="text" id="stUid"></label>
        </div>
        <label class="check" style="margin-top:10px"><input type="checkbox" id="stHeadless"> translations.telegram.org — фоновый браузер (без окна)</label>
        <div class="row end"><button class="btn primary" id="stSaveTg">Сохранить</button></div>
      </div>
      <div class="card"><h3>✂️ Удаление фона <span class="hint" id="bgState"></span></h3>
        <div class="help">Нейросеть (rembg) режет фон намного точнее алгоритма: не съедает светлые волосы, убирает рамки и круги за персонажем.
          Две модели сразу — маски объединяются, одна ловит то, что пропустила другая. Модели скачиваются один раз при первом запуске (~170 МБ каждая).</div>
        <div class="row" id="bgInstallRow" hidden><button class="btn primary" id="bgInstall" data-busy="Ставлю…">⬇ Установить нейросеть (rembg)</button></div>
        <div class="kv" style="margin-top:12px">
          <label class="field">Способ<select id="bgEngine">
            <option value="auto">Авто — нейросеть, если есть, иначе алгоритм</option>
            <option value="ai">Только нейросеть</option>
            <option value="algo">Только алгоритм (быстро, для однотонного фона)</option></select></label>
          <label class="field">Основная модель<select id="bgModel"></select></label>
          <label class="field">Вторая модель (объединение масок)<select id="bgSecond"><option value="">— нет (быстрее, меньше памяти)</option></select></label>
        </div>
        <label class="check" style="margin-top:10px"><input type="checkbox" id="bgDefringe"> Убирать ореол фона на краях</label>
        <div class="row end"><button class="btn ghost" id="bgTry" data-busy="Режу…">👁 Проверить на картинке</button><button class="btn primary" id="bgSave">Сохранить</button></div>
        <div class="bg-cmp" id="bgCmp"></div>
      </div>
    </div>
  </div>`;

  const provBox = $("#stProviders");
  for (const [k, info] of Object.entries(data.providers)) {
    const el = h(`<label class="check"><input type="radio" name="prov" value="${k}" ${S.ai.provider === k ? "checked" : ""}> ${esc(info.label)}</label>`);
    $("input", el).onchange = () => { S.ai.provider = k; drawFields(); };
    provBox.append(el);
  }
  $("#stVision").checked = !!S.ai.vision;
  drawFields();

  $("#stImgProv").value = S.image_ai.provider;
  $("#stPolModel").value = S.image_ai.pollinations_model || "flux";
  $("#stA1111").value = S.image_ai.a1111_url;
  const tg = S.telegram;
  $("#stApiId").value = tg.api_id || "";
  $("#stApiHash").value = tg.api_hash || "";
  $("#stPhone").value = tg.phone || "";
  $("#stBot").value = tg.bot_token || "";
  $("#stUid").value = tg.user_id || "";
  $("#stHeadless").checked = !!S.translations?.headless;

  initBg();
  $("#stSaveAI").onclick = (e) => busy(e.currentTarget, saveAI);
  $("#stProxy").value = S.ai.proxy || "";
  $("#stTest").onclick = async (e) => {
    const out = $("#stTestOut");
    const btn = e.currentTarget;
    btn.disabled = true;
    out.hidden = false;
    out.textContent = "⏳ Отправляю тестовый запрос… (бесплатные сервисы могут думать до минуты)";
    try {
      await saveAI(true);
      const r = await api("/api/ai/test", {});
      out.textContent = `✅ Работает! Ответ за ${r.seconds} c: «${r.reply.trim()}»`;
    } catch (err) {
      out.textContent = "❌ " + err.message;  // ошибка остаётся на экране, а не исчезает через 7 секунд
    } finally { btn.disabled = false; }
  };
  $("#stDiag").onclick = (e) => busy(e.currentTarget, async () => {
    await saveAI(true);
    const r = await api("/api/ai/diagnose", {});
    $("#stDiagOut").innerHTML = r.checks.map((c) =>
      `<div class="small" style="display:flex;align-items:flex-start;gap:8px"><b style="min-width:16px">${c.ok ? "✅" : "❌"}</b>
        <div><b>${esc(c.name)}</b> — <span class="muted">${esc(c.detail)}</span></div></div>`).join("");
  });
  $("#stSaveImg").onclick = (e) => busy(e.currentTarget, async () => {
    await api("/api/settings", { image_ai: { provider: $("#stImgProv").value, a1111_url: $("#stA1111").value, pollinations_model: $("#stPolModel").value } });
    toast("Сохранено ✓", "ok");
  });
  $("#stSaveTg").onclick = (e) => busy(e.currentTarget, saveTg);
  $("#stSaveTg2").onclick = (e) => busy(e.currentTarget, saveTg);
  const showSent = (r) => {
    const box = $("#stCodeInfo");
    box.hidden = false;
    box.innerHTML = `📨 Код отправлен <b>${esc(r.via)}</b>.` +
      (r.next ? `<br>Если не придёт — нажми «Код не пришёл», Telegram пришлёт ${esc(r.next)}${r.timeout ? ` (можно через ${r.timeout} c)` : ""}.` : "") +
      `<br><span class="muted">Никому не сообщай этот код. Не пришёл совсем? Войди по QR-коду выше.</span>`;
    $("#stResend").hidden = !r.next;
  };
  $("#stSendCode").onclick = (e) => busy(e.currentTarget, async () => {
    await saveTg(true);
    const r = await api("/api/tg/send_code", { phone: $("#stPhone").value });
    if (r.authorized) { toast(`Уже вошли как ${r.name} ✓`, "ok"); return tgState(); }
    showSent(r);
  });
  $("#stResend").onclick = (e) => busy(e.currentTarget, async () => showSent(await api("/api/tg/resend_code", {})));
  $("#stQr").onclick = (e) => busy(e.currentTarget, async () => {
    await saveTg(true);
    const r = await api("/api/tg/qr_start", {});
    if (r.status === "done") { toast(`Уже вошли как ${r.name} ✓`, "ok"); return tgState(); }
    $("#stQrBox").hidden = false;
    pollQr(r.url);
  });
  $("#stSignIn").onclick = (e) => busy(e.currentTarget, async () => {
    const r = await api("/api/tg/sign_in", { code: $("#stCode").value || null, password: $("#stPass").value || null });
    if (r.need_password) return toast("Включена двухэтапная проверка — введи облачный пароль и нажми «Войти»");
    if (r.authorized) toast(`Вошли как ${r.name} ✓`, "ok");
    tgState();
  });
  $("#stLogout").onclick = (e) => busy(e.currentTarget, async () => { await api("/api/tg/logout", {}); tgState(); });
  tgState();
}

// ---------- QR-вход ----------
let qrTimer = null, qrUrl = null;
async function loadQrLib() {
  if (window.QRCode) return true;
  await new Promise((res) => {
    const sc = document.createElement("script");
    sc.src = "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js";
    sc.onload = res;
    sc.onerror = res;
    document.head.append(sc);
  });
  return !!window.QRCode;
}
async function drawQr(url) {
  if (url === qrUrl) return;
  qrUrl = url;
  const box = $("#stQrImg");
  box.innerHTML = "";
  if (await loadQrLib()) new window.QRCode(box, { text: url, width: 200, height: 200, correctLevel: window.QRCode.CorrectLevel.L });
  else box.innerHTML = `<div class="small" style="color:#000;word-break:break-all">Нет интернета для QR-картинки. Ссылка: ${esc(url)}</div>`;
}
function pollQr(url) {
  clearTimeout(qrTimer);
  qrUrl = null;
  drawQr(url);
  $("#stQrState").textContent = "⏳ Жду сканирования…";
  const tick = async () => {
    let st;
    try { st = await api("/api/tg/qr_status"); } catch (e) { $("#stQrState").textContent = "❌ " + e.message; return; }
    if (st.status === "waiting") { drawQr(st.url); qrTimer = setTimeout(tick, 2000); return; }
    if (st.status === "done") { $("#stQrState").textContent = `✅ Вошли как ${st.name}`; $("#stQrBox").hidden = true; toast(`Вошли как ${st.name} ✓`, "ok"); tgState(); return; }
    if (st.status === "password") { $("#stQrState").innerHTML = "🔐 Включена двухэтапная проверка: введи <b>облачный пароль</b> ниже и нажми «Войти»."; $("#stPass").focus(); return; }
    if (st.status === "expired") { $("#stQrState").textContent = "⌛ Время вышло — нажми «Показать QR-код» ещё раз"; return; }
    $("#stQrState").textContent = "❌ " + (st.error || st.status);
  };
  qrTimer = setTimeout(tick, 2000);
}

function drawFields() {
  const p = S.ai.provider;
  const cfg = S.ai.providers[p] || {};
  const box = $("#stFields");
  box.innerHTML = "";
  for (const [key, label, ph] of FIELDS[p] || []) {
    const type = key === "api_key" ? "password" : "text";
    box.append(h(`<label class="field">${esc(label)}<input type="${type}" data-k="${key}" value="${esc(cfg[key] || "")}" placeholder="${esc(ph)}"></label>`));
  }
  if (p === "openai_compat") {
    const row = h(`<div class="chips"></div>`);
    for (const [name, v] of Object.entries(PRESETS)) {
      const c = h(`<span class="chip">${esc(name)}</span>`);
      c.onclick = () => { for (const [k, val] of Object.entries(v)) $(`[data-k=${k}]`, box).value = val; };
      row.append(c);
    }
    box.prepend(row);
  }
  $("#stHelp").innerHTML = HELP[p] || "";
}

async function saveAI(silent) {
  const p = S.ai.provider;
  const vals = {};
  $$("#stFields [data-k]").forEach((i) => (vals[i.dataset.k] = i.value));
  S.ai.providers[p] = { ...S.ai.providers[p], ...vals };
  const r = await api("/api/settings", { ai: { provider: p, vision: $("#stVision").checked, proxy: $("#stProxy").value.trim(), providers: { [p]: vals } } });
  S = r.settings;
  if (!silent) toast("Нейросеть сохранена ✓", "ok");
  window.dispatchEvent(new Event("tgs:status"));
}

async function saveTg(silent) {
  await api("/api/settings", {
    telegram: { api_id: $("#stApiId").value.trim(), api_hash: $("#stApiHash").value.trim(), phone: $("#stPhone").value.trim(),
      bot_token: $("#stBot").value.trim(), user_id: $("#stUid").value.trim() },
    translations: { headless: $("#stHeadless").checked },
  });
  if (!silent) toast("Сохранено ✓", "ok");
}

async function tgState() {
  try {
    const st = await api("/api/tg/status");
    $("#stTgState").textContent = st.authorized ? `✓ ${st.name}${st.username ? " @" + st.username : ""}` : (st.error || "не вошли");
  } catch (e) { $("#stTgState").textContent = e.message; }
  window.dispatchEvent(new Event("tgs:status"));
}

// ---------- удаление фона ----------
async function initBg() {
  const st = await api("/api/bg/status");
  const opts = Object.entries(st.models).map(([k, v]) => `<option value="${k}">${esc(k)} — ${esc(v)}</option>`).join("");
  $("#bgModel").innerHTML = opts;
  $("#bgSecond").insertAdjacentHTML("beforeend", opts);
  const b = { engine: "auto", model: "isnet-anime", second: "isnet-general-use", defringe: true, ...st.settings };
  $("#bgEngine").value = b.engine;
  $("#bgModel").value = b.model;
  $("#bgSecond").value = b.second || "";
  $("#bgDefringe").checked = b.defringe !== false;
  const state = (ok) => {
    $("#bgState").textContent = ok ? "✅ нейросеть установлена" : "⚠️ нейросеть не установлена — работает алгоритм";
    $("#bgInstallRow").hidden = ok;
  };
  state(st.installed);
  const save = () => api("/api/settings", { bg: { engine: $("#bgEngine").value, model: $("#bgModel").value,
    second: $("#bgSecond").value, defringe: $("#bgDefringe").checked } });
  $("#bgSave").onclick = (e) => busy(e.currentTarget, async () => { await save(); toast("Сохранено", "ok"); });
  $("#bgInstall").onclick = (e) => busy(e.currentTarget, async () => {
    const { job } = await api("/api/bg/install", {});
    const j = await runJob(job, "Установка нейросети для фона");
    state(j.status === "done");
  });
  $("#bgTry").onclick = async (e) => {
    const names = await pickImages({ multi: false });
    if (!names?.length) return;
    await busy(e.currentTarget, async () => {
      await save();
      const r = await api("/api/bg/preview", { name: names[0] });
      const cell = (x, t) => `<figure><img src="${x.url}?t=${Date.now()}"><figcaption>${t} · ${x.sec} с · прозрачно ${Math.round(x.transparent * 100)}%</figcaption></figure>`;
      $("#bgCmp").innerHTML = cell(r.auto, "По настройкам") + cell(r.algo, "Алгоритм");
    });
  };
}
