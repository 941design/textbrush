import test from 'node:test';
import assert from 'node:assert';
import { JSDOM } from 'jsdom';
import { flashButton, flashButtonById, flashButtonForKey } from './button-flash.js';

function setupDOM() {
  const html = `
    <!DOCTYPE html>
    <html>
    <head></head>
    <body>
      <button id="previous-btn">Previous</button>
      <button id="pause-btn">Pause</button>
      <button id="skip-btn">Skip</button>
      <button id="accept-btn">Accept</button>
      <button id="abort-btn">Abort</button>
      <div id="image-container"></div>
    </body>
    </html>
  `;

  const dom = new JSDOM(html);
  const window = dom.window;

  window.matchMedia = (query) => ({
    matches: query === '(prefers-reduced-motion: reduce)',
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => true,
  });

  return { dom, window };
}

test('flashButton - Null Safety Property', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  assert.doesNotThrow(() => flashButton(null));
});

test('flashButton - Undefined Safety Property', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  assert.doesNotThrow(() => flashButton(undefined));
});

test('flashButton - Returns Void', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButton(null);
  assert.strictEqual(result, undefined);
});

test('flashButton - Class Addition Property', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const button = window.document.getElementById('skip-btn');
  assert(!button.classList.contains('btn-pressed'));

  flashButton(button);

  assert(button.classList.contains('btn-pressed'));
});

test('flashButton - Class Not Removed Synchronously', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const button = window.document.getElementById('accept-btn');
  flashButton(button);

  assert(button.classList.contains('btn-pressed'));
});

test('flashButton - Idempotency: Multiple Rapid Calls', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const button = window.document.getElementById('skip-btn');

  flashButton(button);
  flashButton(button);
  flashButton(button);

  assert(button.classList.contains('btn-pressed'), 'Class should be added');
});

test('flashButton - Multiple Calls Without Errors', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const button = window.document.getElementById('accept-btn');

  assert.doesNotThrow(() => {
    for (let i = 0; i < 10; i++) {
      flashButton(button);
    }
  });
});

test('flashButton - Falsy Elements Are Handled', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  assert.doesNotThrow(() => flashButton(null));
  assert.doesNotThrow(() => flashButton(undefined));
  assert.doesNotThrow(() => flashButton(false));
  assert.doesNotThrow(() => flashButton(0));
  assert.doesNotThrow(() => flashButton(''));
});

test('flashButtonById - Get Element By ID Call', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  let queriedId = null;
  const originalGetElementById = window.document.getElementById;
  window.document.getElementById = (id) => {
    queriedId = id;
    return originalGetElementById.call(window.document, id);
  };

  flashButtonById('skip-btn');

  assert.strictEqual(queriedId, 'skip-btn');

  window.document.getElementById = originalGetElementById;
});

test('flashButtonById - Return True When Found', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonById('skip-btn');

  assert.strictEqual(result, true);
});

test('flashButtonById - Return False When Not Found', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonById('nonexistent-btn');

  assert.strictEqual(result, false);
});

test('flashButtonById - Returns Boolean Always', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const results = [
    flashButtonById('skip-btn'),
    flashButtonById('missing-btn'),
    flashButtonById('accept-btn'),
    flashButtonById('does-not-exist'),
  ];

  results.forEach((result) => {
    assert.strictEqual(typeof result, 'boolean');
  });
});

test('flashButtonById - Add Class When Found', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const button = window.document.getElementById('skip-btn');
  assert(!button.classList.contains('btn-pressed'));

  flashButtonById('skip-btn');

  assert(button.classList.contains('btn-pressed'));
});

test('flashButtonById - No DOM Changes When Not Found', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const allButtons = window.document.querySelectorAll('button');
  const classedBefore = Array.from(allButtons).filter((b) =>
    b.classList.contains('btn-pressed')
  );

  flashButtonById('nonexistent-btn');

  const classedAfter = Array.from(allButtons).filter((b) =>
    b.classList.contains('btn-pressed')
  );

  assert.strictEqual(classedBefore.length, classedAfter.length);
});

test('flashButtonById - Handle Various Button ID Formats', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const ids = ['previous-btn', 'skip-btn', 'accept-btn', 'abort-btn', 'image-container'];

  ids.forEach((id) => {
    const result = flashButtonById(id);
    assert.strictEqual(result, true, `Should find button with ID: ${id}`);
  });
});

test('flashButtonForKey - Map ArrowLeft to previous-btn', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('ArrowLeft');

  assert.strictEqual(result, true);
  assert(window.document.getElementById('previous-btn').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Map ArrowRight to skip-btn', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('ArrowRight');

  assert.strictEqual(result, true);
  assert(window.document.getElementById('skip-btn').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Map Space to pause-btn', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey(' ');

  assert.strictEqual(result, true);
  assert(window.document.getElementById('pause-btn').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Map Enter to accept-btn', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('Enter');

  assert.strictEqual(result, true);
  assert(window.document.getElementById('accept-btn').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Map Escape to abort-btn', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('Escape');

  assert.strictEqual(result, true);
  assert(window.document.getElementById('abort-btn').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Map All Keys Correctly', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const keyMappings = {
    ArrowLeft: 'previous-btn',
    ArrowRight: 'skip-btn',
    ' ': 'pause-btn',
    Enter: 'accept-btn',
    Escape: 'abort-btn',
  };

  Object.entries(keyMappings).forEach(([key, btnId]) => {
    const freshWindow = setupDOM().window;
    global.window = freshWindow;
    global.document = freshWindow.document;

    const result = flashButtonForKey(key);
    const button = freshWindow.document.getElementById(btnId);

    assert.strictEqual(result, true, `Key ${key} should map to ${btnId}`);
    assert(button.classList.contains('btn-pressed'), `Button ${btnId} should be flashed for key ${key}`);
  });
});

test('flashButtonForKey - Delete with Cmd to image-container', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('Delete', true);

  assert.strictEqual(result, true);
  assert(window.document.getElementById('image-container').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Backspace with Cmd to image-container', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('Backspace', true);

  assert.strictEqual(result, true);
  assert(window.document.getElementById('image-container').classList.contains('btn-pressed'));
});

test('flashButtonForKey - Delete Without Cmd Ignored', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('Delete', false);

  assert.strictEqual(result, false);
});

test('flashButtonForKey - Backspace Without Cmd Ignored', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const result = flashButtonForKey('Backspace', false);

  assert.strictEqual(result, false);
});

test('flashButtonForKey - Delete Requires Explicit True Modifier', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const withoutModifier = flashButtonForKey('Delete');
  const withFalse = flashButtonForKey('Delete', false);
  const withTrue = flashButtonForKey('Delete', true);

  assert.strictEqual(withoutModifier, false);
  assert.strictEqual(withFalse, false);
  assert.strictEqual(withTrue, true);
});

test('flashButtonForKey - Return False For Unmapped Keys', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const unmappedKeys = ['a', 'b', 'Shift', 'Control', 'Alt', 'Tab', 'Home', 'End'];

  unmappedKeys.forEach((key) => {
    const result = flashButtonForKey(key);
    assert.strictEqual(result, false, `Key ${key} should not be mapped`);
  });
});

test('flashButtonForKey - Unmapped Keys Do Not Modify DOM', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const allButtons = window.document.querySelectorAll('button');
  const classedBefore = Array.from(allButtons).filter((b) =>
    b.classList.contains('btn-pressed')
  );

  flashButtonForKey('UnmappedKey');

  const classedAfter = Array.from(allButtons).filter((b) =>
    b.classList.contains('btn-pressed')
  );

  assert.strictEqual(classedBefore.length, classedAfter.length);
});

test('flashButtonForKey - Return False When Button Missing', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  window.document.getElementById('previous-btn').remove();

  const result = flashButtonForKey('ArrowLeft');

  assert.strictEqual(result, false);
});

test('flashButtonForKey - Handle Gracefully When Button Missing', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  assert.doesNotThrow(() => {
    window.document.getElementById('previous-btn').remove();
    flashButtonForKey('ArrowLeft');

    window.document.getElementById('skip-btn').remove();
    flashButtonForKey('ArrowRight');

    window.document.getElementById('accept-btn').remove();
    flashButtonForKey('Enter');
  });
});

test('flashButtonForKey - Image Container Missing Return False', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  window.document.getElementById('image-container').remove();

  const result = flashButtonForKey('Delete', true);

  assert.strictEqual(result, false);
});

test('Integration - Consistent Return Values Across Module', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const mapResult = flashButtonForKey('Enter');
  const idResult = flashButtonById('accept-btn');

  assert.strictEqual(mapResult, true);
  assert.strictEqual(idResult, true);
});

test('Integration - Rapid Key Presses Without Errors', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  assert.doesNotThrow(() => {
    flashButtonForKey('ArrowLeft');
    flashButtonForKey('ArrowRight');
    flashButtonForKey('Enter');
    flashButtonForKey('Escape');
    flashButtonForKey('Delete', true);
  });
});

test('Integration - Preserve DOM State After Invalid Operations', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const skipBtn = window.document.getElementById('skip-btn');
  const beforeClasses = skipBtn.className;

  flashButtonForKey('InvalidKey');
  flashButtonById('nonexistent-id');
  flashButton(null);

  const afterClasses = skipBtn.className;

  assert.strictEqual(beforeClasses, afterClasses);
});

test('Integration - Button ID Semantics Across Functions', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const buttons = ['previous-btn', 'skip-btn', 'accept-btn', 'abort-btn'];

  buttons.forEach((btnId) => {
    const button = window.document.getElementById(btnId);
    assert(button !== null, `Button ${btnId} should exist in DOM`);
  });
});

test('Property - Class Addition Idempotent', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const button = window.document.getElementById('skip-btn');

  flashButton(button);
  const firstState = button.classList.contains('btn-pressed');

  flashButton(button);
  const secondState = button.classList.contains('btn-pressed');

  assert.strictEqual(firstState, true);
  assert.strictEqual(secondState, true);
});

test('Property - Key Mapping Exhaustive', () => {
  const { window } = setupDOM();
  global.window = window;
  global.document = window.document;

  const allMappedKeys = [
    'ArrowLeft',
    'ArrowRight',
    ' ',
    'Enter',
    'Escape',
    'Delete',
    'Backspace',
  ];

  allMappedKeys.forEach((key) => {
    const freshWindow = setupDOM().window;
    global.window = freshWindow;
    global.document = freshWindow.document;

    let hasMapping = false;
    if (key === 'Delete' || key === 'Backspace') {
      hasMapping = flashButtonForKey(key, true) === true;
    } else {
      hasMapping = flashButtonForKey(key) !== false;
    }

    assert(hasMapping, `Key ${key} should have a mapping`);
  });
});
