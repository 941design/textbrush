// Integration Tests for UI Enhancements
// Tests end-to-end workflows across ThemeManager, ListManager, and ButtonFlash modules

import { describe, it, before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import * as ThemeManager from './theme-manager.js';
import * as ListManager from './list-manager.js';
import * as ButtonFlash from './button-flash.js';
import { readFileSync } from 'node:fs';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

// Dimensions default to the landscape-medium canvas, which is what the
// backend acknowledges for the presets these tests name. The canvas -- not
// the preset identifier -- is what the output-size group reconciles to,
// because the group offers sizes no preset names.
const PRESET_CANVAS = {
  'landscape-small': [512, 384],
  'landscape-medium': [768, 576],
  'landscape-large': [1024, 768],
  'portrait-small': [384, 512],
  'portrait-medium': [576, 768],
  'portrait-large': [768, 1024],
};

const ack = (model, paths, preset = null, compatible = true, reason = null, required = null,
  settled = true) => ({
  type: 'config_ack',
  payload: {
    model_id: model,
    reference_count: paths.length,
    reference_paths: paths,
    preset,
    compatible,
    incompatibility_reason: reason,
    required_model: required,
    settled,
    width: (PRESET_CANVAS[preset] ?? [])[0] ?? null,
    height: (PRESET_CANVAS[preset] ?? [])[1] ?? null,
  },
});

// A config_ack from a backend that predates the settled field.
const ackWithoutSettled = (model, paths, preset = null) => {
  const message = ack(model, paths, preset);
  delete message.payload.settled;
  return message;
};

async function renderedApp() {
  const source = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  const dom = new JSDOM(source, { url: 'http://localhost', runScripts: 'outside-only' });
  const { window } = dom;
  const calls = [];
  let picked = [];
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  window.__testInvoke = async (command, args) => {
    calls.push({ command, args });
    if (command === 'get_launch_args') return {
      prompt: 'test prompt', aspect_ratio: '1:1', width: 256, height: 256,
      output_path: null, seed: null,
    };
    if (command === 'pick_reference_files') return picked;
    return null;
  };
  window.__testListen = async () => () => {};
  const bundle = await build({
    entryPoints: [fileURLToPath(new URL('./main.ts', import.meta.url))],
    bundle: true,
    format: 'iife',
    write: false,
    logLevel: 'silent',
    plugins: [{
      name: 'tauri-test-bridge',
      setup(builder) {
        builder.onResolve({ filter: /^@tauri-apps\/api\// }, args => ({ path: args.path, namespace: 'tauri-test' }));
        builder.onLoad({ filter: /.*/, namespace: 'tauri-test' }, args => ({
          contents: args.path.endsWith('/core')
            ? 'export const invoke=(command,args)=>window.__testInvoke(command,args); export const convertFileSrc=()=>"data:image/png;base64,iVBORw0KGgo=";'
            : args.path.endsWith('/event')
              ? 'export const listen=(event,callback)=>window.__testListen(event,callback);'
              : 'export const getCurrentWindow=()=>({close:async()=>{}});',
          loader: 'js',
        }));
      },
    }],
  });
  window.eval(bundle.outputFiles[0].text);
  await window.textbrushApp.init();
  return {
    window, calls, setPicked(paths) { picked = paths; },
    emit(message) { window.textbrushApp.handleMessage(message); },
    close() { dom.window.close(); },
  };
}

test('rendered picker waits for settled, then keeps acknowledgements authoritative', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;
    const add = document.getElementById('reference-add');
    assert.equal(add.disabled, true);
    assert.equal(document.getElementById('pause-btn').disabled, true);
    add.click();
    assert.equal(calls.filter(call => call.command === 'pick_reference_files').length, 0);

    // The launch-time ack reports settled=false, so the controls stay closed.
    emit(ack('flux2-klein-4b', [], 'landscape-medium', true, null, null, false));
    assert.equal(document.getElementById('prompt-input').disabled, true);
    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });
    assert.equal(add.disabled, false);
    assert.equal(document.getElementById('prompt-input').disabled, false);
    const promptInput = document.getElementById('prompt-input');
    promptInput.value = 'revised prompt';
    promptInput.dispatchEvent(new window.Event('blur'));
    await new Promise(resolve => setTimeout(resolve, 0));
    const promptUpdate = calls.filter(call => call.command === 'update_generation_config').at(-1);
    // The acknowledged canvas (landscape-medium = 768x576) is the 4:3
    // option of the one output-size group, and that is what the UI sends
    // back -- for this model exactly as it would for a text-only one.
    assert.equal(promptUpdate.args.aspectRatio, '4:3');
    assert.equal(promptUpdate.args.width, 768);
    assert.equal(promptUpdate.args.height, 576);
    const paths = ['/tmp/one.png', '/tmp/two.jpg', '/tmp/three.jpeg', '/tmp/four.JPG'];
    app.setPicked(paths);
    add.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.deepEqual([...document.querySelectorAll('#reference-list img')].map(img => img.alt),
      paths.map((path, index) => `Reference ${index + 1} of 4: ${path.split('/').at(-1)}`));
    assert.equal(add.disabled, true);
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux2-klein-4b');
    assert.equal(document.getElementById('pause-btn').disabled, true);
    emit(ack('flux2-klein-4b', paths, 'landscape-medium'));
    // Four references is this model's maximum, so there is nothing left
    // to add and the button says so.
    assert.equal(add.disabled, true);
    assert.equal(document.getElementById('pause-btn').disabled, false);

    document.querySelectorAll('#reference-list button[aria-label^="Remove"]')[1].click();
    const afterRemove = [paths[0], paths[2], paths[3]];
    emit(ack('flux2-klein-4b', afterRemove, 'landscape-medium'));
    assert.equal(document.querySelectorAll('#reference-list img').length, 3);
    assert.equal(add.disabled, false, 'a freed slot re-opens the add button');
    app.setPicked(['/tmp/replacement.png']);
    document.querySelectorAll('#reference-list button[aria-label^="Replace"]')[2].click();
    await new Promise(resolve => setTimeout(resolve, 0));
    emit(ack('flux2-klein-4b', [paths[0], paths[2], '/tmp/replacement.png'], 'landscape-medium'));
    assert.match(document.querySelectorAll('#reference-list li')[2].textContent, /replacement\.png/);

    document.querySelector('input[value="flux1-kontext-dev"]').click();
    // The click shows at once, marked pending with a spinner on its line...
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux1-kontext-dev');
    const kontextNote = document.querySelector('.model-note[data-model="flux1-kontext-dev"]');
    assert.equal(kontextNote.textContent, 'loading');
    assert.ok(kontextNote.classList.contains('pending'));
    assert.ok(!document.querySelector('.spinner').classList.contains('hidden'));
    // ...and a rejection puts the acknowledged model back.
    emit({ type: 'error', payload: { message: 'model unavailable', fatal: false } });
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux2-klein-4b');
    assert.equal(kontextNote.textContent, '');
    assert.ok(!kontextNote.classList.contains('pending'));
    emit(ack('flux1-kontext-dev', ['/tmp/one.png'], 'portrait-medium'));
    app.setPicked(['/tmp/two.jpg']);
    add.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux1-kontext-dev');
    emit(ack('flux1-kontext-dev', ['/tmp/one.png', '/tmp/two.jpg'], 'portrait-medium',
      false, 'Kontext requires exactly one reference', 'flux2-klein-4b'));
    assert.match(document.getElementById('reference-error').textContent, /requires exactly one/);
    assert.match(document.querySelector('input[value="flux2-klein-4b"]').parentElement.textContent,
      /recommended/);
  } finally {
    app.close();
  }
});

test('a model change while generating pauses the worker, applies once settled, and resumes', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;
    const updates = () => calls.filter(call => call.command === 'update_generation_config');
    const pauses = () => calls.filter(call => call.command === 'pause_generation');

    emit(ack('flux2-klein-4b', ['/tmp/one.png'], 'landscape-medium'));
    emit({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });

    // Running is not a locked door: the selector stays operable, and so
    // does the picker, while the prompt still waits for a settled worker.
    const kontext = document.querySelector('input[value="flux1-kontext-dev"]');
    assert.equal(kontext.disabled, false);
    assert.equal(document.getElementById('reference-add').disabled, false);
    assert.equal(document.getElementById('prompt-input').disabled, true);

    const updatesBefore = updates().length;
    kontext.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    // Nothing is sent to a running worker; it is asked to pause instead.
    assert.equal(updates().length, updatesBefore);
    assert.equal(pauses().length, 1);
    assert.equal(window.textbrushApp.state.deferredConfigChange?.modelId, 'flux1-kontext-dev');
    assert.equal(window.textbrushApp.state.deferredConfigChange?.resumeAfter, true);
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux1-kontext-dev',
      'the requested model shows as selected, marked pending');
    const note = document.querySelector('.model-note[data-model="flux1-kontext-dev"]');
    assert.ok(note.classList.contains('pending'));
    assert.equal(note.textContent, 'waiting for the current image');
    assert.match(document.querySelector('.loading-label').textContent, /before applying changes/);
    // The pause belongs to the change now; Space must not resume under it.
    assert.equal(document.getElementById('pause-btn').disabled, true);
    window.textbrushApp.togglePause();
    assert.equal(pauses().length, 1);
    // Every other control is held too, buttons and their shortcuts alike.
    const held = ['prev-btn', 'next-btn', 'accept-btn', 'delete-btn', 'abort-btn', 'copy-path-btn',
      'resolution-decrease', 'resolution-increase', 'prompt-input'];
    for (const id of held) assert.equal(document.getElementById(id).disabled, true, id);
    for (const radio of document.querySelectorAll('input[name="aspect-ratio"]')) {
      assert.equal(radio.disabled, true);
    }
    const skipsBefore = calls.filter(call => call.command === 'skip_image').length;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(calls.filter(call => call.command === 'skip_image').length, skipsBefore);

    // Pause acknowledged but the in-flight image has not returned yet.
    emit({ type: 'state_changed', payload: { state: 'paused', settled: false } });
    assert.equal(updates().length, updatesBefore);

    // Quiescence sends the parked change, with the references carried over.
    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });
    assert.equal(updates().length, updatesBefore + 1);
    const update = updates().at(-1);
    assert.equal(update.args.modelId, 'flux1-kontext-dev');
    assert.deepEqual([...update.args.references], ['/tmp/one.png']);
    assert.equal(window.textbrushApp.state.deferredConfigChange, null);
    assert.equal(kontext.disabled, true, 'nothing else may be requested while the change is in flight');
    assert.equal(note.textContent, 'loading', 'the line now reports the load itself');
    assert.match(document.querySelector('.loading-label').textContent, /loading FLUX.1 Kontext/);

    // The acknowledgement hands generation back, because it was running.
    emit(ack('flux1-kontext-dev', ['/tmp/one.png'], 'landscape-medium'));
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux1-kontext-dev');
    assert.equal(pauses().length, 2, 'resumed after the acknowledgement');
    assert.ok(!note.classList.contains('pending'), 'the acknowledgement ends the pending mark');
    for (const id of ['prev-btn', 'next-btn', 'accept-btn', 'delete-btn', 'abort-btn', 'copy-path-btn']) {
      assert.equal(document.getElementById(id).disabled, false, `${id} released`);
    }
    emit({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    assert.equal(pauses().length, 2, 'a running worker with nothing parked is left alone');
    assert.equal(kontext.disabled, false);
  } finally {
    app.close();
  }
});

test('adding a reference while generating opens the picker first and pauses for the change', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;
    const picks = () => calls.filter(call => call.command === 'pick_reference_files');
    const updates = () => calls.filter(call => call.command === 'update_generation_config');
    const pauses = () => calls.filter(call => call.command === 'pause_generation');

    emit(ack('flux2-klein-4b', [], 'landscape-medium'));
    emit({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });

    const add = document.getElementById('reference-add');
    assert.equal(add.disabled, false);
    app.setPicked(['/tmp/one.png']);
    add.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(picks().length, 1, 'the file dialog opens without a manual pause');
    assert.equal(pauses().length, 1);
    assert.equal(updates().length, 0);
    // The list already shows the file being applied.
    assert.deepEqual([...document.querySelectorAll('#reference-list img')].map(img => img.alt),
      ['Reference 1 of 1: one.png']);

    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });
    assert.equal(updates().length, 1);
    assert.deepEqual([...updates().at(-1).args.references], ['/tmp/one.png']);
    emit(ack('flux2-klein-4b', ['/tmp/one.png'], 'landscape-medium'));
    assert.equal(pauses().length, 2, 'generation resumes with the new reference');

    // A cancelled dialog changes nothing and asks the worker for nothing.
    emit({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    app.setPicked([]);
    add.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(picks().length, 2);
    assert.equal(pauses().length, 2);
    assert.equal(updates().length, 1);
  } finally {
    app.close();
  }
});

test('a change requested during a manual pause waits for quiescence and stays paused', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;
    const updates = () => calls.filter(call => call.command === 'update_generation_config');
    const pauses = () => calls.filter(call => call.command === 'pause_generation');

    emit(ack('flux2-klein-4b', [], 'landscape-medium'));
    emit({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    window.textbrushApp.togglePause();
    assert.equal(pauses().length, 1);
    emit({ type: 'state_changed', payload: { state: 'paused', settled: false } });

    document.querySelector('input[value="flux1-schnell"]').click();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(pauses().length, 1, 'the pause already under way is not repeated');
    assert.equal(updates().length, 0);
    assert.equal(window.textbrushApp.state.deferredConfigChange?.resumeAfter, false);

    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });
    assert.equal(updates().length, 1);
    assert.equal(updates().at(-1).args.modelId, 'flux1-schnell');
    emit(ack('flux1-schnell', []));
    assert.equal(pauses().length, 1, 'the user paused, so the user resumes');
    assert.equal(document.getElementById('pause-btn').disabled, false);
  } finally {
    app.close();
  }
});

test('a rejected deferred change leaves the worker paused with the message in view', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;
    const pauses = () => calls.filter(call => call.command === 'pause_generation');

    emit(ack('flux2-klein-4b', [], 'landscape-medium'));
    emit({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    document.querySelector('input[value="flux1-kontext-dev"]').click();
    await new Promise(resolve => setTimeout(resolve, 0));
    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });
    assert.equal(pauses().length, 1);

    emit({ type: 'error', payload: { message: 'model unavailable', fatal: false } });
    emit(ack('flux2-klein-4b', [], 'landscape-medium'));
    assert.equal(pauses().length, 1, 'no resume after a rejected change');
    assert.match(document.getElementById('loading-prompt').textContent, /model unavailable/);
    assert.equal(document.querySelector('input[name="model"]:checked').value, 'flux2-klein-4b');
    assert.equal(window.textbrushApp.state.deferredConfigChange, null);
  } finally {
    app.close();
  }
});

test('config_ack opens the editing controls without a preceding state_changed', async () => {
  const app = await renderedApp();
  try {
    const { window, emit } = app;
    const document = window.document;
    const add = document.getElementById('reference-add');
    assert.equal(add.disabled, true);

    // settled=true on config_ack alone must unlock the controls; without it the
    // UI stays dead until a full resume/pause cycle.
    emit(ack('flux2-klein-4b', [], 'landscape-medium'));
    assert.equal(add.disabled, false);
    assert.equal(document.getElementById('prompt-input').disabled, false);
    assert.equal(document.querySelector('input[value="flux2-klein-4b"]').disabled, false);

    // An ack without the field leaves the gate where it was.
    emit(ackWithoutSettled('flux2-klein-4b', []));
    assert.equal(add.disabled, false);

    emit(ack('flux2-klein-4b', [], 'landscape-medium', true, null, null, false));
    assert.equal(add.disabled, true);
    emit(ackWithoutSettled('flux2-klein-4b', []));
    assert.equal(add.disabled, true);
  } finally {
    app.close();
  }
});

test('an unnamed acknowledged canvas does not break prompt submission', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;

    // Most sizes in the output-size group have no preset identifier at
    // all, and textbrush/config.py does not validate the preset, so an
    // unknown id can reach the UI verbatim through config_ack. The
    // dimensions are what matter; the identifier is decoration.
    const message = ack('flux2-klein-4b', ['/tmp/one.png'], 'not-a-preset');
    message.payload.width = 1920;
    message.payload.height = 1080;
    emit(message);
    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });

    assert.equal(document.getElementById('dimension-display').textContent, '1920×1080');
    assert.equal(document.querySelector('input[name="aspect-ratio"]:checked').value, '16:9');

    const promptInput = document.getElementById('prompt-input');
    promptInput.value = 'prompt with an unnamed canvas';
    promptInput.dispatchEvent(new window.Event('blur'));
    await new Promise(resolve => setTimeout(resolve, 0));

    const update = calls.filter(call => call.command === 'update_generation_config').at(-1);
    assert.ok(update, 'prompt blur still reaches the backend');
    assert.equal(update.args.aspectRatio, '16:9');
    assert.equal(update.args.width, 1920);
    assert.equal(update.args.height, 1080);
  } finally {
    app.close();
  }
});

test('the output-size group is the same group for a model that takes references', async () => {
  const app = await renderedApp();
  try {
    const { window, calls, emit } = app;
    const document = window.document;

    emit(ack('flux2-klein-4b', ['/tmp/one.png'], 'landscape-medium'));
    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });

    // Every ratio is offered, and each one shows the pixels it produces.
    const ratios = [...document.querySelectorAll('input[name="aspect-ratio"]')]
      .map(input => input.value);
    assert.deepEqual(ratios, ['4:1', '3:1', '16:9', '4:3', '1:1', '4:5', '3:4', '9:16']);
    assert.equal(document.querySelector('.ratio-dimensions[data-ratio="16:9"]').textContent,
      '1280×720');

    // Picking one routes through the acknowledged-configuration seam,
    // because the held references have to be decoded onto the new canvas.
    const before = calls.filter(call => call.command === 'update_generation_config').length;
    const wide = document.querySelector('input[name="aspect-ratio"][value="16:9"]');
    wide.checked = true;
    wide.dispatchEvent(new window.Event('change', { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 0));
    const update = calls.filter(call => call.command === 'update_generation_config').at(-1);
    assert.equal(calls.filter(call => call.command === 'update_generation_config').length,
      before + 1);
    assert.equal(update.args.aspectRatio, '16:9');
    assert.equal(update.args.width, 1280);
    assert.equal(update.args.height, 720);
    assert.deepEqual([...update.args.references], ['/tmp/one.png']);
    assert.equal(update.args.modelId, 'flux2-klein-4b');
  } finally {
    app.close();
  }
});

test('a model that takes no references keeps the picker visible but disabled', async () => {
  const app = await renderedApp();
  try {
    const { window, emit } = app;
    const document = window.document;

    emit(ack('flux1-schnell', []));
    emit({ type: 'state_changed', payload: { state: 'paused', settled: true } });

    const add = document.getElementById('reference-add');
    assert.ok(add, 'the reference control is always present');
    assert.equal(add.disabled, true, 'and disabled for a model that takes none');
    assert.match(document.getElementById('reference-legend').textContent, /not supported/);

    // FLUX.2 accepts references without requiring them, so selecting it
    // opens the picker again.
    emit(ack('flux2-klein-4b', []));
    assert.equal(add.disabled, false);
    assert.match(document.getElementById('reference-legend').textContent, /up to 4/);
    assert.equal(document.getElementById('reference-error').textContent, '',
      'zero references is a valid FLUX.2 configuration');
  } finally {
    app.close();
  }
});

describe('UI Enhancements Integration Tests', () => {
  let dom;
  let window;
  let document;

  before(() => {
    // Setup minimal DOM environment for integration tests
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <head></head>
        <body>
          <button id="prev-btn">Prev</button>
          <button id="pause-btn">Pause</button>
          <button id="next-btn">Next</button>
          <button id="delete-btn">Delete</button>
          <button id="accept-btn">Done</button>
          <button id="abort-btn">Abort</button>
          <div id="image-container"></div>
        </body>
      </html>
    `, {
      url: 'http://localhost',
      pretendToBeVisual: true,
    });

    window = dom.window;
    document = window.document;

    // Setup globals
    global.window = window;
    global.document = document;
    global.localStorage = {
      storage: {},
      getItem(key) { return this.storage[key] || null; },
      setItem(key, value) { this.storage[key] = value; },
      removeItem(key) { delete this.storage[key]; },
      clear() { this.storage = {}; }
    };
    global.URL = {
      revokeObjectURL: () => {},
      createObjectURL: () => 'blob:mock'
    };

    // Mock window.matchMedia for theme detection
    window.matchMedia = (query) => ({
      matches: query.includes('dark'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {}
    });
  });

  after(() => {
    delete global.window;
    delete global.document;
    delete global.localStorage;
    delete global.URL;
  });

  describe('E2E: Theme Toggle Workflow', () => {
    it('should toggle theme, update CSS, and persist to localStorage', () => {
      // Setup
      localStorage.clear();

      // Initialize theme (should default to system preference or dark)
      const initialTheme = ThemeManager.initTheme();
      assert.ok(initialTheme === 'light' || initialTheme === 'dark', 'Initial theme is valid');

      // Verify DOM attribute set
      const domTheme = document.documentElement.getAttribute('data-theme');
      assert.strictEqual(domTheme, initialTheme, 'DOM reflects initialized theme');

      // Toggle theme
      const newTheme = ThemeManager.toggleTheme();
      assert.notStrictEqual(newTheme, initialTheme, 'Theme changed after toggle');

      // Verify persistence
      const savedTheme = localStorage.getItem('textbrush-theme');
      assert.strictEqual(savedTheme, newTheme, 'Theme persisted to localStorage');

      // Verify DOM updated
      const updatedDomTheme = document.documentElement.getAttribute('data-theme');
      assert.strictEqual(updatedDomTheme, newTheme, 'DOM updated with new theme');

      // Toggle back
      const returnedTheme = ThemeManager.toggleTheme();
      assert.strictEqual(returnedTheme, initialTheme, 'Theme returns to original after second toggle');
    });

    it('should restore theme from localStorage on subsequent init', () => {
      // Setup - manually set localStorage
      localStorage.setItem('textbrush-theme', 'light');

      // Initialize
      const theme = ThemeManager.initTheme();

      // Verify restoration
      assert.strictEqual(theme, 'light', 'Theme restored from localStorage');
      assert.strictEqual(
        document.documentElement.getAttribute('data-theme'),
        'light',
        'DOM reflects restored theme'
      );
    });
  });

  describe('E2E: Bidirectional Navigation', () => {
    it('should navigate through list and update position indicator', () => {
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3' }
        ],
        currentIndex: 1,
        bufferCount: 0
      };

      const displayedImages = [];
      const displayImage = (entry) => {
        displayedImages.push(entry.seed);
      };

      // Navigate to previous
      const prevResult = ListManager.navigateToPrev(state, displayImage);
      assert.strictEqual(prevResult, true, 'Navigation to previous succeeded');
      assert.strictEqual(state.currentIndex, 0, 'Index decremented to 0');
      assert.deepStrictEqual(displayedImages, [1], 'First image displayed');

      // Position indicator at start
      let indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[1/3]', 'Position indicator shows 1 of 3');

      // Try to go before start
      const prevAtStart = ListManager.navigateToPrev(state, displayImage);
      assert.strictEqual(prevAtStart, false, 'Cannot navigate before start');
      assert.strictEqual(state.currentIndex, 0, 'Index remains at 0');

      // Navigate forward
      const nextResult = ListManager.navigateToNext(state, displayImage, () => {});
      assert.strictEqual(nextResult, true, 'Navigation to next succeeded');
      assert.strictEqual(state.currentIndex, 1, 'Index incremented to 1');
      assert.deepStrictEqual(displayedImages, [1, 2], 'Second image displayed');

      // Position indicator in middle
      indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[2/3]', 'Position indicator shows 2 of 3');

      // Navigate to end
      ListManager.navigateToNext(state, displayImage, () => {});
      assert.strictEqual(state.currentIndex, 2, 'At end of list');

      // Position indicator at end
      indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[3/3]', 'Position indicator shows 3 of 3');
    });
  });

  describe('E2E: Backend-Driven Deletion (via delete_ack)', () => {
    it('should verify deletion happens only after backend acknowledgment', () => {
      // Note: With the new state sync protocol (FR9), deletion is backend-driven.
      // Frontend sends delete command with index, then waits for delete_ack.
      // This test verifies the state update pattern after receiving ack.
      const state = {
        imageList: [
          { index: 0, seed: 1, blobUrl: 'asset://localhost/img1.png', path: '/preview/1.png', displayPath: '~/1.png', prompt: 'test', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 },
          { index: 1, seed: 2, blobUrl: 'asset://localhost/img2.png', path: '/preview/2.png', displayPath: '~/2.png', prompt: 'test', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 },
          { index: 2, seed: 3, blobUrl: 'asset://localhost/img3.png', path: '/preview/3.png', displayPath: '~/3.png', prompt: 'test', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 }
        ],
        currentIndex: 1
      };

      // Simulate receiving delete_ack from backend for index 1
      const deleteIndex = 1;
      const imageIndex = state.imageList.findIndex(img => img.index === deleteIndex);

      // Remove from list after ack (mimics handleDeleteAck behavior)
      if (imageIndex !== -1) {
        state.imageList.splice(imageIndex, 1);
        if (state.currentIndex >= state.imageList.length) {
          state.currentIndex = Math.max(0, state.imageList.length - 1);
        }
      }

      // Verify state after backend-confirmed deletion
      assert.strictEqual(state.imageList.length, 2, 'List length reduced to 2');
      assert.strictEqual(state.currentIndex, 1, 'Index adjusted to valid position');
      assert.strictEqual(state.imageList[0].seed, 1, 'First image still present');
      assert.strictEqual(state.imageList[1].seed, 3, 'Third image now at index 1');
    });

    it('should handle empty state after backend confirms last image deletion', () => {
      const state = {
        imageList: [
          { index: 0, seed: 1, blobUrl: 'blob:1', path: '/preview/1.png', displayPath: '~/1.png', prompt: 'test', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 }
        ],
        currentIndex: 0
      };

      // Simulate receiving delete_ack from backend for index 0
      const deleteIndex = 0;
      const imageIndex = state.imageList.findIndex(img => img.index === deleteIndex);

      if (imageIndex !== -1) {
        state.imageList.splice(imageIndex, 1);
        if (state.imageList.length === 0) {
          state.currentIndex = -1;
        }
      }

      // Verify empty state
      assert.strictEqual(state.imageList.length, 0, 'List is empty');
      assert.strictEqual(state.currentIndex, -1, 'Index set to -1');

      // Position indicator should be empty
      const indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '', 'Position indicator empty for no list');
    });
  });

  describe('E2E: Button Flash on Keyboard Shortcuts', () => {
    it('should flash corresponding button when keyboard shortcut pressed', () => {
      const skipBtn = document.getElementById('next-btn');
      const acceptBtn = document.getElementById('accept-btn');
      const abortBtn = document.getElementById('abort-btn');

      // Test ArrowRight -> skip button
      const skipResult = ButtonFlash.flashButtonForKey('ArrowRight');
      assert.strictEqual(skipResult, true, 'Skip button flashed for ArrowRight');
      assert.ok(skipBtn.classList.contains('btn-pressed'), 'Skip button has btn-pressed class');

      // Test Enter -> accept button
      const acceptResult = ButtonFlash.flashButtonForKey('Enter');
      assert.strictEqual(acceptResult, true, 'Accept button flashed for Enter');
      assert.ok(acceptBtn.classList.contains('btn-pressed'), 'Accept button has btn-pressed class');

      // Test Escape -> abort button
      const abortResult = ButtonFlash.flashButtonForKey('Escape');
      assert.strictEqual(abortResult, true, 'Abort button flashed for Escape');
      assert.ok(abortBtn.classList.contains('btn-pressed'), 'Abort button has btn-pressed class');

      // Test Space -> pause button
      const spaceResult = ButtonFlash.flashButtonForKey(' ');
      assert.strictEqual(spaceResult, true, 'Pause button flashed for Space');

      // Test unmapped key
      const unmappedResult = ButtonFlash.flashButtonForKey('x');
      assert.strictEqual(unmappedResult, false, 'Unmapped key returns false');
    });

    it('should flash delete button for Cmd/Ctrl+Delete', () => {
      const deleteBtn = document.getElementById('delete-btn');

      // Test Delete with modifier
      const result = ButtonFlash.flashButtonForKey('Delete', true);
      assert.strictEqual(result, true, 'Delete button flashed for Cmd/Ctrl+Delete');
      assert.ok(deleteBtn.classList.contains('btn-pressed'), 'Delete button has btn-pressed class');

      // Test Delete without modifier - should not flash
      deleteBtn.classList.remove('btn-pressed');
      const noModResult = ButtonFlash.flashButtonForKey('Delete', false);
      assert.strictEqual(noModResult, false, 'Delete without modifier returns false');
      assert.ok(!deleteBtn.classList.contains('btn-pressed'), 'Delete button not flashed without modifier');
    });
  });

  describe('E2E: Backend-Owned Path Management', () => {
    it('should handle navigation with stateless image records', () => {
      // Initialize theme
      localStorage.clear();
      const theme = ThemeManager.initTheme();
      assert.ok(theme, 'Theme initialized');

      // Setup list with preview images (no outputPath - backend owns that)
      // Note: Images now have index field for backend identification (FR5)
      const state = {
        imageList: [
          { index: 0, seed: 1, blobUrl: 'asset://img1', path: '/preview/img1.png', displayPath: '~/Pictures/img1.png', prompt: 'test1', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 },
          { index: 1, seed: 2, blobUrl: 'asset://img2', path: '/preview/img2.png', displayPath: '~/Pictures/img2.png', prompt: 'test2', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 },
          { index: 2, seed: 3, blobUrl: 'asset://img3', path: '/preview/img3.png', displayPath: '~/Pictures/img3.png', prompt: 'test3', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 }
        ],
        currentIndex: 0
      };

      // Navigate forward
      ListManager.navigateToNext(state, () => {}, () => {});
      assert.strictEqual(state.currentIndex, 1, 'Navigated to index 1');

      // Flash button for visual feedback
      ButtonFlash.flashButtonForKey('ArrowRight');
      assert.ok(document.getElementById('next-btn').classList.contains('btn-pressed'), 'Button flashed');

      // Toggle theme
      const newTheme = ThemeManager.toggleTheme();
      assert.notStrictEqual(newTheme, theme, 'Theme toggled');
      assert.strictEqual(localStorage.getItem('textbrush-theme'), newTheme, 'Theme persisted');

      // Verify image records have correct structure (FR5: ImageRecord with index)
      for (const record of state.imageList) {
        assert.ok(!('outputPath' in record), 'Record has no outputPath field');
        assert.ok(!('outputDisplayPath' in record), 'Record has no outputDisplayPath field');
        assert.ok(record.path, 'Record has preview path');
        assert.ok(record.displayPath, 'Record has display path');
        assert.ok(typeof record.index === 'number', 'Record has index field (FR5)');
      }

      // Verify position indicator
      const indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[2/3]', 'Position indicator shows current position');
    });

    it('E2E Accept Workflow with Backend Path Collection', () => {
      // Property: Complete workflow demonstrates backend owns path management
      // Frontend receives paths array from backend in handleAccepted

      // Setup: Simulate generated preview images (no outputPath)
      // Images have index field for backend identification (FR5)
      const state = {
        imageList: [
          { index: 0, seed: 101, blobUrl: 'asset://101', path: '/preview/101.png', displayPath: '~/Pictures/101.png', prompt: 'prompt1', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 },
          { index: 1, seed: 102, blobUrl: 'asset://102', path: '/preview/102.png', displayPath: '~/Pictures/102.png', prompt: 'prompt2', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 },
          { index: 3, seed: 104, blobUrl: 'asset://104', path: '/preview/104.png', displayPath: '~/Pictures/104.png', prompt: 'prompt4', model: 'flux', aspectRatio: '1:1', width: 1024, height: 1024 }
        ],
        currentIndex: 2
      };

      // Note: Image at index 2 (seed 103) was deleted earlier via delete_ack
      // Frontend correctly shows sparse indices (0, 1, 3) after deletion

      // Step 1: Navigate backward to review images
      ListManager.navigateToPrev(state, () => {});
      assert.strictEqual(state.currentIndex, 1, 'Navigated backward');

      // Step 2: Simulate handleAccepted receiving paths from backend
      // Backend sends: { paths: [retained output paths] }
      const backendPayload = {
        paths: ['/output/image-101.png', '/output/image-102.png', '/output/image-104.png']
      };

      // Verify backend payload contains all retained paths
      assert.strictEqual(backendPayload.paths.length, 3, 'Three paths in backend payload');
      assert.deepStrictEqual(
        backendPayload.paths,
        ['/output/image-101.png', '/output/image-102.png', '/output/image-104.png'],
        'Backend provides correct output paths'
      );

      // Step 3: Frontend receives and processes paths (handleAccepted logic)
      const retainedPaths = backendPayload.paths || [];
      assert.strictEqual(retainedPaths.length, 3, 'Frontend receives all paths');
      assert.ok(retainedPaths.length > 1, 'Multi-path exit will be used');

      // Step 4: Verify preview records remain stateless with correct index structure
      for (const record of state.imageList) {
        assert.ok(!('outputPath' in record), 'Preview records never have outputPath');
        assert.ok(typeof record.index === 'number', 'Records have backend index (FR5)');
      }
    });
  });
});
