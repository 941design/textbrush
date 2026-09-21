import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyPickedPaths, removeReference, replaceReference, previewLabel,
  compatibilityMessage, adoptModelCapabilities, maxReferencesFor,
  isEditingModel, MAX_REFERENCES,
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

test('a per-model limit caps the picked references, not the global maximum', () => {
  const result = applyPickedPaths([], ['a.png', 'b.png'], 1);
  assert.deepEqual(result.references, ['a.png']);
  assert.match(result.errors[0], /limit of 1/);
});

test('reference capability is per model: none, required, or optional', () => {
  assert.equal(maxReferencesFor('flux1-schnell'), 0);
  assert.equal(isEditingModel('flux1-schnell'), false);
  // FLUX.2 accepts references without requiring them, so it is both
  // reference-capable and usable from a prompt alone.
  assert.equal(maxReferencesFor('flux2-klein-4b'), 4);
  assert.equal(isEditingModel('flux2-klein-4b'), true);
  assert.equal(compatibilityMessage('flux2-klein-4b', 0), null);
  // An unknown model accepts nothing, so the picker stays disabled
  // rather than offering references no engine would take.
  assert.equal(maxReferencesFor(null), 0);
  assert.equal(maxReferencesFor('not-a-model'), 0);
});

test('the backend catalogue replaces the mirrored cardinality table', () => {
  adoptModelCapabilities([
    { id: 'future-model', displayName: 'Future', minReferences: 2, maxReferences: 3, available: true },
  ]);
  try {
    assert.equal(maxReferencesFor('future-model'), 3);
    assert.equal(maxReferencesFor('flux2-klein-4b'), 0, 'catalogue replaces, never merges');
    assert.match(compatibilityMessage('future-model', 1), /requires between 2 and 3/);
  } finally {
    adoptModelCapabilities([
      { id: 'flux1-schnell', displayName: 'FLUX.1 [schnell]', minReferences: 0, maxReferences: 0 },
      { id: 'flux1-kontext-dev', displayName: 'FLUX.1 Kontext [dev]', minReferences: 1, maxReferences: 1 },
      { id: 'flux2-klein-4b', displayName: 'FLUX.2 [klein] 4B', minReferences: 0, maxReferences: 4 },
    ]);
  }
});

test('compatibility messages follow every model and count cell', () => {
  const cells = [
    ['flux1-schnell', 0, 0],
    ['flux1-kontext-dev', 1, 1],
    ['flux2-klein-4b', 0, 4],
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
