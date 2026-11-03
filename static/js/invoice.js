(function () {
  "use strict";
  const form = document.getElementById("invForm");
  if (!form) return;

  const read = (id) => JSON.parse(document.getElementById(id).textContent);
  const PRODUCTS = read("products-data");
  const KINDS = read("customers-data");
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const rs = (paisa) => "Rs " + (paisa / 100).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const num = (v) => parseFloat(v) || 0;
  const product = (id) => PRODUCTS.find((p) => p.id === +id);

  let nextId = 1;
  const newLine = (d) => {
    const pid = d && product(d.product) ? +d.product : PRODUCTS[0].id;
    return {
      id: nextId++,
      product: pid,
      sold_by: (d && d.sold_by) || "piece",
      quantity: (d && d.quantity) || "1",
      pieces_per_lot: (d && d.pieces_per_lot) || "",
      price: (d && d.price) || product(pid).price,
      discount: (d && d.discount) || "0",
    };
  };
  const lines = [];

  function render() {
    $("lines").innerHTML = lines.map((l) => {
      const opts = PRODUCTS.map((p) => `<option value="${p.id}" ${p.id === l.product ? "selected" : ""}>${esc(p.name)}</option>`).join("");
      const lot = l.sold_by === "lot"
        ? `<div class="lot-pieces"><label class="form-label" for="pl${l.id}">Pieces in each lot</label><input class="form-control num" id="pl${l.id}" data-l="${l.id}" data-f="pieces_per_lot" type="number" min="1" step="1" value="${esc(l.pieces_per_lot)}"></div>`
        : "";
      return `<div class="line">
        <div class="f-product"><label class="form-label" for="pr${l.id}">Product</label><select class="form-select" id="pr${l.id}" data-l="${l.id}" data-f="product">${opts}</select></div>
        <div><label class="form-label" for="un${l.id}">Sold by</label><select class="form-select" id="un${l.id}" data-l="${l.id}" data-f="sold_by"><option value="piece" ${l.sold_by === "piece" ? "selected" : ""}>Piece</option><option value="lot" ${l.sold_by === "lot" ? "selected" : ""}>Lot</option></select></div>
        <div><label class="form-label" for="qt${l.id}">Quantity</label><input class="form-control num" id="qt${l.id}" data-l="${l.id}" data-f="quantity" type="number" min="0" step="any" value="${esc(l.quantity)}"></div>
        <div><label class="form-label" for="dp${l.id}">Price per piece</label><input class="form-control num" id="dp${l.id}" data-l="${l.id}" data-f="price" type="number" min="0" step="0.01" value="${esc(l.price)}"></div>
        <div><label class="form-label" for="dc${l.id}">Discount</label><input class="form-control num" id="dc${l.id}" data-l="${l.id}" data-f="discount" type="number" min="0" step="0.01" value="${esc(l.discount)}"></div>
        <button class="rm" type="button" data-rm="${l.id}" aria-label="Remove this item" ${lines.length === 1 ? "disabled" : ""}><i class="bi bi-x-lg"></i></button>
        ${lot}
        <div class="line-meta"><span id="meta${l.id}"></span><strong id="amt${l.id}"></strong></div>
      </div>`;
    }).join("");
    calc();
  }

  /* On-screen totals only. The server works out the saved figures with Decimal. */
  function calc() {
    const kind = KINDS[$("buyer").value];
    let excl = 0, st = 0, ft = 0, disc = 0;
    lines.forEach((l) => {
      const p = product(l.product);
      const pieces = num(l.quantity) * (l.sold_by === "lot" ? num(l.pieces_per_lot) : 1);
      const v = Math.round(pieces * num(l.price) * 100);
      const d = Math.round(num(l.discount) * 100);
      const s = Math.round((v - d) * num(p.rate) / 100);
      const f = kind === "unregistered" ? Math.round((v - d) * num(p.further) / 100) : 0;
      const fed = Math.round((v - d) * num(p.fed) / 100);
      excl += v; st += s + fed; ft += f; disc += d;
      const meta = $("meta" + l.id), amt = $("amt" + l.id);
      if (meta) meta.textContent = `${pieces.toLocaleString("en-PK")} ${pieces === 1 ? "piece" : "pieces"}, HS ${p.hs}, rate ${num(p.rate)}%`;
      if (amt) amt.textContent = rs(v + s + f + fed - d);
    });
    $("tExcl").textContent = rs(excl);
    $("tST").textContent = rs(st);
    $("tFT").textContent = rs(ft);
    $("tDisc").textContent = "- " + rs(disc);
    $("tGrand").textContent = rs(excl + st + ft - disc);
    $("exportNote").hidden = kind !== "foreign";
  }

  $("lines").addEventListener("input", (e) => {
    const t = e.target, l = lines.find((x) => x.id === +t.dataset.l);
    if (!l) return;
    const f = t.dataset.f;
    if (f === "product") { l.product = +t.value; l.price = product(l.product).price; render(); }
    else if (f === "sold_by") { l.sold_by = t.value; render(); }
    else { l[f] = t.value; calc(); }
  });
  $("lines").addEventListener("click", (e) => {
    const b = e.target.closest("[data-rm]");
    if (!b) return;
    lines.splice(lines.findIndex((x) => x.id === +b.dataset.rm), 1);
    render();
  });
  $("addLine").addEventListener("click", () => { lines.push(newLine()); render(); });
  $("buyer").addEventListener("change", calc);
  form.addEventListener("submit", () => {
    $("offlineField").value = navigator.onLine ? "0" : "1";
    $("linesField").value = JSON.stringify(lines.map((l) => ({
      product: l.product, sold_by: l.sold_by, quantity: l.quantity,
      pieces_per_lot: l.pieces_per_lot, price: l.price, discount: l.discount,
    })));
  });

  const initial = read("initial-lines");
  (Array.isArray(initial) && initial.length ? initial : [null]).forEach((d) => lines.push(newLine(d)));
  render();
})();
