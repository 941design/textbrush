// Exercise the rebuilt application and observe its real Tauri invoke arguments.
import { afterEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { clearMocks } from '@tauri-apps/api/mocks';
import { setupMain } from './main-test-harness.js';

afterEach(() => {
  clearMocks();
  delete global.window;
  delete global.document;
  delete global.HTMLElement;
  delete global.localStorage;
});

function countCalls(calls, cmd) {
  return calls.filter(entry => entry.cmd === cmd);
}

for (const seed of [0, 42, null, undefined]) {
  test(`INIT preserves launch seed ${seed}`, async () => {
    const { calls } = await setupMain({ launchArgs: { seed } });
    const initializations = countCalls(calls, 'init_generation');
    assert.equal(initializations.length, 1);
    assert.equal(initializations[0].args.seed, seed ?? null);
  });
}


test('native launch options reach the actual INIT invoke payload', async () => {
  const { calls } = await setupMain({ launchArgs: {
    prompt: 'cat', output_path: '/output path/cat.png', seed: 0,
    aspect_ratio: '3:4', width: 576, height: 768,
    model_id: 'flux2-klein-4b', references: ['/a b.png', '/c.png', '/a b.png'],
    preset: 'portrait-medium', buffer_max: 3,
  } });
  assert.deepEqual(countCalls(calls, 'init_generation').map(call => call.args), [{
    prompt: 'cat', outputPath: '/output path/cat.png', seed: 0,
    aspectRatio: '3:4', width: 576, height: 768,
    modelId: 'flux2-klein-4b', references: ['/a b.png', '/c.png', '/a b.png'],
    preset: 'portrait-medium', bufferMax: 3,
  }]);
});
