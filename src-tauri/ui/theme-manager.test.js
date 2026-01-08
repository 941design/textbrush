// theme-manager.test.js
// Property-based tests for theme manager module
// Uses JSDOM for DOM simulation and Node's built-in test runner

import test from 'node:test';
import assert from 'node:assert';
import { JSDOM } from 'jsdom';
import { initTheme, toggleTheme, getCurrentTheme } from './theme-manager.js';

// Setup DOM environment before importing module functions
function setupDOM(options = {}) {
  const { systemPrefersDark = true } = options;

  const html = `
    <!DOCTYPE html>
    <html>
    <head></head>
    <body><div id="app"></div></body>
    </html>
  `;

  const dom = new JSDOM(html, {
    url: 'http://localhost/',
    pretendToBeVisual: true,
  });
  const window = dom.window;

  // Mock matchMedia
  window.matchMedia = (query) => {
    return {
      matches: query === '(prefers-color-scheme: dark)' ? systemPrefersDark : false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => true,
    };
  };

  return { dom, window };
}

test('initTheme() respects saved theme preference from localStorage', () => {
  const { window } = setupDOM({ systemPrefersDark: true });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.setItem('textbrush-theme', 'light');

  const theme = initTheme();

  assert.strictEqual(theme, 'light');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'light');
});

test('initTheme() applies saved dark theme from localStorage', () => {
  const { window } = setupDOM({ systemPrefersDark: false });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.setItem('textbrush-theme', 'dark');

  const theme = initTheme();

  assert.strictEqual(theme, 'dark');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'dark');
});

test('initTheme() detects system dark preference when no saved preference', () => {
  const { window } = setupDOM({ systemPrefersDark: true });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.clear();

  const theme = initTheme();

  assert.strictEqual(theme, 'dark');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'dark');
});

test('initTheme() detects system light preference when no saved preference', () => {
  const { window } = setupDOM({ systemPrefersDark: false });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.clear();

  const theme = initTheme();

  assert.strictEqual(theme, 'light');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'light');
});

test('initTheme() falls back to system detection for invalid localStorage value', () => {
  const { window } = setupDOM({ systemPrefersDark: false });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.setItem('textbrush-theme', 'invalid-value');

  const theme = initTheme();

  assert.strictEqual(theme, 'light');
});

test('initTheme() is idempotent - safe to call multiple times', () => {
  const { window } = setupDOM({ systemPrefersDark: true });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.setItem('textbrush-theme', 'dark');

  const first = initTheme();
  const second = initTheme();
  const third = initTheme();

  assert.strictEqual(first, 'dark');
  assert.strictEqual(second, 'dark');
  assert.strictEqual(third, 'dark');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'dark');
});

test('initTheme() applies theme to DOM element', () => {
  const { window } = setupDOM({ systemPrefersDark: true });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.clear();

  initTheme();

  const attr = document.documentElement.getAttribute('data-theme');
  assert(attr === 'light' || attr === 'dark', `Theme should be light or dark, got ${attr}`);
});

test('toggleTheme() toggles from light to dark', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  document.documentElement.setAttribute('data-theme', 'light');

  const newTheme = toggleTheme();

  assert.strictEqual(newTheme, 'dark');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'dark');
});

test('toggleTheme() toggles from dark to light', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  document.documentElement.setAttribute('data-theme', 'dark');

  const newTheme = toggleTheme();

  assert.strictEqual(newTheme, 'light');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'light');
});

test('toggleTheme() persists theme to localStorage', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.clear();
  document.documentElement.setAttribute('data-theme', 'light');

  const newTheme = toggleTheme();

  assert.strictEqual(localStorage.getItem('textbrush-theme'), newTheme);
  assert.strictEqual(localStorage.getItem('textbrush-theme'), 'dark');
});

test('toggleTheme() is symmetric - toggling twice returns to original theme', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  document.documentElement.setAttribute('data-theme', 'light');

  const first = toggleTheme();
  const second = toggleTheme();

  assert.strictEqual(first, 'dark');
  assert.strictEqual(second, 'light');
});

test('toggleTheme() defaults to dark when data-theme attribute is missing', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  document.documentElement.removeAttribute('data-theme');

  const newTheme = toggleTheme();

  assert.strictEqual(newTheme, 'light', 'Should assume dark as default and toggle to light');
  assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'light');
});

test('toggleTheme() always returns valid theme value', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  for (let i = 0; i < 10; i++) {
    document.documentElement.setAttribute('data-theme', 'light');
    const result = toggleTheme();
    assert(result === 'light' || result === 'dark', `Result must be light or dark, got ${result}`);
  }
});

test('getCurrentTheme() returns light theme when set', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  document.documentElement.setAttribute('data-theme', 'light');

  const theme = getCurrentTheme();

  assert.strictEqual(theme, 'light');
});

test('getCurrentTheme() returns dark theme when set', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  document.documentElement.setAttribute('data-theme', 'dark');

  const theme = getCurrentTheme();

  assert.strictEqual(theme, 'dark');
});

test('getCurrentTheme() defaults to dark when attribute is not set', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  document.documentElement.removeAttribute('data-theme');

  const theme = getCurrentTheme();

  assert.strictEqual(theme, 'dark');
});

test('getCurrentTheme() is read-only - does not modify state', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  document.documentElement.setAttribute('data-theme', 'light');
  const before = document.documentElement.getAttribute('data-theme');

  getCurrentTheme();
  getCurrentTheme();
  getCurrentTheme();

  const after = document.documentElement.getAttribute('data-theme');
  assert.strictEqual(before, after);
});

test('getCurrentTheme() always returns valid theme string', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  for (let i = 0; i < 5; i++) {
    document.documentElement.setAttribute('data-theme', 'dark');
    const theme = getCurrentTheme();
    assert(theme === 'light' || theme === 'dark', `Theme must be light or dark, got ${theme}`);
  }
});

test('Integration: init + toggle persists across init calls', () => {
  const { window } = setupDOM({ systemPrefersDark: false });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.clear();
  const initial = initTheme();

  const toggled = toggleTheme();

  document.documentElement.removeAttribute('data-theme');
  const reloaded = initTheme();

  assert.strictEqual(toggled, reloaded, 'Toggled theme should persist and be restored on init');
});

test('Integration: consecutive toggles maintain valid state', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  document.documentElement.setAttribute('data-theme', 'light');

  for (let i = 0; i < 20; i++) {
    const theme = toggleTheme();
    const current = getCurrentTheme();
    assert.strictEqual(theme, current, `toggleTheme and getCurrentTheme should agree`);
  }
});

test('Integration: system preference only used when no saved preference', () => {
  const { window } = setupDOM({ systemPrefersDark: true });
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  localStorage.clear();

  const noSave = initTheme();
  assert.strictEqual(noSave, 'dark', 'Should use system dark preference');

  localStorage.setItem('textbrush-theme', 'light');
  document.documentElement.removeAttribute('data-theme');

  const withSave = initTheme();
  assert.strictEqual(withSave, 'light', 'Should use saved preference over system preference');
});

test('Integration: localStorage always reflects current DOM state after toggle', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;
  global.localStorage = window.localStorage;

  document.documentElement.setAttribute('data-theme', 'light');

  for (let i = 0; i < 5; i++) {
    toggleTheme();
    const savedTheme = localStorage.getItem('textbrush-theme');
    const newDomTheme = document.documentElement.getAttribute('data-theme');

    assert.strictEqual(savedTheme, newDomTheme, 'localStorage should match DOM after toggle');
  }
});
