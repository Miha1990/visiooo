/* No third-party code or requests until an explicit, server-recorded opt-in. */
(() => {
  'use strict';
  const configNode = document.getElementById('analytics-config');
  if (!configNode) return;
  const config = JSON.parse(configNode.textContent);
  const banner = document.querySelector('[data-analytics-banner]');
  const status = document.querySelector('[data-analytics-status]');
  const buttons = [...document.querySelectorAll('[data-analytics-choice]')];
  const settings = document.querySelector('[data-analytics-settings]');
  let csrf = '', choice = null, started = false, ready = false;
  function start() {
    if (!ready || choice !== 'granted' || !config.eligible || started) return;
    started = true;
    window.ym = window.ym || function () { (window.ym.a = window.ym.a || []).push(arguments); };
    window.ym.l = Date.now();
    window.ym(Number(config.counter_id), 'init', {defer: true, webvisor: false, clickmap: false,
      trackLinks: false, trackHash: false, ecommerce: false, disableYtm: true,
      accurateTrackBounce: false, sendTitle: false});
    window.ym(Number(config.counter_id), 'hit', config.page_url, {title: 'Визитка', referer: ''});
    const script = document.createElement('script');
    script.async = true;
    script.referrerPolicy = 'no-referrer';
    script.src = 'https://mc.yandex.ru/metrika/tag.js';
    document.head.appendChild(script);
  }
  function clearIdentifiers() {
    const hosts = window.location.hostname.split('.');
    for (const item of document.cookie.split(';')) {
      const name = item.split('=')[0].trim();
      if (!name.startsWith('_ym')) continue;
      document.cookie = `${name}=; Max-Age=0; Path=/; SameSite=Lax`;
      for (let index = 0; index < hosts.length - 1; index++) {
        const host = hosts.slice(index).join('.');
        document.cookie = `${name}=; Max-Age=0; Path=/; Domain=.${host}; SameSite=Lax`;
      }
    }
    for (const name of ['localStorage', 'sessionStorage']) {
      try {
        const storage = window[name];
        for (const key of Object.keys(storage)) {
          if (key.startsWith('_ym')) storage.removeItem(key);
        }
      } catch (_) { /* A storage restriction never grants consent. */ }
    }
  }
  function show() { banner.hidden = false; banner.querySelector('h2').focus(); }
  if (settings) settings.addEventListener('click', show);
  buttons.forEach(button => button.addEventListener('click', async () => {
    buttons.forEach(item => { item.disabled = true; });
    status.textContent = '';
    try {
      if (!ready) throw new Error('not ready');
      const body = new URLSearchParams({choice: button.dataset.analyticsChoice, version: config.version});
      const response = await fetch('/analytics/consent', {method: 'POST', credentials: 'same-origin',
        cache: 'no-store', headers: {'X-CSRFToken': csrf}, body});
      if (!response.ok) throw new Error('save failed');
      const data = await response.json();
      if (!data.enabled) throw new Error('disabled');
      choice = data.choice;
      banner.hidden = true;
      try { window.localStorage.setItem('visiooo-analytics-choice', String(Date.now())); } catch (_) {}
      if (choice !== 'granted') {
        clearIdentifiers();
        // Reload removes the library and all its handlers, including an in-flight load.
        window.location.reload();
      } else start();
    } catch (_) {
      status.textContent = 'Не удалось сохранить выбор. Аналитика не будет включена без подтверждения. Повторите попытку или обновите страницу.';
    } finally { buttons.forEach(item => { item.disabled = false; }); }
  }));
  window.addEventListener('storage', event => {
    if (event.key === 'visiooo-analytics-choice') window.location.reload();
  });
  // Recheck consent when returning to a previously open tab.
  window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); });
  fetch('/analytics/consent', {credentials: 'same-origin', cache: 'no-store'})
    .then(response => { if (!response.ok) throw new Error('state failed'); return response.json(); })
    .then(data => {
      if (!data.enabled) return;
      csrf = data.csrf_token;
      choice = data.choice;
      ready = true;
      if (choice === 'granted') start();
      else if (!choice && config.eligible) banner.hidden = false;
      if (choice !== 'granted') clearIdentifiers();
    }).catch(() => { /* Remain disabled when the consent state cannot be verified. */ });
})();
