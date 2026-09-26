// Unit tests for config_controls helpers.
//
// The tsc output keeps extensionless import specifiers, so the module is built
// in memory instead of importing ./config_controls.js directly.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const bundle = await build({
  entryPoints: [fileURLToPath(new URL('./config_controls.ts', import.meta.url))],
  bundle: true,
  format: 'esm',
  write: false,
  logLevel: 'silent',
  plugins: [{
    name: 'tauri-test-bridge',
    setup(builder) {
      builder.onResolve({ filter: /^@tauri-apps\/api\// }, args => ({ path: args.path, namespace: 'tauri-test' }));
      builder.onLoad({ filter: /.*/, namespace: 'tauri-test' }, () => ({
        contents: 'export const invoke=async()=>null;',
        loader: 'js',
      }));
    },
  }],
});

const { resolutionAtStep, getResolutionIndex, SUPPORTED_RATIOS } = await import(
  `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`
);

test('every ratio is in the one output-size group, sorted widest to tallest', () => {
  // Height/width ascending: 4:1 (0.25) through 1:1 (1.0) to 9:16 (1.78).
  assert.deepEqual(SUPPORTED_RATIOS, ['4:1', '3:1', '16:9', '4:3', '1:1', '4:5', '3:4', '9:16']);
  const heightOverWidth = SUPPORTED_RATIOS.map(ratio => {
    const [w, h] = ratio.split(':').map(Number);
    return h / w;
  });
  assert.deepEqual(heightOverWidth, [...heightOverWidth].sort((a, b) => a - b));
});

test('the 4:3 and 3:4 ladders are the landscape and portrait preset sizes', () => {
  // The backend still names these six sizes landscape-small/medium/large
  // and portrait-small/medium/large (textbrush/validation.py), so a
  // config file or --preset keeps resolving to an offered size.
  assert.deepEqual([0, 1, 2].map(step => resolutionAtStep('4:3', step)), [
    { width: 512, height: 384 }, { width: 768, height: 576 }, { width: 1024, height: 768 },
  ]);
  assert.deepEqual([0, 1, 2].map(step => resolutionAtStep('3:4', step)), [
    { width: 384, height: 512 }, { width: 576, height: 768 }, { width: 768, height: 1024 },
  ]);
});

test('a ladder step carries across ratios and clamps to the shorter ladder', () => {
  // 4:1 has only two entries; switching to it from the third step of
  // 1:1 must land on its largest size, not fall back to its smallest.
  assert.deepEqual(resolutionAtStep('4:1', 2), { width: 1600, height: 400 });
  assert.deepEqual(resolutionAtStep('1:1', 2), { width: 1024, height: 1024 });
  assert.deepEqual(resolutionAtStep('1:1', -1), { width: 256, height: 256 });
  assert.deepEqual(resolutionAtStep('not-a-ratio', 0), { width: 256, height: 256 });
});

test('the ladder index round-trips through the dimensions', () => {
  for (const ratio of SUPPORTED_RATIOS) {
    for (const step of [0, 1, 2]) {
      const { width, height } = resolutionAtStep(ratio, step);
      assert.equal(resolutionAtStep(ratio, getResolutionIndex(ratio, width, height)).width, width);
    }
  }
});
