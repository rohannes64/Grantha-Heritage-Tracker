import { getJSON, el, fmt } from "./common.js";

const explorer = document.getElementById("lang-explorer");
const langBtns = document.getElementById("lang-chips");
const langSheet = document.getElementById("lang-sheet");

if (explorer && langBtns && langSheet) {
  getJSON("data/facts.json").then((facts) => {
    const langs = (facts.corpus && facts.corpus.by_language) || [];
    const groups = facts.groups || [];
    if (!langs.length) return;

    const showLang = (item) => {
      for (const b of langBtns.querySelectorAll("button")) {
        b.setAttribute("aria-pressed", String(b.dataset.lang === item.lang));
      }
      const retention = item.harvested ? item.usable / item.harvested : null;
      const groupShares = groups.map((g) => {
        const share = g.languages && g.languages[item.lang];
        return `Group ${g.group + 1} (${g.majority_subject}): ${share != null ? fmt.p(share, 1) : "n/a"}`;
      }).join(" · ");

      langSheet.replaceChildren(
        el("div", {}, el("dt", { text: "Language" }), el("dd", { text: `${item.name} (${item.lang})` })),
        el("div", {}, el("dt", { text: "Harvested / Usable" }), el("dd", { class: "num", text: `${fmt.n(item.usable)} of ${fmt.n(item.harvested)} (${fmt.p(retention, 1)})` })),
        el("div", {}, el("dt", { text: "Median OCR confidence" }), el("dd", { class: "num", text: `${fmt.f(item.median_conf, 1)} of 100` })),
        el("div", {}, el("dt", { text: "Share of each topic group" }), el("dd", { text: groupShares || "n/a" }))
      );
    };

    langBtns.replaceChildren(...langs.map((item) => el("button", {
      type: "button",
      class: "chip",
      "data-lang": item.lang,
      "aria-pressed": "false",
      text: item.name,
      onclick: () => showLang(item),
    })));
    showLang(langs[0]);
  }).catch(() => {
    langSheet.replaceChildren(el("p", { class: "ink-2", text: "Language breakdown could not be loaded." }));
  });
}

for (const fig of document.querySelectorAll(".impact-video")) {
  const video = fig.querySelector("video");
  const bar = fig.querySelector(".video-controls");
  if (!video || !bar) continue;

  const playBtn = el("button", {
    type: "button",
    class: "chip",
    "aria-pressed": "true",
    text: "Pause",
    onclick: () => {
      if (video.paused) {
        video.play().catch(() => {});
        playBtn.textContent = "Pause";
        playBtn.setAttribute("aria-pressed", "true");
      } else {
        video.pause();
        playBtn.textContent = "Play";
        playBtn.setAttribute("aria-pressed", "false");
      }
    },
  });

  const speeds = [0.5, 1, 1.5].map((spd) => el("button", {
    type: "button",
    class: "chip",
    "aria-pressed": String(spd === 1),
    text: `${spd}×`,
    onclick: () => {
      video.playbackRate = spd;
      for (const b of bar.querySelectorAll("[data-spd]")) {
        b.setAttribute("aria-pressed", String(Number(b.dataset.spd) === spd));
      }
    },
  }));
  speeds.forEach((b, i) => { b.dataset.spd = String([0.5, 1, 1.5][i]); });
  bar.replaceChildren(playBtn, ...speeds);
}
