import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyPickedPaths, removeReference, replaceReference, previewLabel,
  compatibilityMessage, EDITING_PRESETS, MAX_REFERENCES,
} from './reference_picker.js';

test('picked paths keep order and duplicates, while formats and limit are enforced', () => {
  const paths = ['a.png', 'a.png', 'b.JPG', 'c.jpeg', 'fifth.png', 'bad.bmp'];
  const result = applyPickedPaths([], paths);
  assert.deepEqual(result.references, paths.slice(0, MAX_REFERENCES));
  assert.match(result.errors[0], /limit of 4/);
  assert.match(result.errors[1], /bad\.bmp.*supported formats/);
});

test('remove and replace change one position and preserve other entries', () => {
  const paths = ['a.png', 'b.jpg', 'c.jpeg'];
  assert.deepEqual(removeReference(paths, 1), ['a.png', 'c.jpeg']);
  assert.deepEqual(replaceReference(paths, 1, 'd.JPG').references, ['a.png', 'd.JPG', 'c.jpeg']);
  assert.deepEqual(replaceReference(paths, 1, 'bad.bmp').references, paths);
});

test('preview names the position and basename', () => {
  assert.equal(previewLabel('/tmp/person.jpg', 1), 'Reference 2 of 4: person.jpg');
  assert.equal(previewLabel('C:\\photos\\person.jpg', 0, 2), 'Reference 1 of 2: person.jpg');
});

test('preset identifiers and dimensions match the shared backend table', () => {
  assert.deepEqual(EDITING_PRESETS.map(preset => [preset.id, preset.width, preset.height]), [
    ['landscape-small', 512, 384], ['landscape-medium', 768, 576], ['landscape-large', 1024, 768],
    ['portrait-small', 384, 512], ['portrait-medium', 576, 768], ['portrait-large', 768, 1024],
  ]);
});

test('compatibility messages follow every model and count cell', () => {
  const cells = [
    ['flux1-schnell', 0, 0],
    ['flux1-kontext-dev', 1, 1],
    ['flux2-klein-4b', 1, 4],
  ];
  for (const [model, min, max] of cells) {
    for (let count = 0; count <= 5; count++) {
      const message = compatibilityMessage(model, count);
      if (count >= min && count <= max) assert.equal(message, null);
      else {
        assert.match(message, new RegExp(`${model}.*got ${count}`));
        if (count === 5) assert.match(message, /no supported model accepts more than 4/);
      }
    }
  }
});
