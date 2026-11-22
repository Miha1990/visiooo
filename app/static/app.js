const form = document.querySelector('#editor-form');
if (form) {
  for (const key of ['name', 'title', 'company', 'bio']) {
    const input = form.elements.namedItem(key);
    const target = document.querySelector(`[data-preview="${key}"]`);
    if (input && target) {
      const update = () => {
        target.textContent = input.value;
        const initial = document.querySelector('[data-preview="initial"]');
        if (key === 'name' && initial) initial.textContent = input.value.slice(0, 1);
      };
      input.addEventListener('input', update);
      update();
    }
  }
  form.elements.namedItem('accent').addEventListener('input', event => {
    document.querySelector('.contact-card').style.setProperty('--accent', event.target.value);
  });
  const card = document.querySelector('.contact-card');
  const template = form.elements.namedItem('template');
  const updateTemplate = () => {
    card.classList.remove('template-classic', 'template-minimal', 'template-profile');
    if (['classic', 'minimal', 'profile'].includes(template.value)) card.classList.add(`template-${template.value}`);
  };
  template.addEventListener('change', updateTemplate);
  updateTemplate();

  const safeHttp = value => {
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && !/[\x00-\x20]/.test(value);
    } catch { return false; }
  };
  const updateActions = () => {
    const actions = card.querySelector('.contact-actions');
    actions.replaceChildren();
    const add = (label, href, detail, external = false) => {
      const anchor = document.createElement('a');
      anchor.textContent = label;
      anchor.href = href;
      if (detail) {
        const span = document.createElement('span');
        span.textContent = detail;
        anchor.append(span);
      }
      if (external) { anchor.target = '_blank'; anchor.rel = 'noopener noreferrer'; }
      actions.append(anchor);
    };
    const phone = form.elements.namedItem('phone').value.trim();
    const email = form.elements.namedItem('email').value.trim();
    if (/^\+[1-9][0-9]{7,14}$/.test(phone)) add('Позвонить', `tel:${phone}`, phone);
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) add('Написать', `mailto:${email}`, email);
    for (const line of form.elements.namedItem('links').value.split('\n').filter(line => line.trim()).slice(0, 10)) {
      const divider = line.indexOf('|');
      if (divider === -1) continue;
      const label = line.slice(0, divider).trim();
      const url = line.slice(divider + 1).trim();
      if (label && safeHttp(url)) add(label, url, '', true);
    }
  };
  for (const key of ['phone', 'email', 'website', 'links']) form.elements.namedItem(key).addEventListener('input', updateActions);
  updateActions();

  const socialSection = card.querySelector('.social-section');
  const socialContainer = card.querySelector('.social-links');
  const socialFields = [...form.querySelectorAll('[data-social]')];
  const iconBase = new URL('icons/', document.currentScript.src).href;
  const updateSocials = () => {
    socialContainer.replaceChildren();
    for (const input of socialFields) {
      let url = input.value.trim();
      if (url && !url.includes(':')) url = `https://${url}`;
      if (!safeHttp(url)) continue;
      const key = input.dataset.social;
      const anchor = document.createElement('a');
      anchor.className = `social-link social-${key}`;
      anchor.href = url;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      const icon = document.createElement('span');
      icon.className = 'social-icon';
      const img = document.createElement('img');
      img.src = `${iconBase}${key}.svg`;
      img.alt = '';
      img.width = 24;
      img.height = 24;
      icon.append(img);
      const label = document.createElement('span');
      label.textContent = input.dataset.label;
      anchor.append(icon, label);
      socialContainer.append(anchor);
    }
    socialSection.hidden = !socialContainer.childElementCount;
  };
  socialFields.forEach(input => input.addEventListener('input', updateSocials));
  updateSocials();
}
const editor = document.querySelector('.editor');
if (editor) {
  editor.classList.add('has-view-toggle');
  document.querySelectorAll('[data-editor-view]').forEach(button => {
    button.addEventListener('click', () => {
      editor.dataset.view = button.dataset.editorView;
      document.querySelectorAll('[data-editor-view]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    });
  });
}
document.querySelectorAll('[data-copy], [data-share]').forEach(button => {
  button.addEventListener('click', async () => {
    const field = document.getElementById(button.dataset.copy || button.dataset.share);
    const status = document.querySelector('#share-status');
    try {
      if (button.dataset.share && navigator.share) {
        await navigator.share({title: 'Моя визитка', url: field.value});
        status.textContent = 'Ссылка передана в меню отправки.';
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(field.value);
        status.textContent = 'Ссылка скопирована.';
      } else {
        field.select();
        status.textContent = 'Скопируйте выделенную ссылку.';
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        field.select();
        status.textContent = 'Скопируйте ссылку из поля вручную.';
      }
    }
  });
});
