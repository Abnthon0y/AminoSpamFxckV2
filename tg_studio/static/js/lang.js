import { $, $$, api, busy, debounce, esc, h, linkify, runJob, store, toast } from "./api.js";

const S = { fonts: {}, platforms: {}, presets: new Set(["aesthetic", "cyr_soft"]), mode: "charmap", platform: "android" };

export async function initLang(root) {
  const cm = await api("/api/charmaps");
  S.fonts = cm.fonts;
  S.platforms = cm.platforms;
  const saved = store.get("lang:form", {});
  root.innerHTML = `
  <div class="page-head"><div><h1>🔤 Языки Telegram</h1>
    <p>Свой язык интерфейса для Android, iPhone и компьютера: замена букв на красивые символы и/или переписывание
    нейросетью по описанию. Плейсхолдеры (%1$s, {count}, **…) защищены. Программа может сама зайти на translations.telegram.org и создать язык.</p></div></div>
  <div class="grid cols-side-r">
    <div class="stack">
      <div class="card"><h3>1 · Платформы и исходник</h3>
        <div class="chips" id="lgPlat"></div>
        <div class="kv3" style="margin-top:12px">
          <label class="field">Исходный язык<select id="lgSrc"><option value="ru">Русский (ru)</option><option value="en">English (en)</option>
            <option value="uk">Українська (uk)</option><option value="be">Беларуская (be)</option><option value="kk">Қазақ (kk)</option></select></label>
          <label class="field">Фильтр ключей (regex)<input type="text" id="lgFilter" placeholder="напр. Chat|Message — пусто = все"></label>
          <label class="field">Лимит строк для ИИ<input type="number" id="lgLimit" value="0" min="0"></label>
        </div>
        <label class="check small" style="margin-top:8px"><input type="checkbox" id="lgRest" checked> остальные строки — заменой символов (иначе исходник)</label>
      </div>
      <div class="card"><h3>2 · Как менять текст</h3>
        <div class="seg" id="lgMode"><button data-v="charmap" class="on">🔣 Замена символов</button><button data-v="ai">🧠 Нейросеть по описанию</button><button data-v="both">✨ ИИ + символы</button></div>
        <div id="lgMapBox" style="margin-top:12px">
          <div class="muted small" style="margin-bottom:6px">Наборы замен (можно несколько, кириллица и латиница отдельно):</div>
          <div class="chips" id="lgPresets"></div>
          <label class="field" style="margin-top:10px"><span>Свои замены — по одной на строку: <code>а=ᥲ</code>, <code>о=᥆</code>, можно слоги <code>ой=ꭷ</code></span>
            <textarea id="lgCustom" rows="4" placeholder="а=ᥲ\nе=ᥱ\nо=♡"></textarea></label>
        </div>
        <div id="lgAiBox" style="margin-top:12px" hidden>
          <label class="field">Описание стиля языка
            <textarea id="lgDesc" rows="4" placeholder="Например: милый язык как у котика — мяукающие слова, ласковые уменьшительные, в конце кнопок ♡; или: язык в стиле дворянина XIX века"></textarea></label>
          <div class="kv" style="margin-top:8px">
            <label class="field">Язык результата<input type="text" id="lgTarget" value="русский"></label>
            <label class="field">Примеры (необязательно)<input type="text" id="lgEx" placeholder="Чаты → Мурчатики"></label>
          </div>
        </div>
        <div class="row" style="margin-top:12px"><button class="btn" id="lgPrev" data-busy="Генерирую…">👁 Предпросмотр</button>
          <span class="muted small">Предпросмотр ИИ тратит 1 запрос.</span></div>
      </div>
      <div class="card"><h3>3 · Название и создание</h3>
        <div class="kv3">
          <label class="field">Название<input type="text" id="lgName" placeholder="Мурчащий"></label>
          <label class="field">Название на самом языке<input type="text" id="lgNative" placeholder="ᥖᥙρчᥲщᥙй"></label>
          <label class="field">Короткое имя (ссылка)<input type="text" id="lgCode" placeholder="murr"></label>
        </div>
        <div class="kv" style="margin-top:10px">
          <label class="field">Базовый язык на платформе<select id="lgBase"><option value="ru">ru</option><option value="en">en</option><option value="uk">uk</option></select></label>
          <label class="check" style="align-self:end"><input type="checkbox" id="lgUpload"> сразу загрузить на translations.telegram.org</label>
        </div>
        <div class="help" style="margin-top:10px">Строки берутся прямо из Telegram (нужен вход в «ИИ и аккаунт»). Файлы для Desktop можно подключить без сайта:
          в Telegram Desktop открой Настройки → зажми <b>Alt+Shift</b> и кликни «Язык» → выбери <code>lang.strings</code>.
          Загрузка на сайт открывает браузер: один раз подтверди вход в приложении Telegram.</div>
        <div class="row end"><button class="btn primary" id="lgBuild">🚀 Создать язык</button></div>
      </div>
    </div>
    <div class="stack">
      <div class="card"><h3>👁 Предпросмотр <span class="hint" id="lgPrevInfo"></span></h3>
        <div class="seg" id="lgPrevPlat" style="margin-bottom:12px"></div>
        <div id="lgMock" style="display:flex;justify-content:center"></div>
        <div class="sep" style="margin:12px 0"></div>
        <div class="lang-prev" id="lgPrevList"></div>
      </div>
      <div class="card"><h3>🧪 Проверить строку</h3>
        <textarea id="lgTry" rows="2">Удалить %1$s сообщений у {user}?</textarea>
        <pre class="out" id="lgTryOut"></pre>
      </div>
    </div>
  </div>`;

  const plat = $("#lgPlat");
  for (const [k, v] of Object.entries(S.platforms)) {
    const on = (saved.platforms || ["android", "ios", "tdesktop"]).includes(k);
    const c = h(`<span class="chip ${on ? "on" : ""}" data-v="${k}">${esc(v)}</span>`);
    c.onclick = () => c.classList.toggle("on");
    plat.append(c);
  }
  const pre = $("#lgPresets");
  if (saved.presets) S.presets = new Set(saved.presets);
  for (const [k, v] of Object.entries(S.fonts)) {
    const c = h(`<span class="chip ${S.presets.has(k) ? "on" : ""}" title="${k}">${esc(v.label)}</span>`);
    c.onclick = () => { S.presets.has(k) ? S.presets.delete(k) : S.presets.add(k); c.classList.toggle("on"); livePreview(); };
    pre.append(c);
  }
  $$("#lgMode button").forEach((b) => (b.onclick = () => {
    $$("#lgMode button").forEach((x) => x.classList.toggle("on", x === b));
    S.mode = b.dataset.v;
    $("#lgAiBox").hidden = S.mode === "charmap";
    $("#lgMapBox").hidden = S.mode === "ai";
    livePreview();
  }));
  const pp = $("#lgPrevPlat");
  for (const k of ["android", "ios", "tdesktop"]) {
    const b = h(`<button data-v="${k}" class="${k === S.platform ? "on" : ""}">${k}</button>`);
    b.onclick = () => { $$("button", pp).forEach((x) => x.classList.toggle("on", x === b)); S.platform = k; preview(); };
    pp.append(b);
  }
  for (const id of ["lgCustom", "lgName", "lgNative", "lgCode", "lgDesc"]) {
    if (saved[id] !== undefined) $("#" + id).value = saved[id];
  }
  $("#lgCustom").oninput = livePreview;
  $("#lgTry").oninput = livePreview;
  $("#lgPrev").onclick = (e) => busy(e.currentTarget, () => preview(true));
  $("#lgBuild").onclick = build;
  preview();
}

function form() {
  const f = {
    platforms: $$("#lgPlat .chip.on").map((c) => c.dataset.v),
    lang_code: $("#lgSrc").value, key_filter: $("#lgFilter").value, limit: +$("#lgLimit").value,
    rest_charmap: $("#lgRest").checked, mode: S.mode,
    presets: S.mode === "ai" ? [] : [...S.presets], custom_map: S.mode === "ai" ? "" : $("#lgCustom").value,
    description: $("#lgDesc").value, target_lang: $("#lgTarget").value, examples: $("#lgEx").value,
    name: $("#lgName").value, native_name: $("#lgNative").value, code: $("#lgCode").value, base: $("#lgBase").value,
    upload: $("#lgUpload").checked,
  };
  store.set("lang:form", { ...f, presets: [...S.presets], lgCustom: $("#lgCustom").value, lgName: f.name, lgNative: f.native_name, lgCode: f.code, lgDesc: f.description });
  return f;
}

const livePreview = debounce(() => { if (S.mode !== "ai") preview(); tryString(); }, 250);

async function tryString() {
  const f = form();
  const r = await api("/api/lang/preview", { ...f, mode: "charmap", texts: { s: $("#lgTry").value } });
  $("#lgTryOut").textContent = r.result.s;
}

async function preview(useAI = false) {
  const f = form();
  const mode = useAI ? S.mode : "charmap";
  const r = await api("/api/lang/preview", { ...f, platform: S.platform, mode });
  $("#lgPrevInfo").textContent = Object.keys(r.source).length + " строк"
    + (S.mode !== "charmap" && !useAI ? " · для ИИ нажми «Предпросмотр»" : "");
  $("#lgPrevList").innerHTML = Object.entries(r.result).map(([k, v]) => `<div class="k" title="${esc(k)}">${esc(r.source[k])}</div><div>${esc(v)}</div>`).join("");
  const t = (keys, def) => { for (const k of keys) if (r.result[k]) return r.result[k]; return def; };
  $("#lgMock").innerHTML = `<div class="lang-mock">
    <div class="h">${esc(t(["Chats", "DialogList.Title", "lng_dlg_filter"], "Чаты"))}</div>
    <div class="it"><span>${esc(t(["SavedMessages", "DialogList.SavedMessages", "lng_saved_messages"], "Избранное"))}</span><small>12:04</small></div>
    <div class="it"><span>${esc(t(["Contacts", "Contacts.Title", "lng_menu_contacts"], "Контакты"))}</span><small>${esc(t(["Online", "Presence.online", "lng_status_online"], "в сети"))}</small></div>
    <div class="it"><span>${esc(t(["Settings", "Settings.Title", "lng_settings_title"], "Настройки"))}</span><small>›</small></div>
    <div class="it"><span>${esc(t(["Reply", "Conversation.ContextMenuReply", "lng_context_reply_msg"], "Ответить"))}</span><small>${esc(t(["Forward", "Conversation.ContextMenuForward", "lng_context_forward_msg"], "Переслать"))}</small></div>
    <div class="in">${esc(t(["TypeMessage", "Conversation.InputTextPlaceholder", "lng_message_ph"], "Сообщение"))}</div></div>`;
  tryString();
}

async function build() {
  const f = form();
  if (!f.platforms.length) return toast("Выбери хотя бы одну платформу", "err");
  if (!f.code) return toast("Укажи короткое имя (латиница) — это часть ссылки t.me/setlanguage/…", "err");
  if (f.mode !== "charmap" && !f.limit && !f.key_filter && !confirm("ИИ перепишет ВСЕ строки (тысячи) — это может занять долго. Продолжить?")) return;
  await busy($("#lgBuild"), async () => {
    const { job } = await api("/api/lang/build", f);
    await runJob(job, "Создание языка", (r) => `
      <div class="links">${linkify(r.zip, "📦 Все файлы")}${Object.entries(r.files).map(([k, v]) => linkify(v, k)).join("")}</div>
      ${r.link ? `<div>Ссылка на язык: ${linkify(r.link)}</div>` : `<div class="muted small">Ссылка t.me/setlanguage/${esc(r.code)} заработает после загрузки на translations.telegram.org.</div>`}
      ${r.upload ? `<pre class="out">${esc(JSON.stringify(r.upload.platforms, null, 1))}</pre>` : ""}`);
  });
}
