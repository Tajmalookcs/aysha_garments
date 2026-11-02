(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const wait = (ms) => new Promise((r) => setTimeout(r, reduce ? Math.min(ms, 350) : ms));

  /* ---------- Sample data (placeholders only) ---------- */
  const PRODUCTS = [
    { id: 1, name: "Quilt, double", price: 4200, rate: 18, further: 4 },
    { id: 2, name: "Cushion, 16 inch", price: 650, rate: 18, further: 4 },
    { id: 3, name: "Pillow, standard", price: 900, rate: 18, further: 4 },
    { id: 4, name: "Sleeping bag", price: 5400, rate: 18, further: 4 },
  ];
  const RECENT = [
    ["AG-000014", "Sample Textile Mills", "Registered", 128400, "wait", "Waiting to send"],
    ["AG-000013", "Walk-in buyer", "Unregistered", 5208, "wait", "Waiting to send"],
    ["AG-000012", "Sample Weaving Co.", "Registered", 92040, "ok", "Accepted"],
    ["AG-000011", "Sample Home Textiles", "Registered", 214760, "ok", "Accepted"],
    ["AG-000010", "Walk-in buyer", "Unregistered", 3224, "ok", "Accepted"],
  ];
  const ICON = { ok: "bi-check-circle-fill", wait: "bi-clock-fill", bad: "bi-x-circle-fill" };

  const rs = (paisa) => "Rs " + (paisa / 100).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const toPaisa = (v) => Math.round((parseFloat(v) || 0) * 100);

  /* ---------- Quilt pattern on the login screen ---------- */
  function buildQuilt() {
    const svg = $("#quilt");
    const step = 100, w = 800, h = 900;
    let lines = "", masks = "", i = 0;
    for (let c = -h; c <= w; c += step) {
      const d1 = `M${c} 0 L${c + h} ${h}`;
      const d2 = `M${c + h} 0 L${c} ${h}`;
      [d1, d2].forEach((d) => {
        lines += `<path class="q-line" d="${d}"/>`;
        masks += `<path class="q-reveal" pathLength="1" d="${d}" style="animation-delay:${(i++ * 0.05).toFixed(2)}s"/>`;
      });
    }
    const seam = "M-20 650 L150 480 L250 580 L450 380 L550 480 L820 210";
    svg.innerHTML =
      `<defs><mask id="m1" maskUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}">${masks}</mask>` +
      `<mask id="m2" maskUnits="userSpaceOnUse" x="-40" y="0" width="${w + 80}" height="${h}"><path class="q-thread-reveal" pathLength="1" d="${seam}"/></mask></defs>` +
      `<g mask="url(#m1)">${lines}</g>` +
      `<g mask="url(#m2)"><path class="q-thread" d="${seam}"/></g>` +
      `<g class="q-needle" style="offset-path:path('${seam}')"><rect x="-26" y="-1.8" width="52" height="3.6" rx="1.8" fill="#fff"/></g>`;
  }

  /* ---------- Screens ---------- */
  async function showLoading(texts, each) {
    const box = $("#loading"), t = $("#loadingText");
    box.hidden = false;
    for (const text of texts) { t.textContent = text; await wait(each); }
    box.hidden = true;
  }
  function go(view) {
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("is-active", v.id === view));
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("is-active", n.dataset.go === view));
    window.scrollTo(0, 0);
  }
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await showLoading(["Checking your login", "Opening your invoices"], 850);
    $("#login").classList.remove("is-active");
    $("#app").classList.add("is-active");
  });
  document.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => go(b.dataset.go)));

  /* ---------- Dashboard ---------- */
  function renderRecent() {
    $("#recent").innerHTML = RECENT.map((r) =>
      `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td class="text-end num">${rs(r[3] * 100)}</td>` +
      `<td><span class="status ${r[4]}"><i class="bi ${ICON[r[4]]}"></i>${r[5]}</span></td></tr>`).join("");
    const n = RECENT.filter((r) => r[4] === "wait").length;
    $("#dashLine").textContent = n === 1 ? "1 invoice is waiting to reach FBR" : `${n} invoices are waiting to reach FBR`;
  }

  /* ---------- Connection (preview toggle) ---------- */
  let online = true;
  $("#net").addEventListener("click", () => {
    online = !online;
    const b = $("#net");
    b.classList.toggle("is-off", !online);
    b.querySelector("i").className = online ? "bi bi-wifi" : "bi bi-wifi-off";
    b.querySelector("span").textContent = online ? "Online" : "Offline: invoices will wait";
    $("#save").textContent = online ? "Save and send to FBR" : "Save invoice";
  });

  /* ---------- Invoice lines ---------- */
  let nextId = 1;
  const lines = [];
  function addLine(productId) {
    lines.push({ id: nextId++, product: productId || 1, unit: "piece", qty: 1, perLot: 50, discount: 0 });
    renderLines();
  }
  function renderLines() {
    $("#lines").innerHTML = lines.map((l) => {
      const opts = PRODUCTS.map((p) => `<option value="${p.id}" ${p.id === l.product ? "selected" : ""}>${p.name}</option>`).join("");
      const lot = l.unit === "lot"
        ? `<div class="lot-pieces"><label class="form-label" for="pl${l.id}">Pieces in each lot</label><input class="form-control num" id="pl${l.id}" data-l="${l.id}" data-f="perLot" type="number" min="1" value="${l.perLot}"></div>`
        : "";
      return `<div class="line">
        <div class="f-product"><label class="form-label" for="pr${l.id}">Product</label><select class="form-select" id="pr${l.id}" data-l="${l.id}" data-f="product">${opts}</select></div>
        <div><label class="form-label" for="un${l.id}">Sold by</label><select class="form-select" id="un${l.id}" data-l="${l.id}" data-f="unit"><option value="piece" ${l.unit === "piece" ? "selected" : ""}>Piece</option><option value="lot" ${l.unit === "lot" ? "selected" : ""}>Lot</option></select></div>
        <div><label class="form-label" for="qt${l.id}">Quantity</label><input class="form-control num" id="qt${l.id}" data-l="${l.id}" data-f="qty" type="number" min="1" value="${l.qty}"></div>
        <div><label class="form-label" for="dp${l.id}">Price per piece</label><input class="form-control num" id="dp${l.id}" value="${PRODUCTS.find((p) => p.id === l.product).price}" readonly></div>
        <div><label class="form-label" for="dc${l.id}">Discount</label><input class="form-control num" id="dc${l.id}" data-l="${l.id}" data-f="discount" type="number" min="0" value="${l.discount}"></div>
        <button class="rm" type="button" data-rm="${l.id}" aria-label="Remove this item" ${lines.length === 1 ? "disabled" : ""}><i class="bi bi-x-lg"></i></button>
        ${lot}
        <div class="line-meta"><span id="meta${l.id}"></span><strong id="amt${l.id}"></strong></div>
      </div>`;
    }).join("");
    calc();
  }
  function calc() {
    const reg = $("#buyer").value === "reg";
    let excl = 0, st = 0, ft = 0, disc = 0;
    lines.forEach((l) => {
      const p = PRODUCTS.find((x) => x.id === l.product);
      const pieces = (parseFloat(l.qty) || 0) * (l.unit === "lot" ? (parseFloat(l.perLot) || 0) : 1);
      const v = Math.round(pieces * p.price * 100);
      const s = Math.round(v * p.rate / 100);
      const f = reg ? 0 : Math.round(v * p.further / 100);
      const d = toPaisa(l.discount);
      excl += v; st += s; ft += f; disc += d;
      const meta = $("#meta" + l.id), amt = $("#amt" + l.id);
      if (meta) meta.textContent = `${pieces.toLocaleString("en-PK")} ${pieces === 1 ? "piece" : "pieces"}, HS 0000.0000, sample rate ${p.rate}%`;
      if (amt) amt.textContent = rs(v + s + f - d);
    });
    $("#tExcl").textContent = rs(excl);
    $("#tST").textContent = rs(st);
    $("#tFT").textContent = rs(ft);
    $("#tDisc").textContent = "- " + rs(disc);
    $("#tGrand").textContent = rs(excl + st + ft - disc);
    const foreign = $("#buyer").value === "foreign";
    $("#exportNote").hidden = !foreign;
  }
  $("#lines").addEventListener("input", (e) => {
    const t = e.target, l = lines.find((x) => x.id === +t.dataset.l);
    if (!l) return;
    const f = t.dataset.f;
    if (f === "product") { l.product = +t.value; renderLines(); }
    else if (f === "unit") { l.unit = t.value; renderLines(); }
    else { l[f] = t.value; calc(); }
  });
  $("#lines").addEventListener("click", (e) => {
    const b = e.target.closest("[data-rm]");
    if (!b) return;
    lines.splice(lines.findIndex((x) => x.id === +b.dataset.rm), 1);
    renderLines();
  });
  $("#addLine").addEventListener("click", () => addLine(2));
  $("#buyer").addEventListener("change", calc);

  /* ---------- Save: shows how the invoice moves through the steps ---------- */
  function mark(upto) {
    const order = ["saved", "checked", "accepted"];
    document.querySelectorAll("#track li").forEach((li) =>
      li.classList.toggle("done", order.indexOf(li.dataset.s) <= order.indexOf(upto)));
  }
  $("#save").addEventListener("click", async () => {
    const save = $("#save"), res = $("#result");
    const foreign = $("#buyer").value === "foreign";
    res.hidden = true; mark("none");
    save.disabled = true;
    const total = $("#tGrand").textContent;
    if (!online || foreign) {
      await showLoading(["Saving on this computer"], 900);
      mark("saved");
      res.innerHTML = foreign
        ? "Saved. This export invoice stays here until FBR's rules for foreign buyers are confirmed."
        : "Saved. It will go to FBR when the internet returns, and can only print as a Pending FBR copy until then.";
    } else {
      await showLoading(["Saving on this computer", "Checking with FBR", "Getting the IRN"], 750);
      mark("accepted");
      res.innerHTML = "Accepted in this preview. Nothing was sent to FBR.<br>Sample IRN: <code>0000000DI0000000000015</code>";
      RECENT.unshift(["AG-000015", $("#buyer").selectedOptions[0].textContent.replace(/ \(.*/, ""), $("#buyer").selectedOptions[0].textContent.match(/\((.*)\)/)[1], Math.round(parseFloat(total.replace(/[^\d.]/g, ""))), "ok", "Accepted"]);
      renderRecent();
    }
    res.hidden = false;
    save.disabled = false;
  });

  /* ---------- Start ---------- */
  buildQuilt();
  renderRecent();
  $("#date").valueAsDate = new Date();
  addLine(1);
})();
