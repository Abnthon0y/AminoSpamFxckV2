import { $, api, busy, dropZone, h, library, linkify, toast, uploadFiles } from "./api.js";

export async function initLibrary(root) {
  root.innerHTML = `
  <div class="page-head"><div><h1>🗂️ Библиотека</h1>
    <p>Все загруженные и сгенерированные картинки — их можно использовать в любом разделе. Внизу — готовые архивы.</p></div></div>
  <div class="card"><div class="drop" id="libDrop">⬆ Перетащи картинки / GIF сюда или нажми</div>
    <div class="lib-grid" id="libGrid" style="margin-top:14px;max-height:none"></div></div>
  <div class="card" style="margin-top:16px"><h3>📦 Готовые архивы</h3><div class="links" id="libOut"></div></div>`;
  const drop = $("#libDrop");
  const add = async (files) => { await uploadFiles(files); toast("Загружено ✓", "ok"); draw(); };
  drop.onclick = () => { const i = h(`<input type="file" multiple accept="image/*">`); i.onchange = () => add(i.files); i.click(); };
  dropZone(drop, add);
  root.addEventListener("shown", draw);
  draw();
}

async function draw() {
  await library.refresh();
  const g = $("#libGrid");
  g.innerHTML = library.files.length ? "" : `<div class="empty">Пока пусто</div>`;
  for (const f of library.files) {
    const el = h(`<div class="thumb" title="${f.name} · ${f.w}×${f.h}"><img loading="lazy" src="${f.url}">
      ${f.animated ? '<span class="badge">GIF</span>' : ""}<button class="icon-btn x">🗑</button></div>`);
    el.querySelector(".x").onclick = (e) => busy(null, async () => {
      e.stopPropagation();
      await api(`/api/library/${encodeURIComponent(f.name)}`, undefined, "DELETE");
      draw();
    });
    el.onclick = () => window.open(f.url, "_blank");
    g.append(el);
  }
  const out = await api("/api/outputs");
  $("#libOut").innerHTML = out.items.map((i) => linkify(i.url, `${i.name} · ${(i.size / 1024).toFixed(0)} КБ`)).join("") || `<span class="muted">Ещё ничего не собрано</span>`;
}
