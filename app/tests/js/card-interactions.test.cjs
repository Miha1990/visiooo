const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = name => fs.readFileSync(path.join(__dirname, '../../static', name), 'utf8');

function element() {
  return {hidden: false, disabled: false, checked: false, dataset: {}, events: {}, attrs: {}, textContent: '',
    addEventListener(name, fn) { this.events[name] = fn; },
    getAttribute(name) { return this.attrs[name] || null; },
    setAttribute(name, value) { this.attrs[name] = value; },
    removeAttribute(name) { delete this.attrs[name]; },
    focus() { this.focused = true; }};
}

function avatar() {
  const button = element(), photo = element(), qr = element(), image = element(), hint = element();
  qr.hidden = true;
  image.dataset.avatarQr = '/c/test/qr.png';
  Object.defineProperty(image, 'src', {get() {return this.attrs.src;}, set(value) {this.attrs.src = value;}});
  button.nextElementSibling = hint;
  button.attrs['aria-pressed'] = 'false';
  button.querySelector = selector => ({'.avatar-photo-face': photo, '.avatar-qr-face': qr, '[data-avatar-qr]': image})[selector];
  vm.runInNewContext(source('card-interactions.js'), {document: {querySelectorAll: selector => selector==='[data-avatar-toggle]'?[button]:[]}});
  return {button, photo, qr, image, hint};
}

test('one click shows QR, second click restores photo and accessibility state', () => {
  const {button, photo, qr, image} = avatar();
  button.events.click();
  assert.equal(image.src, '/c/test/qr.png');
  assert.equal(photo.hidden, true);
  assert.equal(qr.hidden, false);
  assert.equal(button.attrs['aria-pressed'], 'true');
  button.events.click();
  assert.equal(photo.hidden, false);
  assert.equal(qr.hidden, true);
  assert.equal(button.attrs['aria-pressed'], 'false');
});

test('failed QR request returns to photo and allows retry', () => {
  const {button, photo, image, hint} = avatar();
  button.events.click();
  image.events.error();
  assert.equal(photo.hidden, false);
  assert.equal(image.getAttribute('src'), null);
  assert.match(hint.textContent, /недоступен/);
  button.events.click();
  assert.equal(image.src, '/c/test/qr.png');
});

function nfc({local = false, supported = true, write = async () => {}} = {}) {
  const ids = Object.fromEntries(['nfc-write', 'nfc-status', 'nfc-write-consent', 'nfc-cancel'].map(id => [id, element()]));
  ids['nfc-write'].dataset = {localOnly: String(local), url: 'https://cards.example.com/p/fixed-id'};
  const window = {isSecureContext: true};
  if (supported) window.NDEFReader = class {write(...args) {return write(...args);}};
  vm.runInNewContext(source('physical.js'), {document: {getElementById: id => ids[id]},
    window, AbortController, setTimeout: () => 1, clearTimeout: () => {}});
  return ids;
}

test('NFC write requires explicit consent', async () => {
  let calls = 0;
  const ids = nfc({write: async () => {calls++;}});
  await ids['nfc-write'].events.click();
  assert.equal(calls, 0);
  assert.equal(ids['nfc-write-consent'].focused, true);
});

test('NFC writes the exact stable URL as a URL record', async () => {
  let message, options;
  const ids = nfc({write: async (m, o) => {message = m; options = o;}});
  ids['nfc-write-consent'].checked = true;
  await ids['nfc-write'].events.click();
  assert.equal(message.records[0].recordType, 'url');
  assert.equal(message.records[0].data, 'https://cards.example.com/p/fixed-id');
  assert.equal(options.overwrite, true);
  assert.match(ids['nfc-status'].textContent, /Ссылка записана/);
  assert.equal(ids['nfc-write'].disabled, false);
});

test('local URLs and unsupported browsers disable NFC writing', async () => {
  for (const settings of [{local: true}, {supported: false}]) {
    let calls = 0;
    const ids = nfc({...settings, write: async () => {calls++;}});
    assert.equal(ids['nfc-write'].disabled, true);
    await ids['nfc-write'].events.click();
    assert.equal(calls, 0);
  }
});

test('cancel aborts pending NFC write and restores controls', async () => {
  const ids = nfc({write: (message, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(Object.assign(new Error(), {name: 'AbortError'})));
  })});
  ids['nfc-write-consent'].checked = true;
  const pending = ids['nfc-write'].events.click();
  assert.equal(ids['nfc-cancel'].hidden, false);
  ids['nfc-cancel'].events.click();
  await pending;
  assert.match(ids['nfc-status'].textContent, /отменена/);
  assert.equal(ids['nfc-write'].disabled, false);
  assert.equal(ids['nfc-cancel'].hidden, true);
});
