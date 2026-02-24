import { afterEach, describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { mockIPC, mockWindows, clearMocks } from '@tauri-apps/api/mocks';

function createDom() {
  return new JSDOM(`
    <!DOCTYPE html>
    <html>
      <body>
        <main id="app">
          <header class="header-bar">
            <div class="aspect-ratio-control">
              <input type="radio" name="aspect-ratio" value="1:1" checked />
              <input type="radio" name="aspect-ratio" value="16:9" />
            </div>
            <div class="resolution-control">
              <button id="resolution-decrease" type="button">-</button>
              <span id="dimension-display">256×256</span>
              <button id="resolution-increase" type="button">+</button>
            </div>
            <input id="prompt-input" type="text" />
            <div id="validation-error"></div>
          </header>

          <section class="viewer">
            <div class="image-container">
              <img class="current-image" id="current-image" src="" alt="" />
              <div class="magnifier-lens" id="magnifier-lens"></div>
              <div class="loading-overlay" id="loading-overlay">
                <div class="spinner"></div>
                <span class="loading-label"></span>
                <span id="loading-prompt"></span>
              </div>
            </div>
            <div id="nav-indicator"></div>
            <div id="nav-dots"></div>
          </section>

          <section class="status-bar"></section>
          <div id="prompt-display"></div>
          <div id="image-path-display"></div>
          <span id="path-text"></span>
          <button id="copy-path-btn" type="button"></button>

          <section class="controls">
            <button id="prev-btn" type="button"></button>
            <button id="next-btn" type="button"></button>
            <button id="accept-btn" type="button"></button>
            <button id="delete-btn" type="button"></button>
            <button id="abort-btn" type="button"></button>
            <button id="pause-btn" type="button">
              <span id="pause-icon"></span>
              <span id="pause-label"></span>
            </button>
            <button id="theme-toggle" type="button"></button>
            <input type="radio" name="font-size" value="small" />
            <input type="radio" name="font-size" value="medium" checked />
            <input type="radio" name="font-size" value="large" />
          </section>
        </main>
      </body>
    </html>
  `, {
    url: 'http://localhost',
    pretendToBeVisual: true,
  });
}

async function setupMain(options = {}) {
  const dom = createDom();
  const { window } = dom;
  const { document } = window;
  const calls = [];
  const failConfigUpdates = options.failConfigUpdates === true;

  global.window = window;
  global.document = document;
  global.HTMLElement = window.HTMLElement;
  global.localStorage = {
    _store: {},
    getItem(key) { return this._store[key] ?? null; },
    setItem(key, value) { this._store[key] = String(value); },
    removeItem(key) { delete this._store[key]; },
    clear() { this._store = {}; },
  };
  window.matchMedia = () => ({
    matches: false,
    media: '',
    addEventListener: () => {},
    removeEventListener: () => {},
  });

  if (!window.crypto && globalThis.crypto) {
    Object.defineProperty(window, 'crypto', { value: globalThis.crypto });
  }

  mockWindows('main');
  mockIPC((cmd, args) => {
    calls.push({ cmd, args });

    if (cmd === 'get_launch_args') {
      return {
        prompt: 'test prompt',
        output_path: null,
        seed: null,
        aspect_ratio: '1:1',
        width: 256,
        height: 256,
      };
    }
    if (cmd === 'update_generation_config' && failConfigUpdates) {
      throw new Error('Simulated config update failure');
    }
    return null;
  }, { shouldMockEvents: true });

  const modUrl = new URL(`./bundle.js?test=${Date.now()}-${Math.random()}`, import.meta.url);
  await import(modUrl.href);
  await window.textbrushApp?.init();

  return { dom, window, document, calls };
}

function countCalls(calls, cmd) {
  return calls.filter((entry) => entry.cmd === cmd);
}

afterEach(() => {
  clearMocks();
  delete global.window;
  delete global.document;
  delete global.HTMLElement;
  delete global.localStorage;
});

describe('Main UI regression tests', () => {
  test('single resolution click advances one notch after repeated init calls', async () => {
    const { window, document, calls } = await setupMain();

    await window.textbrushApp.init();
    await window.textbrushApp.init();

    const beforeUpdates = countCalls(calls, 'update_generation_config').length;
    const increaseBtn = document.getElementById('resolution-increase');
    assert.ok(increaseBtn, 'resolution increase button exists');

    increaseBtn.click();
    await Promise.resolve();

    const updateCalls = countCalls(calls, 'update_generation_config').slice(beforeUpdates);
    assert.strictEqual(updateCalls.length, 1, 'one backend config update for one click');
    assert.deepStrictEqual(updateCalls[0].args, {
      prompt: 'test prompt',
      aspectRatio: '1:1',
      width: 512,
      height: 512,
    });
  });

  test('single Space keydown toggles pause exactly once after repeated init calls', async () => {
    const { window, document, calls } = await setupMain();

    await window.textbrushApp.init();
    await window.textbrushApp.init();

    const beforePause = countCalls(calls, 'pause_generation').length;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await Promise.resolve();

    const pauseCalls = countCalls(calls, 'pause_generation').slice(beforePause);
    assert.strictEqual(pauseCalls.length, 1, 'one pause command for one Space keydown');
  });

  test('repeated Space keydown events are ignored when event.repeat is true', async () => {
    const { window, document, calls } = await setupMain();

    const beforePause = countCalls(calls, 'pause_generation').length;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true, repeat: false }));
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true, repeat: true }));
    await Promise.resolve();

    const pauseCalls = countCalls(calls, 'pause_generation').slice(beforePause);
    assert.strictEqual(pauseCalls.length, 1, 'repeat keydown does not trigger extra pause command');
  });

  test('resolution controls roll back visual state when config update fails', async () => {
    const { document, calls } = await setupMain({ failConfigUpdates: true });

    const increaseBtn = document.getElementById('resolution-increase');
    const decreaseBtn = document.getElementById('resolution-decrease');
    const dimensionDisplay = document.getElementById('dimension-display');
    assert.ok(increaseBtn, 'resolution increase button exists');
    assert.ok(decreaseBtn, 'resolution decrease button exists');
    assert.ok(dimensionDisplay, 'dimension display exists');

    increaseBtn.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    const updateCalls = countCalls(calls, 'update_generation_config');
    assert.strictEqual(updateCalls.length, 1, 'one backend config update attempt for one click');
    assert.strictEqual(dimensionDisplay.textContent, '256×256', 'dimension display rolls back to actual size');
    assert.strictEqual(decreaseBtn.disabled, true, 'decrease button matches rolled-back minimum size');
    assert.strictEqual(increaseBtn.disabled, false, 'increase button remains enabled after rollback');
  });

  test('aspect ratio controls roll back selection and size when config update fails', async () => {
    const { document } = await setupMain({ failConfigUpdates: true });

    const ratio11 = document.querySelector('input[name="aspect-ratio"][value="1:1"]');
    const ratio169 = document.querySelector('input[name="aspect-ratio"][value="16:9"]');
    const dimensionDisplay = document.getElementById('dimension-display');
    const decreaseBtn = document.getElementById('resolution-decrease');
    const increaseBtn = document.getElementById('resolution-increase');
    assert.ok(ratio11, '1:1 radio exists');
    assert.ok(ratio169, '16:9 radio exists');
    assert.ok(dimensionDisplay, 'dimension display exists');
    assert.ok(decreaseBtn, 'resolution decrease button exists');
    assert.ok(increaseBtn, 'resolution increase button exists');

    ratio169.checked = true;
    ratio169.dispatchEvent(new window.Event('change', { bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.strictEqual(ratio11.checked, true, 'ratio selection rolls back to previous value');
    assert.strictEqual(ratio169.checked, false, 'failed ratio change is reverted');
    assert.strictEqual(dimensionDisplay.textContent, '256×256', 'dimension display rolls back to previous size');
    assert.strictEqual(decreaseBtn.disabled, true, 'decrease button matches rolled-back size');
    assert.strictEqual(increaseBtn.disabled, false, 'increase button matches rolled-back size');
  });
});
