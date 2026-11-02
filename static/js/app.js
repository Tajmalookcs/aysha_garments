(function () {
  "use strict";

  /* Quilt pattern on the login and setup screens */
  const svg = document.getElementById("quilt");
  if (svg) {
    const step = 100, w = 800, h = 900;
    let lines = "", masks = "", i = 0;
    for (let c = -h; c <= w; c += step) {
      [`M${c} 0 L${c + h} ${h}`, `M${c + h} 0 L${c} ${h}`].forEach((d) => {
        lines += `<path class="q-line" d="${d}"/>`;
        masks += `<path class="q-reveal" pathLength="1" d="${d}" style="animation-delay:${(i++ * 0.05).toFixed(2)}s"/>`;
      });
    }
    const seam = "M-20 650 L150 480 L250 580 L450 380 L550 480 L820 210";
    svg.innerHTML =
      `<defs><mask id="m1" maskUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}">${masks}</mask>` +
      `<mask id="m2" maskUnits="userSpaceOnUse" x="-40" y="0" width="${w + 80}" height="${h}"><path class="q-thread-reveal" pathLength="1" d="${seam}"/></mask></defs>` +
      `<g mask="url(#m1)">${lines}</g><g mask="url(#m2)"><path class="q-thread" d="${seam}"/></g>` +
      `<g class="q-needle" style="offset-path:path('${seam}')"><rect x="-26" y="-1.8" width="52" height="3.6" rx="1.8" fill="#fff"/></g>`;
  }

  /* Stitching loader on form submit */
  const box = document.getElementById("loading"), text = document.getElementById("loadingText");
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented) return;
      text.textContent = form.dataset.loading;
      box.hidden = false;
    });
  });
  /* A page restored with the browser's Back button must not stay covered */
  window.addEventListener("pageshow", () => { box.hidden = true; });

  document.querySelectorAll("[data-autosubmit]").forEach((el) => {
    el.addEventListener("change", () => el.form.requestSubmit());
  });

  /* Real connection state */
  const net = document.getElementById("net");
  if (net) {
    const update = () => {
      const on = navigator.onLine;
      net.classList.toggle("is-off", !on);
      net.querySelector("i").className = on ? "bi bi-wifi" : "bi bi-wifi-off";
      net.querySelector("span").textContent = on ? "Online" : "Offline: you can keep saving";
    };
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    update();
  }
})();
