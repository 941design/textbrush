import { JSDOM } from 'jsdom';
import { mockIPC, mockWindows } from '@tauri-apps/api/mocks';

function createDom() {
  return new JSDOM(`
    <!DOCTYPE html>
    <html>
      <body>
        <main id="app">
          <header class="header-bar">
            <fieldset id="output-size">
              <div class="aspect-ratio-control">
                <label><input type="radio" name="aspect-ratio" value="1:1" checked /><span class="ratio-dimensions" data-ratio="1:1"></span></label>
                <label><input type="radio" name="aspect-ratio" value="16:9" /><span class="ratio-dimensions" data-ratio="16:9"></span></label>
              </div>
              <div class="resolution-control">
                <button id="resolution-decrease" type="button">-</button>
                <span id="dimension-display">256×256</span>
                <button id="resolution-increase" type="button">+</button>
              </div>
            </fieldset>
            <fieldset id="model-selector"><label><input type="radio" name="model" value="flux1-schnell" /><small class="model-note"></small></label></fieldset>
            <div id="reference-picker"><span id="reference-legend"></span><button id="reference-add"></button><ul id="reference-list"></ul><div id="reference-error"></div></div>
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

export async function setupMain(options = {}) {
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
        ...options.launchArgs,
      };
    }
    if (cmd === 'init_generation' && options.onInit) return options.onInit(window);
    if (cmd === 'accept_image' && options.failAccept) throw new Error('Dispatch failed');
    if (cmd === 'update_generation_config' && failConfigUpdates) {
      throw new Error('Simulated config update failure');
    }
    return null;
  }, { shouldMockEvents: true });

  if (options.wrapInvoke) {
    window.__TAURI_INTERNALS__.invoke = options.wrapInvoke(window.__TAURI_INTERNALS__.invoke);
  }

  const modUrl = new URL(`./bundle.js?test=${Date.now()}-${Math.random()}`, import.meta.url);
  await import(modUrl.href);
  if (!options.skipInitWait) await window.textbrushApp?.init();

  return { dom, window, document, calls };
}

