const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../static/analytics-consent.js'), 'utf8');

async function setup({choice = null, eligible = true, failGet = false, failPost = false} = {}) {
  const scripts = [], requests = [], events = {}, status = {textContent: ''};
  const buttons = ['denied', 'granted'].map(value => ({dataset: {analyticsChoice: value}, events: {},
    addEventListener(type, handler) { this.events[type] = handler; }}));
  const banner = {hidden: true, querySelector() { return {focus() {}}; }};
  const config = {eligible, counter_id: '123456', page_url: 'https://visiooo.ru/pricing', version: 'v1'};
  const store = {_ym_uid: 'identifier', unrelated: 'keep'};
  Object.defineProperty(store, 'removeItem', {value(key) {delete this[key];}});
  Object.defineProperty(store, 'setItem', {value(key, value) {this[key] = value;}});
  let reloads = 0;
  const window = {localStorage: store, sessionStorage: store,
    location: {hostname: 'visiooo.ru', reload() { reloads++; }},
    addEventListener(type, handler) { events[type] = handler; }};
  const document = {cookie: '_ym_uid=identifier; csrftoken=safe',
    getElementById() {return {textContent: JSON.stringify(config)};},
    querySelector(selector) {return selector.includes('banner') ? banner : selector.includes('status') ? status : null;},
    querySelectorAll() {return buttons;}, createElement() {return {};},
    head: {appendChild(script) {scripts.push(script);}}};
  async function fetch(url, options = {}) {
    requests.push({url, options});
    if (!options.method && failGet) throw new Error('offline');
    if (options.method && failPost) return {ok: false};
    if (options.method) choice = options.body.get('choice') === 'granted' ? 'granted' : 'withdrawn';
    return {ok: true, async json() {return {enabled: true, choice, csrf_token: 'csrf'};}};
  }
  vm.runInNewContext(source, {window, document, fetch, URLSearchParams, Date});
  await new Promise(resolve => setImmediate(resolve));
  return {scripts, requests, banner, buttons, status, window, store, reloads: () => reloads};
}

test('no choice and refusal make no third-party requests', async () => {
  const fresh = await setup();
  assert.equal(fresh.scripts.length, 0);
  assert.equal(fresh.banner.hidden, false);
  await fresh.buttons[0].events.click();
  assert.equal(fresh.scripts.length, 0);
  assert.equal(fresh.reloads(), 1);
  assert.equal(fresh.store._ym_uid, undefined);
  assert.equal(fresh.store.unrelated, 'keep');
});
test('counter starts only after server acknowledges explicit permission', async () => {
  const env = await setup();
  await env.buttons[1].events.click();
  assert.equal(env.scripts.length, 1);
  assert.equal(env.scripts[0].src, 'https://mc.yandex.ru/metrika/tag.js');
  assert.equal(env.scripts[0].referrerPolicy, 'no-referrer');
  const [init, hit] = env.window.ym.a;
  assert.equal(init[1], 'init');
  for (const option of ['webvisor', 'clickmap', 'trackLinks', 'trackHash', 'ecommerce', 'sendTitle']) {
    assert.equal(init[2][option], false);
  }
  assert.equal(init[2].defer, true);
  assert.equal(init[2].disableYtm, true);
  assert.equal(hit[2], 'https://visiooo.ru/pricing');
  assert.equal(hit[3].referer, '');
});
test('failed state fetch or failed evidence save never enables analytics', async () => {
  const failedState = await setup({failGet: true});
  assert.equal(failedState.scripts.length, 0);
  const failedSave = await setup({failPost: true});
  await failedSave.buttons[1].events.click();
  assert.equal(failedSave.scripts.length, 0);
  assert.ok(failedSave.status.textContent);
});
test('previous permission does not enable counter on private or legal pages', async () => {
  const env = await setup({choice: 'granted', eligible: false});
  assert.equal(env.scripts.length, 0);
});
test('withdrawing an existing permission reloads without retaining identifiers', async () => {
  const env = await setup({choice: 'granted'});
  assert.equal(env.scripts.length, 1);
  await env.buttons[0].events.click();
  assert.equal(env.reloads(), 1);
  assert.equal(env.store._ym_uid, undefined);
});
