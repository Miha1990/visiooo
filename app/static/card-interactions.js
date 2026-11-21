document.querySelectorAll('[data-avatar-toggle]').forEach(button => {
  const photo = button.querySelector('.avatar-photo-face');
  const qr = button.querySelector('.avatar-qr-face');
  const image = button.querySelector('[data-avatar-qr]');
  const show = visible => {
    photo.hidden = visible;
    qr.hidden = !visible;
    button.dataset.qrVisible = String(visible);
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', visible ? 'Показать фото' : 'Показать QR-код визитки');
  };
  image.addEventListener('error', () => {
    show(false);
    image.removeAttribute('src');
    const hint = button.nextElementSibling;
    if (hint) hint.textContent = 'QR недоступен. Проверьте публикацию визитки.';
  });
  button.addEventListener('click', () => {
    const visible = button.getAttribute('aria-pressed') !== 'true';
    if (visible && !image.getAttribute('src')) image.src = image.dataset.avatarQr;
    show(visible);
  });
});
