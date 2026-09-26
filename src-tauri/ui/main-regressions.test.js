import { afterEach, describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { clearMocks } from '@tauri-apps/api/mocks';
import { setupMain } from './main-test-harness.js';

function countCalls(calls, cmd) {
  return calls.filter((entry) => entry.cmd === cmd);
}

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}

test('INIT waits for subscription and observes immediate backend state', async () => {
  const registration = deferred();
  const started = deferred();
  let subscriptions = 0;
  let removals = 0;
  const { window, calls } = await setupMain({
    skipInitWait: true,
    wrapInvoke: invoke => async (cmd, args) => {
      if (cmd === 'plugin:event|listen') {
        subscriptions++;
        started.resolve();
        await registration.promise;
      }
      if (cmd === 'plugin:event|unlisten') removals++;
      return invoke(cmd, args);
    },
    onInit: window => window.__TAURI_INTERNALS__.invoke('plugin:event|emit', {
      event: 'sidecar-message',
      payload: { type: 'state_changed', payload: { state: 'awaiting_model', settled: true } },
    }),
  });
  await started.promise;
  const parallelInit = window.textbrushApp.init();
  assert.equal(countCalls(calls, 'init_generation').length, 0);
  registration.resolve();
  await parallelInit;
  assert.equal(window.textbrushApp.state.backendState.state, 'awaiting_model');
  await window.textbrushApp.init();
  assert.equal(subscriptions, 1);
  assert.equal(countCalls(calls, 'init_generation').length, 1);
  window.dispatchEvent(new window.Event('pagehide'));
  await Promise.resolve();
  assert.equal(removals, 1);
});

test('subscription failure shows a retry action without starting the backend', async () => {
  let subscriptions = 0;
  const { window, document, calls } = await setupMain({
    wrapInvoke: invoke => async (cmd, args) => {
      if (cmd === 'plugin:event|listen' && ++subscriptions === 1) {
        throw new Error('Subscription unavailable');
      }
      return invoke(cmd, args);
    },
  });
  assert.equal(countCalls(calls, 'init_generation').length, 0);
  assert.match(document.getElementById('loading-prompt').textContent, /Subscription unavailable/);
  const retry = document.querySelector('#loading-prompt button');
  assert.ok(retry);
  retry.click();
  await window.textbrushApp.init();
  assert.equal(subscriptions, 2);
  assert.equal(countCalls(calls, 'init_generation').length, 1);
  assert.equal(document.querySelector('#loading-prompt button'), null);
  await window.textbrushApp.init();
  assert.equal(subscriptions, 2);
});

test('retry after INIT rejection reuses the existing subscription', async () => {
  let subscriptions = 0;
  let attempts = 0;
  const { window, document } = await setupMain({
    wrapInvoke: invoke => async (cmd, args) => {
      if (cmd === 'plugin:event|listen') subscriptions++;
      return invoke(cmd, args);
    },
    onInit: () => {
      if (++attempts === 1) throw new Error('Backend unavailable');
    },
  });
  assert.match(document.getElementById('loading-prompt').textContent, /Backend unavailable/);
  document.querySelector('#loading-prompt button').click();
  await window.textbrushApp.init();
  assert.equal(attempts, 2);
  assert.equal(subscriptions, 1);
});

/**
 * Put the app in the state it reaches once a text-only model has been
 * selected and its worker has parked.
 *
 * Loading is deferred, so until a model is acknowledged there is no
 * backend and an output-size change is a local edit with nothing to
 * send. The acknowledgement carries no width/height here, which leaves
 * the launch size in place.
 */
function selectTextModel(window) {
  window.textbrushApp.handleMessage({
    type: 'config_ack',
    payload: {
      model_id: 'flux1-schnell',
      reference_count: 0,
      reference_paths: [],
      preset: null,
      compatible: true,
      incompatibility_reason: null,
      required_model: null,
      settled: true,
    },
  });
  window.textbrushApp.handleMessage({
    type: 'state_changed',
    payload: { state: 'paused', settled: true },
  });
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
    selectTextModel(window);

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
    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });

    const beforePause = countCalls(calls, 'pause_generation').length;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await Promise.resolve();

    const pauseCalls = countCalls(calls, 'pause_generation').slice(beforePause);
    assert.strictEqual(pauseCalls.length, 1, 'one pause command for one Space keydown');
  });

  test('repeated Space keydown events are ignored when event.repeat is true', async () => {
    const { window, document, calls } = await setupMain();
    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });

    const beforePause = countCalls(calls, 'pause_generation').length;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true, repeat: false }));
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true, repeat: true }));
    await Promise.resolve();

    const pauseCalls = countCalls(calls, 'pause_generation').slice(beforePause);
    assert.strictEqual(pauseCalls.length, 1, 'repeat keydown does not trigger extra pause command');
  });

  test('rapid pause toggles are suppressed while command is in flight', async () => {
    const { window, document, calls } = await setupMain();

    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    const beforePause = countCalls(calls, 'pause_generation').length;

    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await Promise.resolve();

    const pauseCalls = countCalls(calls, 'pause_generation').slice(beforePause);
    assert.strictEqual(pauseCalls.length, 1, 'second toggle is ignored until backend state update');
  });

  test('pause in-flight clears only when backend reaches requested state', async () => {
    const { window, document, calls } = await setupMain();
    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });

    const beforePause = countCalls(calls, 'pause_generation').length;
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await Promise.resolve();

    // Mismatched state update should not clear in-flight (request was paused=true)
    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await Promise.resolve();
    assert.strictEqual(
      countCalls(calls, 'pause_generation').slice(beforePause).length,
      1,
      'mismatched state does not unlock another toggle',
    );

    // Matching paused state clears in-flight and allows next toggle (resume)
    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'paused' } });
    document.dispatchEvent(new window.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    await Promise.resolve();
    assert.strictEqual(
      countCalls(calls, 'pause_generation').slice(beforePause).length,
      2,
      'matching state clears in-flight and next toggle is allowed',
    );
  });

  test('pause button syncs with backend paused/generating states', async () => {
    const { window, document } = await setupMain();
    const pauseLabel = document.getElementById('pause-label');
    const pauseIcon = document.getElementById('pause-icon');
    const pauseBtn = document.getElementById('pause-btn');
    assert.ok(pauseLabel);
    assert.ok(pauseIcon);
    assert.ok(pauseBtn);

    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'paused' } });
    assert.strictEqual(pauseLabel.textContent, 'Resume');
    assert.strictEqual(pauseIcon.textContent, '▶');
    assert.strictEqual(pauseBtn.classList.contains('paused'), true);

    window.textbrushApp.handleMessage({ type: 'state_changed', payload: { state: 'generating', prompt: 'test prompt' } });
    assert.strictEqual(pauseLabel.textContent, 'Pause');
    assert.strictEqual(pauseIcon.textContent, '⏸');
    assert.strictEqual(pauseBtn.classList.contains('paused'), false);
  });

  test('resolution controls roll back visual state when config update fails', async () => {
    const { window, document, calls } = await setupMain({ failConfigUpdates: true });
    selectTextModel(window);

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
    const { window, document } = await setupMain({ failConfigUpdates: true });
    selectTextModel(window);

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


describe('Acceptance recovery', () => {
  test('prevents overlapping accepts and restores retry after asynchronous save error', async () => {
    const { window, document, calls } = await setupMain();
    const app = window.textbrushApp;
    app.showLoading(false);
    document.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    document.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    await Promise.resolve();
    assert.equal(countCalls(calls, 'accept_image').length, 1);
    assert.equal(document.getElementById('accept-btn').disabled, true);
    app.handleMessage({type: 'error', payload: {
      operation: 'accept', message: 'Disk full; one image saved', fatal: false,
      saved_paths: ['/output/first.png'],
    }});
    assert.equal(document.getElementById('accept-btn').disabled, false);
    assert.match(document.getElementById('validation-error').textContent, /Disk full/);
    assert.equal(document.getElementById('validation-error').style.display, 'block');
    document.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    await Promise.resolve();
    assert.equal(countCalls(calls, 'accept_image').length, 2);
  });
});


test('accept invoke rejection restores retry and shows a visible error', async () => {
  const { window, document, calls } = await setupMain({failAccept: true});
  window.textbrushApp.accept();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(document.getElementById('accept-btn').disabled, false);
  assert.match(document.getElementById('validation-error').textContent, /Dispatch failed/);
  window.textbrushApp.accept();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(countCalls(calls, 'accept_image').length, 2);
});

test('recovery with only deletion tombstones clears stale visible images', async () => {
  const { window, document } = await setupMain();
  const app = window.textbrushApp;
  app.state.imageList = [{index: 0, path: '/old.png'}];
  app.state.currentIndex = 0;
  app.handleMessage({type: 'image_list', payload: {images: [
    {index: 0, deleted: true, path: '', display_path: ''},
  ]}});
  assert.deepEqual(app.state.imageList, []);
  assert.equal(app.state.currentIndex, -1);
  assert.ok(document.getElementById('current-image').classList.contains('hidden'));
});


test('sidecar crash event replaces loading with a visible fatal error', async (t) => {
  const { window, document, calls } = await setupMain();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  await window.__TAURI_INTERNALS__.invoke('plugin:event|emit', {
    event: 'sidecar-message', payload: { type: 'error', payload: {
      message: 'Backend connection closed unexpectedly (exit status: 7). Check Python runtime installation.',
      fatal: true, operation: 'sidecar_exit',
    } },
  });
  assert.match(document.querySelector('.loading-label').textContent, /Fatal Error: Backend connection closed/);
  assert.equal(document.getElementById('accept-btn').disabled, true);
  assert.equal(document.getElementById('prompt-input').disabled, true);
  document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  await Promise.resolve();
  assert.equal(countCalls(calls, 'accept_image').length, 0);
  assert.equal(countCalls(calls, 'plugin:window|close').length, 0);
  t.mock.timers.tick(3000);
  await Promise.resolve();
  assert.equal(countCalls(calls, 'plugin:window|close').length, 1);
});


test('abort exits after command completion without requiring ABORTED', async (t) => {
  const { window, calls } = await setupMain();
  t.mock.timers.enable({ apis: ['setTimeout'] });
  window.textbrushApp.abort();
  window.textbrushApp.abort();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(countCalls(calls, 'abort_generation').length, 1);
  t.mock.timers.tick(500);
  await Promise.resolve();
  assert.equal(countCalls(calls, 'abort_exit').length, 1);
  window.textbrushApp.handleMessage({ type: 'aborted', payload: {} });
  t.mock.timers.tick(500);
  await Promise.resolve();
  assert.equal(countCalls(calls, 'abort_exit').length, 1);
});

test('abort command failure still invokes the exit cleanup path', async (t) => {
  const { window, calls } = await setupMain({
    wrapInvoke: invoke => (cmd, args) => cmd === 'abort_generation'
      ? Promise.reject(new Error('Backend already gone')) : invoke(cmd, args),
  });
  t.mock.timers.enable({ apis: ['setTimeout'] });
  window.textbrushApp.abort();
  await new Promise(resolve => setImmediate(resolve));
  t.mock.timers.tick(500);
  await Promise.resolve();
  assert.equal(countCalls(calls, 'abort_exit').length, 1);
});
