if (document.querySelector('[data-domain-poll]')) {
  let dirty = false;
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('change', () => { dirty = true; });
    form.addEventListener('input', () => { dirty = true; });
  });
  setInterval(() => {
    if (!dirty && document.visibilityState === 'visible') window.location.reload();
  }, 15000);
}
