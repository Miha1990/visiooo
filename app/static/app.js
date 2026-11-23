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
  const designed = card.classList.contains('designed-card');
  const designIcons = designed ? JSON.parse(card.dataset.iconMap) : {};
  const fontInput = form.elements.namedItem('design_font');
  if (fontInput) fontInput.addEventListener('change', () => card.style.setProperty('--design-font', ({ui:"'Segoe UI',system-ui,sans-serif",serif:'Georgia,serif',rounded:"'Trebuchet MS',Arial,sans-serif"})[fontInput.value]));
  const template = form.elements.namedItem('template');
  const updateTemplate = () => {
    card.classList.remove('template-classic', 'template-minimal', 'template-profile');
    if (['classic', 'minimal', 'profile'].includes(template.value)) card.classList.add(`template-${template.value}`);
  };
  template.addEventListener('change', updateTemplate);
  updateTemplate();

  const httpUrl = value => window.WebLinks.normalize(value);
  const updateActions = () => {
    if (form.elements.namedItem('builder_mode')?.value === 'tiles') {
      try { window.CardButtons.render(card, JSON.parse(form.elements.namedItem('button_items').value || '[]')); } catch {}
      return;
    }
    const actions = card.querySelector('.contact-actions');
    actions.replaceChildren();
    const add = (label, href, detail, external = false, role = 'link') => {
      const anchor = document.createElement('a');
      anchor.textContent = label;
      if (designed) {
        const img = document.createElement('img');
        img.src = designIcons[role]; img.alt = ''; img.className = 'design-contact-icon'; img.width = 24; img.height = 24;
        anchor.prepend(img);
      }
      anchor.href = href;
      if (detail) {
        const span = document.createElement('span');
        span.textContent = detail;
        anchor.append(span);
      }
      if (external) { anchor.target = '_blank'; anchor.rel = 'noopener noreferrer'; }
      actions.append(anchor);
    };
    let phone = form.elements.namedItem('phone').value.trim().replace(/[\s()\-]/g, '');
    if (/^[78][0-9]{10}$/.test(phone)) phone = '+7' + phone.slice(1);
    const email = form.elements.namedItem('email').value.trim();
    const phoneLabel = form.elements.namedItem('phone_label'), emailLabel = form.elements.namedItem('email_label');
    if (/^\+[1-9][0-9]{7,14}$/.test(phone)) add(phoneLabel?.value.trim() || card.dataset.phoneLabel || 'Позвонить', `tel:${phone}`, phoneLabel ? '' : phone, false, 'phone');
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) add(emailLabel?.value.trim() || card.dataset.emailLabel || 'Написать', `mailto:${email}`, emailLabel ? '' : email, false, 'email');
    const linkRows = [...form.querySelectorAll('[data-link-row]')];
    const lines = linkRows.length ? linkRows.map(row => `${row.querySelector('[data-link-label]').value} | ${row.querySelector('[data-link-url]').value}`) : (form.elements.namedItem('links')?.value || '').split('\n');
    for (const line of lines.filter(line => line.trim()).slice(0, 10)) {
      const divider = line.indexOf('|');
      if (divider === -1) continue;
      const label = line.slice(0, divider).trim();
      const url = httpUrl(line.slice(divider + 1));
      if (label && url) add(label, url, '', true);
    }
  };
  for (const key of ['phone', 'email', 'phone_label', 'email_label', 'website', 'links', 'button_items']) form.elements.namedItem(key)?.addEventListener('input', updateActions);
  const linkRows = [...form.querySelectorAll('[data-link-row]')];
  linkRows.forEach(row => row.querySelectorAll('input').forEach(input => input.addEventListener('input', updateActions)));
  const addLink = form.querySelector('[data-add-link]');
  if (addLink) {
    let firstEmptyShown = false;
    linkRows.forEach(row => {
      const empty = ![...row.querySelectorAll('input')].some(input => input.value.trim());
      row.hidden = empty && firstEmptyShown;
      if (empty) firstEmptyShown = true;
    });
    const updateAddLink = () => {addLink.hidden = !linkRows.some(row => row.hidden);};
    addLink.addEventListener('click', () => {
      const row = linkRows.find(row => row.hidden);
      if (row) {row.hidden = false;row.querySelector('input').focus();}
      updateAddLink();
    });
    updateAddLink();
  }
  updateActions();

  const socialSection = card.querySelector('.social-section');
  const socialContainer = card.querySelector('.social-links');
  const socialFields = [...form.querySelectorAll('[data-social]')];
  const iconBase = new URL('icons/', document.currentScript.src).href;
  const updateSocials = () => {
    socialContainer.replaceChildren();
    for (const input of socialFields) {
      const url = httpUrl(input.value);
      if (!url) continue;
      const key = input.dataset.social;
      const anchor = document.createElement('a');
      anchor.className = `social-link social-${key}`;
      anchor.href = url;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      const icon = document.createElement('span');
      icon.className = 'social-icon';
      const img = document.createElement('img');
      img.src = designIcons[key] || `${iconBase}${key}.svg`;
      img.alt = '';
      img.width = 24;
      img.height = 24;
      icon.append(img);
      const label = document.createElement('span');
      label.textContent = input.dataset.label;
      anchor.setAttribute('aria-label', input.dataset.label);
      anchor.append(icon, label);
      socialContainer.append(anchor);
    }
    socialSection.hidden = !socialContainer.childElementCount;
    window.CardWidgets?.refresh(card);
  };
  socialFields.forEach(input => input.addEventListener('input', updateSocials));
  updateSocials();
}
const editor = document.querySelector('.editor');
if (editor) {
  editor.classList.add('has-view-toggle');
  document.querySelectorAll('[data-editor-view]').forEach(item => item.setAttribute('aria-pressed', String(item.dataset.editorView === editor.dataset.view)));
  document.querySelectorAll('[data-editor-view]').forEach(button => {
    button.addEventListener('click', () => {
      editor.dataset.view = button.dataset.editorView;
      document.querySelectorAll('[data-editor-view]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    });
  });
  editor.querySelectorAll('.editor-section-nav a').forEach(link=>link.addEventListener('click',()=>{
    editor.dataset.view='edit';
    document.querySelectorAll('[data-editor-view]').forEach(item=>item.setAttribute('aria-pressed',String(item.dataset.editorView==='edit')));
  }));
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
