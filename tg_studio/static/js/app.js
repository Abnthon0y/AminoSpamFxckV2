import { $, $$, api } from "./api.js";
import { initThemes } from "./themes.js";
import { initLang } from "./lang.js";
import { initEmoji } from "./emoji.js";
import { initPixel } from "./pixel.js";
import { initStickers } from "./stickers.js";
import { initText } from "./text.js";
import { initLibrary } from "./library.js";
import { initSettings } from "./settings.js";

const pages = {
  themes: initThemes, lang: initLang, emoji: initEmoji, pixel: initPixel, stickers: initStickers,
  text: initText, library: initLibrary, settings: initSettings,
};
const inited = new Set();

function show(page) {
  $$(".nav button").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${page}`));
  if (!inited.has(page)) {
    inited.add(page);
    pages[page]($(`#page-${page}`));
  } else {
    $(`#page-${page}`).dispatchEvent(new CustomEvent("shown"));
  }
  location.hash = page;
}

$$(".nav button").forEach((b) => (b.onclick = () => show(b.dataset.page)));
window.addEventListener("tgs:goto", (e) => show(e.detail));

export async function refreshStatus() {
  try {
    const { settings, providers } = await api("/api/settings");
    const p = settings.ai.provider;
    $("#aiDot").className = "dot " + (p === "none" ? "off" : "on");
    $("#aiLabel").textContent = "ИИ: " + (providers[p]?.label.split(" —")[0] || p);
  } catch { /* сервер ещё стартует */ }
  try {
    const st = await api("/api/tg/status");
    $("#tgDot").className = "dot " + (st.authorized ? "on" : "off");
    $("#tgLabel").textContent = st.authorized ? `TG: ${st.name || st.username}` : "Telegram: не вошли";
  } catch { $("#tgLabel").textContent = "Telegram: —"; }
}
window.addEventListener("tgs:status", refreshStatus);

const start = location.hash.slice(1);
show(start in pages ? start : "themes");
refreshStatus();
