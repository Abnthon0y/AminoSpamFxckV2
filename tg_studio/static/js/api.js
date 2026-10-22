// Общие помощники: запросы к API, тосты, задачи с прогрессом, выбор картинок, цвета.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  // importNode: узел должен принадлежать основному документу (иначе input.click() не откроет диалог)
  return document.importNode(t.content, true).firstElementChild;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export async function api(path, body, method) {
  const opts = { method: method || (body === undefined ? "GET" : "POST"), headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  let data = null;
  try { data = await r.json(); } catch { /* пустой ответ */ }
  if (!r.ok) {
    const msg = data?.error || data?.detail || `Ошибка ${r.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export async function uploadFiles(fileList, url = "/api/upload") {
  const fd = new FormData();
  for (const f of fileList) fd.append("files", f);
  const r = await fetch(url, { method: "POST", body: fd });
  const data = await r.json();
  if (!r.ok) throw new Error(data?.error || data?.detail || "Не удалось загрузить");
  return data;
}

export function toast(msg, kind = "") {
  const el = h(`<div class="toast ${kind}">${esc(msg)}</div>`);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "err" ? 7000 : 3500);
}

/** Обёртка для кнопок: блокирует на время запроса и показывает ошибку. */
export async function busy(btn, fn) {
  const old = btn?.innerHTML;
  if (btn) { btn.disabled = true; btn.innerHTML = "⏳ " + (btn.dataset.busy || "Минутку…"); }
  try { return await fn(); }
  catch (e) { toast(e.message || String(e), "err"); console.error(e); }
  finally { if (btn) { btn.disabled = false; btn.innerHTML = old; } }
}

export function linkify(url, label) {
  return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label || url)}</a>`;
}

// ---------- фоновые задачи ----------
export function runJob(jobId, title, renderResult) {
  const modal = $("#jobModal");
  modal.hidden = false;
  $("#jobTitle").textContent = title;
  $("#jobResult").innerHTML = "";
  $("#jobBar").style.width = "0%";
  $("#jobWait").hidden = true;
  $("#jobClose").onclick = () => (modal.hidden = true);
  $("#jobContinue").onclick = () => api(`/api/jobs/${jobId}/continue`, {});
  return new Promise((resolve) => {
    const tick = async () => {
      let j;
      try { j = await api(`/api/jobs/${jobId}`); } catch (e) { setTimeout(tick, 1500); return; }
      $("#jobBar").style.width = `${Math.round(j.progress * 100)}%`;
      $("#jobMsg").textContent = j.message;
      $("#jobLog").textContent = j.log.join("\n");
      $("#jobWait").hidden = !j.waiting;
      $("#jobWaitText").textContent = j.waiting || "";
      if (j.status === "running") { setTimeout(tick, 900); return; }
      if (j.status === "done") {
        toast(`${title}: готово ✓`, "ok");
        if (renderResult) $("#jobResult").innerHTML = renderResult(j.result);
        modal.hidden = false;
      } else {
        toast(`${title}: ${j.message}`, "err");
      }
      resolve(j);
    };
    tick();
  });
}

// ---------- библиотека / выбор картинок ----------
export const library = {
  files: [],
  async refresh() { this.files = (await api("/api/library")).files; return this.files; },
};

export function pickImages({ multi = true, selected = [] } = {}) {
  return new Promise(async (resolve) => {
    const modal = $("#pickModal");
    const grid = $("#pickGrid");
    const sel = new Set(selected);
    const draw = () => {
      grid.innerHTML = library.files.length ? "" : `<div class="empty">Библиотека пуста — загрузи картинки ⬆</div>`;
      for (const f of library.files) {
        const el = h(`<div class="thumb ${sel.has(f.name) ? "sel" : ""}"><img loading="lazy" src="${f.url}">${f.animated ? '<span class="badge">GIF</span>' : ""}</div>`);
        el.onclick = () => {
          if (!multi) sel.clear();
          sel.has(f.name) ? sel.delete(f.name) : sel.add(f.name);
          draw();
        };
        grid.append(el);
      }
    };
    await library.refresh();
    draw();
    modal.hidden = false;
    $("#pickUpload").onchange = async (e) => {
      const res = await uploadFiles(e.target.files);
      res.files.forEach((f) => sel.add(f.name));
      await library.refresh();
      draw();
      e.target.value = "";
    };
    const close = (val) => { modal.hidden = true; resolve(val); };
    $("#pickOk").onclick = () => close([...sel]);
    $("[data-close]", modal).onclick = () => close(null);
  });
}

export function dropZone(el, onFiles) {
  el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("over"); });
  el.addEventListener("dragleave", () => el.classList.remove("over"));
  el.addEventListener("drop", (e) => {
    e.preventDefault();
    el.classList.remove("over");
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
  });
}

// ---------- цвет ----------
export const color = {
  toRgb(hex) {
    hex = hex.replace("#", "");
    if (hex.length === 3) hex = [...hex].map((c) => c + c).join("");
    return [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  },
  toHex([r, g, b]) {
    return "#" + [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
  },
  toHsl(hex) {
    let [r, g, b] = this.toRgb(hex).map((v) => v / 255);
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    let hh = 0, s = 0;
    const l = (mx + mn) / 2;
    if (mx !== mn) {
      const d = mx - mn;
      s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      hh = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      hh *= 60;
    }
    return [hh, s, l];
  },
  fromHsl(hh, s, l) {
    hh = ((hh % 360) + 360) % 360;
    s = Math.max(0, Math.min(1, s));
    l = Math.max(0, Math.min(1, l));
    const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs(((hh / 60) % 2) - 1)), m = l - c / 2;
    const [r, g, b] = hh < 60 ? [c, x, 0] : hh < 120 ? [x, c, 0] : hh < 180 ? [0, c, x] : hh < 240 ? [0, x, c] : hh < 300 ? [x, 0, c] : [c, 0, x];
    return this.toHex([(r + m) * 255, (g + m) * 255, (b + m) * 255]);
  },
  lum(hex) {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    const [r, g, b] = this.toRgb(hex).map(f);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  },
  contrast(a, b) {
    const [x, y] = [this.lum(a), this.lum(b)];
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  },
  /** hue: градусы, sat/light/contrast: -1..1 — как в Python adjust_color */
  adjust(hex, { hue = 0, sat = 0, light = 0, contrast = 0 } = {}) {
    let [hh, s, l] = this.toHsl(hex);
    hh += hue;
    s = sat < 0 ? s * (1 + sat) : s + (1 - s) * sat;
    l = light > 0 ? l + light * (1 - l) : l * (1 + light);
    l = 0.5 + (l - 0.5) * (1 + contrast);
    return this.fromHsl(hh, s, l);
  },
};

export function debounce(fn, ms = 350) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function download(name, text, type = "text/plain") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export const store = {
  get(k, d) { try { const v = localStorage.getItem("tgs:" + k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tgs:" + k, JSON.stringify(v)); } catch { /* приватный режим */ } },
};
