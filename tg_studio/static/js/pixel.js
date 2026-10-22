import { $, $$, api, busy, esc, h, linkify, pickImages, store, toast } from "./api.js";

const S = { mode: "image", gallery: store.get("pixel:gallery", []), source: null };

export async function initPixel(root) {
  const meta = await api("/api/pixel/meta");
  root.innerHTML = `
  <div class="page-head"><div><h1>👾 Пиксельные GIF-эмодзи</h1>
    <p>Пиши промпт — нейросеть рисует, программа превращает в пиксель-арт и анимирует (блёстки, прыжок, пульс, радуга…).
    На выходе GIF, WEBM 100×100 для эмодзи и TGS — вектор с идеально чёткими пикселями.</p></div></div>
  <div class="grid cols-side">
    <div class="stack">
      <div class="card"><h3>✏️ Промпт</h3>
        <textarea id="pxPrompt" rows="3" placeholder="розовый бантик с жемчугом / маленький призрак с сердечком / клубничное молоко"></textarea>
        <div class="seg" id="pxMode" style="margin-top:10px">
          <button data-v="image" class="on" title="Нейросеть-художник рисует → пикселизация">🎨 ИИ-художник</button>
          <button data-v="ai" title="Текстовая нейросеть рисует сетку пикселей">🧠 ИИ-пиксели</button>
          <button data-v="procedural" title="Без интернета">📦 Шаблоны</button>
          <button data-v="file" title="Своя картинка → пиксель-арт">🖼 Из картинки</button>
        </div>
        <div id="pxSpriteBox" class="chips" style="margin-top:10px" hidden></div>
        <div id="pxFileBox" style="margin-top:10px" hidden><button class="btn small" id="pxPick">Выбрать картинку</button> <span id="pxFileName" class="muted small"></span></div>
      </div>
      <div class="card"><h3>🎬 Анимация</h3>
        <div class="chips" id="pxAnim"></div>
        <div class="stack" style="gap:6px;margin-top:12px">
          <div class="slider-row"><span>Размер, пикс.</span><input type="range" id="pxSize" min="12" max="48" step="4" value="24"><output>24</output></div>
          <div class="slider-row"><span>Кадров</span><input type="range" id="pxFrames" min="2" max="30" value="12"><output>12</output></div>
          <div class="slider-row"><span>FPS</span><input type="range" id="pxFps" min="2" max="30" value="10"><output>10</output></div>
          <div class="slider-row"><span>Цветов</span><input type="range" id="pxColors" min="2" max="32" value="12"><output>12</output></div>
        </div>
        <div class="row" style="margin-top:8px"><label class="check small"><input type="checkbox" id="pxOutline" checked> тёмный контур</label>
          <label class="field" style="width:120px">Seed<input type="number" id="pxSeed" placeholder="случайно"></label></div>
        <div class="row end"><button class="btn primary" id="pxGo" data-busy="Рисую…">✨ Сгенерировать</button></div>
      </div>
    </div>
    <div class="stack">
      <div class="card"><h3>🖼 Результат</h3>
        <div class="row" style="align-items:flex-start;gap:20px">
          <img class="gif-big" id="pxOut" alt="">
          <div class="stack" style="flex:1;min-width:220px">
            <div class="links" id="pxLinks"></div>
            <div class="row"><button class="btn small" id="pxAgain" data-busy="…">🎲 Ещё вариант</button>
              <button class="btn small" id="pxToEmoji">➕ На полотно эмодзи</button></div>
            <div class="help">Готовая GIF уже лежит в библиотеке — её можно ставить в композитор пака.
              Для загрузки в Telegram используй <b>.webm</b> (видео-эмодзи) или <b>.tgs</b> (вектор).</div>
          </div>
        </div>
      </div>
      <div class="card"><h3>✨ Галерея</h3><div class="gallery" id="pxGallery"></div></div>
    </div>
  </div>`;

  const sb = $("#pxSpriteBox");
  meta.sprites.forEach((s, i) => {
    const c = h(`<span class="chip ${i === 0 ? "on" : ""}" data-v="${s}">${s}</span>`);
    c.onclick = () => { $$(".chip", sb).forEach((x) => x.classList.toggle("on", x === c)); };
    sb.append(c);
  });
  const ab = $("#pxAnim");
  Object.entries(meta.animations).forEach(([k, v]) => {
    const c = h(`<span class="chip ${k === "sparkle" ? "on" : ""}" data-v="${k}">${esc(v)}</span>`);
    c.onclick = () => { $$(".chip", ab).forEach((x) => x.classList.toggle("on", x === c)); };
    ab.append(c);
  });
  $$("#pxMode button").forEach((b) => (b.onclick = () => {
    $$("#pxMode button").forEach((x) => x.classList.toggle("on", x === b));
    S.mode = b.dataset.v;
    $("#pxSpriteBox").hidden = S.mode !== "procedural";
    $("#pxFileBox").hidden = S.mode !== "file";
  }));
  $$(".slider-row input", root).forEach((i) => (i.oninput = () => (i.nextElementSibling.textContent = i.value)));
  $("#pxPick").onclick = async () => { const r = await pickImages({ multi: false }); if (r?.length) { S.source = r[0]; $("#pxFileName").textContent = r[0]; } };
  $("#pxGo").onclick = (e) => busy(e.currentTarget, () => generate(false));
  $("#pxAgain").onclick = (e) => busy(e.currentTarget, () => generate(true));
  $("#pxToEmoji").onclick = () => {
    if (!S.last) return;
    toast("Открой «Эмодзи-паки» и кликни по GIF в библиотеке — он уже там ✓", "ok");
    window.dispatchEvent(new CustomEvent("tgs:goto", { detail: "emoji" }));
  };
  drawGallery();
}

async function generate(again) {
  const prompt = $("#pxPrompt").value.trim();
  if (["image", "ai"].includes(S.mode) && !prompt) return toast("Напиши промпт", "err");
  if (S.mode === "file" && !S.source) return toast("Выбери картинку", "err");
  const body = {
    prompt, mode: S.mode === "file" ? "procedural" : S.mode,
    sprite: $("#pxSpriteBox .chip.on")?.dataset.v, animation: $("#pxAnim .chip.on")?.dataset.v,
    size: +$("#pxSize").value, frames: +$("#pxFrames").value, fps: +$("#pxFps").value, colors: +$("#pxColors").value,
    outline: $("#pxOutline").checked, seed: again || !$("#pxSeed").value ? null : +$("#pxSeed").value,
    file: S.mode === "file" ? S.source : null,
  };
  const r = await api("/api/pixel/generate", body);
  S.last = r;
  $("#pxOut").src = r.files.gif + "?t=" + Date.now();
  $("#pxSeed").placeholder = "seed " + r.seed;
  $("#pxLinks").innerHTML = Object.entries(r.files).map(([k, v]) => linkify(v, k.toUpperCase())).join("");
  S.gallery.unshift({ gif: r.files.gif, files: r.files, prompt });
  S.gallery = S.gallery.slice(0, 40);
  store.set("pixel:gallery", S.gallery);
  drawGallery();
}

function drawGallery() {
  const g = $("#pxGallery");
  g.innerHTML = S.gallery.length ? "" : `<span class="muted">Здесь будут твои гифки</span>`;
  for (const it of S.gallery) {
    const im = h(`<img src="${it.gif}" title="${esc(it.prompt || "")}">`);
    im.onclick = () => { $("#pxOut").src = it.gif; $("#pxLinks").innerHTML = Object.entries(it.files).map(([k, v]) => linkify(v, k.toUpperCase())).join(""); };
    g.append(im);
  }
}
