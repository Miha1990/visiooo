(() => {
  const qrDialog = document.querySelector('[data-qr-dialog]');
  const portrait = document.querySelector('[data-owner-portrait]');
  document.querySelectorAll('[data-open-qr]').forEach(link => link.addEventListener('click', event => {
    if (portrait) { event.preventDefault(); portrait.click(); portrait.scrollIntoView({behavior:'smooth',block:'center'}); return; }
    if (!qrDialog || typeof qrDialog.showModal !== 'function') return;
    event.preventDefault();
    if (!qrDialog.open) qrDialog.showModal();
  }));
  document.querySelectorAll('.client-dialog').forEach(dialog => dialog.addEventListener('click', event => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  }));
  const status = document.querySelector('[data-client-share-status]');
  const fallback = () => {
    const dialog = document.querySelector('[data-share-dialog]');
    const input = document.querySelector('#client-share-url');
    if (dialog && typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
    input?.focus();
    input?.select();
    if (status) status.textContent = 'Скопируйте ссылку и отправьте её получателю.';
  };
  document.querySelectorAll('[data-client-share]').forEach(button => button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    try {
      if (navigator.share) {
        await navigator.share({title: button.dataset.title, url: button.dataset.url});
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(button.dataset.url);
        if (status) status.textContent = 'Ссылка скопирована. Отправьте её получателю.';
      } else fallback();
    } catch (error) {
      if (error.name !== 'AbortError') fallback();
    } finally { button.disabled = false; }
  }));
})();
