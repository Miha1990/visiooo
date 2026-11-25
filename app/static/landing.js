(() => {
  const card = document.querySelector('[data-demo-card]');
  if (!card) return;
  const buttons = document.querySelectorAll('[data-demo-theme]');
  buttons.forEach(button => button.addEventListener('click', () => {
    card.dataset.theme = button.dataset.demoTheme;
    card.querySelectorAll('[data-demo-panel]').forEach(panel=>panel.hidden=panel.dataset.demoPanel!==button.dataset.demoTheme);
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  }));
})();
