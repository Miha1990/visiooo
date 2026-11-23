document.querySelectorAll('[data-avatar-toggle]').forEach(button => {
  const photo = button.querySelector('.avatar-photo-face');
  const qr = button.querySelector('.avatar-qr-face');
  const image = button.querySelector('[data-avatar-qr]');
  const show = visible => {
    photo.hidden = visible;
    qr.hidden = !visible;
    photo.setAttribute('aria-hidden', String(visible));
    qr.setAttribute('aria-hidden', String(!visible));
    button.dataset.qrVisible = String(visible);
    button.setAttribute('aria-pressed', String(visible));
    button.setAttribute('aria-label', visible ? 'Показать фото' : 'Показать QR-код визитки');
  };
  show(false);
  image.addEventListener('error', () => {
    show(false);
    image.removeAttribute('src');
    const hint = button.nextElementSibling;
    if (hint && !('ownerPortrait' in button.dataset)) hint.textContent = 'QR недоступен. Проверьте публикацию визитки.';
  });
  button.addEventListener('click', () => {
    const visible = button.getAttribute('aria-pressed') !== 'true';
    if (visible && !image.getAttribute('src')) image.src = image.dataset.avatarQr;
    show(visible);
  });
});

document.querySelectorAll('[data-save-contact]').forEach(link => {
  link.addEventListener('click', () => {
    const help = link.closest('.contact-save-group')?.querySelector('[data-contact-help]');
    if (!help) return;
    const ua = navigator.userAgent || '';
    const apple = /iPhone|iPad|iPod/i.test(ua) || (/Mac/i.test(navigator.platform || '') && navigator.maxTouchPoints > 1);
    const instructions = help.querySelector('[data-contact-instructions]');
    instructions.textContent = apple
      ? 'В открывшейся карточке выберите «Создать новый контакт» или «Добавить к существующему» и подтвердите сохранение. Если файл скачался, откройте его в приложении «Файлы».'
      : /Android/i.test(ua)
        ? 'Откройте файл contact.vcf в приложении «Контакты» и подтвердите добавление. Если файл только скачался, откройте его из загрузок браузера. Также можно выбрать в «Контактах» импорт из файла VCF.'
        : 'Откройте файл contact.vcf в приложении контактов и подтвердите добавление. Файл также можно импортировать в телефонную книгу.';
    help.hidden = false;
  });
});
