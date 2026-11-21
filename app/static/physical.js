const writeButton = document.getElementById('nfc-write');
if (writeButton) {
  const status = document.getElementById('nfc-status');
  const consent = document.getElementById('nfc-write-consent');
  const cancelButton = document.getElementById('nfc-cancel');
  let controller;
  if (writeButton.dataset.localOnly === 'true') {
    writeButton.disabled = true;
    status.textContent = 'Для записи рабочей NFC-ссылки сначала настройте публичный домен сервиса.';
  } else if (!window.isSecureContext || !('NDEFReader' in window)) {
    writeButton.disabled = true;
    status.textContent = 'Этот браузер не поддерживает запись NFC. Скопируйте ссылку и запишите её как URL в приложении для NFC.';
  }
  cancelButton.addEventListener('click', () => controller?.abort());
  writeButton.addEventListener('click', async () => {
    if (writeButton.disabled) return;
    if (!consent.checked) {
      status.textContent = 'Подтвердите замену записи в вашей NFC-метке.';
      consent.focus();
      return;
    }
    writeButton.disabled = true;
    cancelButton.hidden = false;
    controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    status.textContent = 'Приложите вашу NFC-карточку к телефону. Запись ожидает метку…';
    try {
      const reader = new window.NDEFReader();
      await reader.write({records: [{recordType: 'url', data: writeButton.dataset.url}]},
        {overwrite: true, signal: controller.signal});
      status.textContent = 'Ссылка записана. Уберите метку и приложите снова, чтобы проверить открытие визитки.';
    } catch (error) {
      status.textContent = error.name === 'AbortError' ? 'Запись отменена или время ожидания истекло.'
        : 'Запись не выполнена. Проверьте разрешение браузера, NFC телефона и возможность перезаписи метки.';
    } finally {
      clearTimeout(timeout);
      writeButton.disabled = false;
      cancelButton.hidden = true;
    }
  });
}
