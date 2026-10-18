(function () {
  const csrf = document.querySelector('meta[name=csrf]').content;
  const $ = id => document.getElementById(id);
  const cart = {}; // id -> {id,name,price,stock,unit,qty}
  const cur = document.body.dataset.currency || 'Rs.';
  const fmt = n => cur + ' ' + Number(n).toLocaleString(undefined, {maximumFractionDigits: 2});
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  let timer;

  async function search(q) {
    const r = await fetch('/products/api/search?q=' + encodeURIComponent(q));
    if (!r.ok) return [];
    return r.json();
  }
  function renderResults(list) {
    const box = $('results');
    if (!list.length) { box.innerHTML = '<div class="empty w-100"><i class="bi bi-box"></i>No products found.</div>'; return; }
    box.innerHTML = list.map(p => `<button type="button" class="pos-item ${p.stock <= 0 ? 'disabled' : ''}" data-id="${p.id}">
      <div class="fw-semibold">${esc(p.name)}</div><div class="small text-muted">${esc(p.sku || p.barcode || '')}</div>
      <div class="d-flex justify-content-between mt-1"><span>${fmt(p.price)}</span>
      <span class="small ${p.low ? 'text-danger' : 'text-muted'}">${p.stock} ${esc(p.unit || '')}</span></div></button>`).join('');
    box.querySelectorAll('.pos-item').forEach((el, i) => el.addEventListener('click', () => add(list[i])));
  }
  function add(p, qty) {
    qty = qty || Number($('addQty').value) || 1;
    if (p.stock <= 0) return toast('Out of stock: ' + p.name, 'danger');
    const line = cart[p.id] || (cart[p.id] = {id: p.id, name: p.name, price: p.price, stock: p.stock, unit: p.unit, qty: 0});
    line.qty = Math.round((line.qty + qty) * 1000) / 1000;
    if (line.qty > p.stock) { line.qty = p.stock; toast('Only ' + p.stock + ' in stock for ' + p.name, 'warning'); }
    $('addQty').value = 1; renderCart();
  }
  function renderCart() {
    const lines = Object.values(cart);
    $('cartBody').innerHTML = lines.length ? lines.map(l => `<tr><td>${esc(l.name)}<div class="small text-muted">${fmt(l.price)} / ${esc(l.unit || '')}</div></td>
      <td><input type="number" class="form-control form-control-sm cart-qty" min="0.001" step="any" max="${l.stock}" value="${l.qty}" data-id="${l.id}"></td>
      <td class="num">${fmt(l.qty * l.price)}</td>
      <td><button type="button" class="btn btn-sm btn-outline-danger" data-rm="${l.id}" title="Remove"><i class="bi bi-x-lg"></i></button></td></tr>`).join('')
      : '<tr><td colspan="4" class="empty">Cart is empty. Search and add products.</td></tr>';
    $('cartBody').querySelectorAll('input[data-id]').forEach(i => i.addEventListener('change', () => {
      const l = cart[i.dataset.id]; let v = Number(i.value);
      if (!(v > 0)) v = 1; if (v > l.stock) { v = l.stock; toast('Only ' + l.stock + ' in stock.', 'warning'); }
      l.qty = v; renderCart();
    }));
    $('cartBody').querySelectorAll('[data-rm]').forEach(b => b.addEventListener('click', () => { delete cart[b.dataset.rm]; renderCart(); }));
    totals();
  }
  function totals() {
    const sub = Object.values(cart).reduce((s, l) => s + l.qty * l.price, 0);
    let disc = Number($('discount').value) || 0;
    if (disc > sub) disc = sub; if (disc < 0) disc = 0;
    const total = Math.round((sub - disc) * 100) / 100;
    $('subtotal').textContent = fmt(sub); $('grand').textContent = fmt(total);
    const method = $('method').value, paidEl = $('paid');
    if (!paidEl.dataset.touched) paidEl.value = method === $('method').dataset.credit ? 0 : total;
    const rem = Math.max(total - (Number(paidEl.value) || 0), 0);
    $('remaining').textContent = fmt(rem);
    return {sub, disc, total};
  }
  function toast(msg, kind) {
    const c = document.querySelector('.toast-container');
    const el = document.createElement('div');
    el.className = 'toast align-items-center border-0 text-bg-' + (kind || 'info');
    el.innerHTML = '<div class="d-flex"><div class="toast-body"></div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    el.querySelector('.toast-body').textContent = msg; c.appendChild(el);
    new bootstrap.Toast(el, {delay: 4500}).show();
  }
  $('q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(async () => renderResults(await search($('q').value.trim())), 200); });
  $('q').addEventListener('keydown', async e => {   // barcode scanners type the code then press Enter
    if (e.key !== 'Enter') return; e.preventDefault();
    const q = $('q').value.trim(); if (!q) return;
    const list = await search(q);
    const exact = list.find(p => p.barcode === q || p.sku === q) || (list.length === 1 ? list[0] : null);
    if (exact) { add(exact, 1); $('q').value = ''; renderResults(await search('')); } else renderResults(list);
  });
  ['discount', 'method'].forEach(id => $(id).addEventListener('input', () => { if (id === 'method') delete $('paid').dataset.touched; totals(); }));
  $('paid').addEventListener('input', () => { $('paid').dataset.touched = 1; totals(); });
  $('clear').addEventListener('click', () => { Object.keys(cart).forEach(k => delete cart[k]); renderCart(); });
  $('checkout').addEventListener('click', async () => {
    const t = totals(), btn = $('checkout');
    if (!Object.keys(cart).length) return toast('Add at least one product.', 'warning');
    btn.disabled = true;
    try {
      const r = await fetch('/sales/pos/checkout', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({items: Object.values(cart).map(l => ({product_id: l.id, qty: l.qty})), discount: t.disc,
          payment_method: $('method').value, customer_id: $('customer').value || null, paid: $('paid').value})});
      const d = await r.json();
      if (d.ok) location.href = d.url; else { toast(d.error || 'Could not complete the sale.', 'danger'); btn.disabled = false; }
    } catch (e) { toast('Network error. Please try again.', 'danger'); btn.disabled = false; }
  });
  search('').then(renderResults); renderCart(); $('q').focus();
})();
