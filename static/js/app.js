document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.toast').forEach(t => new bootstrap.Toast(t, {delay: 4500}).show());
  document.getElementById('sbToggle')?.addEventListener('click', () => document.body.classList.toggle('sb-open'));
  document.getElementById('sbOverlay')?.addEventListener('click', () => document.body.classList.remove('sb-open'));

  // Confirmation dialog for forms carrying data-confirm="message"
  const cm = document.getElementById('confirmModal');
  let pending = null;
  document.addEventListener('submit', e => {
    const f = e.target;
    if (cm && f.dataset && f.dataset.confirm) {
      e.preventDefault(); pending = f;
      cm.querySelector('.msg').textContent = f.dataset.confirm;
      bootstrap.Modal.getOrCreateInstance(cm).show();
    }
  });
  cm?.querySelector('.ok').addEventListener('click', () => {
    if (pending) { bootstrap.Modal.getInstance(cm).hide(); pending.submit(); }
  });

  // Add/Edit modals: buttons with data-edit='{json}' data-action='/url' pre-fill the form
  document.querySelectorAll('.entity-modal').forEach(m => {
    m.addEventListener('show.bs.modal', e => {
      const b = e.relatedTarget, f = m.querySelector('form');
      f.reset();
      const edit = b && b.dataset.edit ? JSON.parse(b.dataset.edit) : null;
      f.action = edit ? b.dataset.action : m.dataset.newAction;
      m.querySelector('.modal-title .t').textContent = edit ? 'Edit' : 'Add';
      if (edit) for (const [k, v] of Object.entries(edit)) { const el = f.elements[k]; if (el) el.value = v ?? ''; }
    });
  });

  // Pre-fill generic "pay" modals: button data-action + data-name
  document.querySelectorAll('.pay-modal').forEach(m => {
    m.addEventListener('show.bs.modal', e => {
      const b = e.relatedTarget; if (!b) return;
      const f = m.querySelector('form'); f.reset();
      f.action = b.dataset.action;
      m.querySelector('.who').textContent = b.dataset.name || '';
      if (b.dataset.max) f.elements.amount.max = b.dataset.max;
    });
  });
});
