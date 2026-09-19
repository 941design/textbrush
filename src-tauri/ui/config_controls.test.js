// Unit tests for config_controls helpers.
//
// The tsc output keeps extensionless import specifiers, so the module is built
// in memory instead of importing ./config_controls.js directly.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { EDITING_PRESETS } from './reference_picker.js';

const bundle = await build({
  entryPoints: [new URL('./config_controls.ts', import.meta.url).pathname],
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

const { resolveEditingPreset } = await import(
  `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString('base64')}`
);

test('resolveEditingPreset returns the requested preset', () => {
  for (const preset of EDITING_PRESETS) {
    assert.deepEqual(resolveEditingPreset(preset.id), preset);
  }
});

test('resolveEditingPreset falls back to landscape-medium for null', () => {
  assert.deepEqual(resolveEditingPreset(null), { id: 'landscape-medium', width: 768, height: 576 });
});

test('resolveEditingPreset falls back instead of throwing on an unknown id', () => {
  // textbrush/config.py does not validate the preset, so an arbitrary string
  // can reach the frontend through config_ack.
  const warnings = [];
  const original = console.warn;
  console.warn = message => warnings.push(message);
  try {
    assert.deepEqual(resolveEditingPreset('not-a-preset'),
      { id: 'landscape-medium', width: 768, height: 576 });
    assert.equal(warnings.length, 1, 'unknown preset is reported once');
    assert.match(warnings[0], /not-a-preset/);
    resolveEditingPreset('not-a-preset');
    assert.equal(warnings.length, 1, 'the same unknown preset is not reported twice');
  } finally {
    console.warn = original;
  }
});
