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
  /* The quantity goes to FBR in the product's unit, so the choices follow it. */
  const PACK_UNITS = ["SET PACK", "PAIR PACK", "PIECE PACK"];
  const soldByFor = (p, wanted) => {
    if (!p.kg) return wanted === "lot" ? "lot" : "piece";
    if (wanted === "kg" || wanted === "pack") return wanted;
    return p.pack_unit ? "pack" : "kg";
  };
  const defaultProduct = () => PRODUCTS.find((p) => p.kg) || PRODUCTS[0];

  let nextId = 1;
  const newLine = (d) => {
    const pid = d && product(d.product) ? +d.product : defaultProduct().id;
    return {
      id: nextId++,
      product: pid,
      sold_by: soldByFor(product(pid), d && d.sold_by),
      quantity: (d && d.quantity) || "1",
      kg: (d && d.kg) || "",
      pack_unit: (d && d.pack_unit) || product(pid).pack_unit || PACK_UNITS[0],
      pieces_per_lot: (d && d.pieces_per_lot) || "",
      price: (d && d.price) || product(pid).price,
      discount: (d && d.discount) || "0",
    };
  };
  const lines = [];
  /* The client knows one weight, not one for each line. Lines that go to FBR as one item share a total. */
  const kgTotals = {};
  const groupOf = (l) => product(l.product).kg_group;
  const kgGroups = () => {
    const seen = [];
    lines.filter((l) => l.sold_by === "pack").forEach((l) => {
      const found = seen.find((g) => g.key === groupOf(l));
      if (found) { if (!found.names.includes(product(l.product).name)) found.names.push(product(l.product).name); }
      else seen.push({ key: groupOf(l), names: [product(l.product).name] });
    });
    return seen;
  };
  const unitOptions = (l) => {
    const p = product(l.product);
    if (p.kg) {
      const current = l.sold_by === "kg" ? "KG" : l.pack_unit;
      return [...PACK_UNITS, "KG"].map((u) => `<option value="${u}" ${u === current ? "selected" : ""}>${u}</option>`).join("");
    }
    const uom = String(p.uom || "").trim();
    const piece = !uom || uom.toLowerCase() === "numbers, pieces, units" ? "Piece" : uom;
    return `<option value="piece" ${l.sold_by === "piece" ? "selected" : ""}>${esc(piece)}</option><option value="lot" ${l.sold_by === "lot" ? "selected" : ""}>Lot</option>`;
  };

  function render() {
    $("lines").innerHTML = lines.map((l) => {
      const opts = PRODUCTS.map((p) => `<option value="${p.id}" ${p.id === l.product ? "selected" : ""}>${esc(p.name)}</option>`).join("");
      const lot = l.sold_by === "lot"
        ? `<div class="lot-pieces"><label class="form-label" for="pl${l.id}">Pieces in each lot</label><input class="form-control num" id="pl${l.id}" data-l="${l.id}" data-f="pieces_per_lot" type="number" min="1" step="1" value="${esc(l.pieces_per_lot)}"></div>`
        : "";
      const discount = l.showDiscount || num(l.discount) > 0
        ? `<div class="line-discount"><label class="form-label" for="dc${l.id}">Discount</label><input class="form-control num" id="dc${l.id}" data-l="${l.id}" data-f="discount" type="number" min="0" step="0.01" value="${esc(l.discount)}"></div>`
        : `<button class="btn btn-link add-discount" type="button" data-disc="${l.id}"><i class="bi bi-plus-lg"></i> Discount</button>`;
      return `<div class="line">
        <div><label class="form-label" for="qt${l.id}">Qty</label><input class="form-control num" id="qt${l.id}" data-l="${l.id}" data-f="quantity" type="number" min="0" step="any" value="${esc(l.quantity)}"></div>
        <div><label class="form-label" for="un${l.id}">Unit</label><select class="form-select" id="un${l.id}" data-l="${l.id}" data-f="unit">${unitOptions(l)}</select></div>
        <div class="f-product"><label class="form-label" for="pr${l.id}">Product</label><select class="form-select" id="pr${l.id}" data-l="${l.id}" data-f="product">${opts}</select></div>
        <div><label class="form-label" for="dp${l.id}">Rate</label><input class="form-control num" id="dp${l.id}" data-l="${l.id}" data-f="price" type="number" min="0" step="0.01" value="${esc(l.price)}"></div>
        <button class="rm" type="button" data-rm="${l.id}" aria-label="Remove this item" ${lines.length === 1 ? "disabled" : ""}><i class="bi bi-x-lg"></i></button>
        ${lot}${discount}
        <div class="line-meta"><span id="meta${l.id}"></span><strong id="amt${l.id}"></strong></div>
      </div>`;
    }).join("");
    const groups = kgGroups();
    $("kgTotals").innerHTML = groups.map((g, i) => `<div class="kg-total"><label class="form-label" for="kgt${i}">Total KG${groups.length > 1 ? ": " + esc(g.names.join(", ")) : ""}</label><input class="form-control num" id="kgt${i}" data-kg="${esc(g.key)}" type="number" min="0" step="any" value="${esc(kgTotals[g.key] || "")}"></div>`).join("");
    calc();
  }

  /* On-screen totals only. The server works out the saved figures with Decimal. */
  function calc() {
    const kind = KINDS[$("buyer").value];
    let excl = 0, st = 0, ft = 0, disc = 0, kg = 0;
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
      kg += l.sold_by === "kg" ? pieces : 0;
      if (meta) meta.textContent = `Value ${rs(v)}, HS ${p.hs}, sales tax ${num(p.rate)}%`;
      if (amt) amt.textContent = rs(v + s + f + fed - d);
    });
    kgGroups().forEach((g) => { kg += num(kgTotals[g.key]); });
    $("tKgRow").style.display = kg ? "" : "none";
    $("tKg").textContent = kg.toLocaleString("en-PK") + " KG";
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
    if (f === "product") { l.product = +t.value; l.price = product(l.product).price; const p = product(l.product); l.sold_by = soldByFor(p, p.kg ? null : l.sold_by); l.pack_unit = p.pack_unit || l.pack_unit; render(); }
    else if (f === "unit") {
      if (t.value === "piece" || t.value === "lot") l.sold_by = t.value;
      else if (t.value === "KG") l.sold_by = "kg";
      else { l.sold_by = "pack"; l.pack_unit = t.value; }
      render();
    }
    else { l[f] = t.value; calc(); }
  });
  $("kgTotals").addEventListener("input", (e) => {
    if (e.target.dataset.kg) { kgTotals[e.target.dataset.kg] = e.target.value; calc(); }
  });
  $("lines").addEventListener("click", (e) => {
    const d = e.target.closest("[data-disc]");
    if (d) {
      lines.find((x) => x.id === +d.dataset.disc).showDiscount = true;
      render();
      $("dc" + d.dataset.disc).focus();
      return;
    }
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
      kg_total: l.sold_by === "pack" ? (kgTotals[groupOf(l)] || "") : "", pack_unit: l.pack_unit,
    })));
  });

  const initial = read("initial-lines");
  (Array.isArray(initial) && initial.length ? initial : [null]).forEach((d) => {
    const l = newLine(d);
    lines.push(l);
    if (d && l.sold_by === "pack") {
      const key = groupOf(l);
      if (d.kg_total !== undefined) kgTotals[key] = d.kg_total;
      else if (d.kg) kgTotals[key] = String(Math.round((num(kgTotals[key]) + num(d.kg)) * 10000) / 10000);
    }
  });
  render();
})();
