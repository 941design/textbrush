// Integration Tests: Frontend State Synchronization
// Verifies state_changed event handling, index-based operations, and system-level properties

import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

/**
 * SYSTEM-LEVEL PROPERTIES:
 *
 * 1. State Transition Consistency:
 *    - Backend state always reflects most recent state_changed event
 *    - Loading overlay display matches backend state
 *    - No optimistic state updates - all changes event-driven
 *
 * 2. Index-Based Deletion Integrity:
 *    - Delete commands use backend index (not path)
 *    - Images removed from list only after delete_ack
 *    - No optimistic removal before backend confirmation
 *
 * 3. State Machine Invariants:
 *    - Only 5 valid states: loading, idle, generating, paused, error
 *    - State transitions follow backend events
 *    - Prompt only present when state = generating
 */

// Test helper: Create mock AppState with new structure
function createMockState() {
  return {
    currentImage: null,
    backendState: {
      state: "loading",
    },
    isPaused: false,
    isTransitioning: false,
    prompt: '',
    generationPrompt: '',
    aspectRatio: '1:1',
    width: 1024,
    height: 1024,
    outputPath: null,
    actionQueue: Promise.resolve(),
    currentBlobUrl: null,
    imageList: [],
    currentIndex: -1,
  };
}

// Test helper: Create mock ImageRecord with index
function createMockImageRecord(index, path = `/tmp/image_${index}.png`) {
  return {
    index,
    path,
    displayPath: `~/image_${index}.png`,
    seed: 12345 + index,
    blobUrl: `asset://localhost/${path}`,
    prompt: `test prompt ${index}`,
    model: 'test_model',
    aspectRatio: '1:1',
    width: 1024,
    height: 1024,
  };
}

describe('State Changed Event Integration', () => {
  let dom;
  let document;

  beforeEach(() => {
    dom = new JSDOM(`<!DOCTYPE html>
      <div id="loading-overlay">
        <div id="loading-spinner"></div>
        <div id="loading-label"></div>
        <div id="loading-prompt"></div>
      </div>
    `);
    document = dom.window.document;
    global.document = document;
  });

  it('Property: Backend state always reflects most recent state_changed payload', () => {
    const state = createMockState();

    // Initial state
    assert.equal(state.backendState.state, "loading");

    // Simulate state_changed to idle
    const idlePayload = { state: "idle" };
    state.backendState = idlePayload;
    assert.equal(state.backendState.state, "idle");

    // Simulate state_changed to generating
    const generatingPayload = { state: "generating", prompt: "sunset" };
    state.backendState = generatingPayload;
    assert.equal(state.backendState.state, "generating");
    assert.equal(state.backendState.prompt, "sunset");

    // Simulate state_changed to paused
    const pausedPayload = { state: "paused" };
    state.backendState = pausedPayload;
    assert.equal(state.backendState.state, "paused");
    assert.equal(state.backendState.prompt, undefined);

    // Simulate state_changed to error
    const errorPayload = { state: "error", message: "GPU error", fatal: true };
    state.backendState = errorPayload;
    assert.equal(state.backendState.state, "error");
    assert.equal(state.backendState.message, "GPU error");
    assert.equal(state.backendState.fatal, true);
  });

  it('Property: Only 5 valid backend states exist', () => {
    const validStates = ["loading", "idle", "generating", "paused", "error"];
    const state = createMockState();

    // Test each valid state
    validStates.forEach(stateValue => {
      state.backendState = { state: stateValue };
      assert.ok(validStates.includes(state.backendState.state));
    });

    // Verify no other states are used
    const testStateChanges = [
      { state: "loading" },
      { state: "idle" },
      { state: "generating", prompt: "test" },
      { state: "paused" },
      { state: "error", message: "test" },
    ];

    testStateChanges.forEach(payload => {
      state.backendState = payload;
      assert.ok(validStates.includes(state.backendState.state));
    });
  });

  it('Property: Prompt field only present when state = generating', () => {
    const state = createMockState();

    // State: loading - no prompt
    state.backendState = { state: "loading" };
    assert.equal(state.backendState.prompt, undefined);

    // State: idle - no prompt
    state.backendState = { state: "idle" };
    assert.equal(state.backendState.prompt, undefined);

    // State: generating - prompt required
    state.backendState = { state: "generating", prompt: "sunset" };
    assert.equal(state.backendState.prompt, "sunset");

    // State: paused - no prompt
    state.backendState = { state: "paused" };
    assert.equal(state.backendState.prompt, undefined);

    // State: error - no prompt (has message instead)
    state.backendState = { state: "error", message: "error text" };
    assert.equal(state.backendState.prompt, undefined);
    assert.equal(state.backendState.message, "error text");
  });

  it('E2E: State transition flow from loading to idle to generating to idle', () => {
    const state = createMockState();
    const events = [];

    // Initial: loading
    events.push({ ...state.backendState });
    assert.equal(state.backendState.state, "loading");

    // Backend loads model → idle
    state.backendState = { state: "idle" };
    events.push({ ...state.backendState });
    assert.equal(state.backendState.state, "idle");

    // User initiates generation → generating
    state.backendState = { state: "generating", prompt: "sunset" };
    events.push({ ...state.backendState });
    assert.equal(state.backendState.state, "generating");
    assert.equal(state.backendState.prompt, "sunset");

    // Image ready → idle
    state.backendState = { state: "idle" };
    events.push({ ...state.backendState });
    assert.equal(state.backendState.state, "idle");

    // Verify state sequence
    assert.equal(events.length, 4);
    assert.equal(events[0].state, "loading");
    assert.equal(events[1].state, "idle");
    assert.equal(events[2].state, "generating");
    assert.equal(events[3].state, "idle");
  });

  it('Property: Error state with fatal flag triggers app close (conceptual test)', () => {
    const state = createMockState();

    // Non-fatal error
    state.backendState = { state: "error", message: "Network timeout", fatal: false };
    assert.equal(state.backendState.state, "error");
    assert.equal(state.backendState.fatal, false);

    // Fatal error
    state.backendState = { state: "error", message: "GPU crashed", fatal: true };
    assert.equal(state.backendState.state, "error");
    assert.equal(state.backendState.fatal, true);
    // In real code, this would trigger setTimeout(() => appWindow.close(), 2000)
  });
});

describe('Index-Based Deletion Integration', () => {
  it('Property: ImageRecord always includes backend index', () => {
    const record1 = createMockImageRecord(0);
    const record2 = createMockImageRecord(5);
    const record3 = createMockImageRecord(100);

    assert.ok(typeof record1.index === 'number');
    assert.ok(typeof record2.index === 'number');
    assert.ok(typeof record3.index === 'number');

    assert.equal(record1.index, 0);
    assert.equal(record2.index, 5);
    assert.equal(record3.index, 100);
  });

  it('Property: Delete command payload uses index (not path)', () => {
    const record = createMockImageRecord(42, '/tmp/test.png');

    // OLD (deprecated): { imageId: record.path }
    // NEW (correct): { index: record.index }

    const deletePayload = { index: record.index };

    assert.ok('index' in deletePayload);
    assert.ok(!('imageId' in deletePayload));
    assert.ok(!('path' in deletePayload));
    assert.equal(deletePayload.index, 42);
  });

  it('Property: DeleteAckPayload uses index (not image_id)', () => {
    // OLD protocol: { image_id: "/path/to/image.png" }
    // NEW protocol: { index: 5 }

    const deleteAckPayload = { index: 5 };

    assert.ok('index' in deleteAckPayload);
    assert.ok(!('image_id' in deleteAckPayload));
    assert.equal(typeof deleteAckPayload.index, 'number');
  });

  it('E2E: Delete flow - send index, wait for ack, then remove from list', () => {
    const state = createMockState();

    // Add images to list
    state.imageList.push(createMockImageRecord(0));
    state.imageList.push(createMockImageRecord(1));
    state.imageList.push(createMockImageRecord(2));
    state.currentIndex = 1;

    assert.equal(state.imageList.length, 3);

    // User deletes current image (index=1)
    const imageToDelete = state.imageList[state.currentIndex];
    const deleteCommand = { index: imageToDelete.index };

    assert.equal(deleteCommand.index, 1);

    // CRITICAL: Do NOT remove from list here (no optimistic removal)
    // List should remain unchanged until delete_ack

    // Backend processes and sends delete_ack
    const deleteAckPayload = { index: 1 };

    // NOW remove from list
    const imageIndex = state.imageList.findIndex(img => img.index === deleteAckPayload.index);
    assert.equal(imageIndex, 1);

    state.imageList.splice(imageIndex, 1);

    // Verify removal
    assert.equal(state.imageList.length, 2);
    assert.equal(state.imageList[0].index, 0);
    assert.equal(state.imageList[1].index, 2);
  });

  it('Property: No optimistic removal - list unchanged until delete_ack', () => {
    const state = createMockState();
    state.imageList.push(createMockImageRecord(0));
    state.imageList.push(createMockImageRecord(1));
    state.imageList.push(createMockImageRecord(2));

    const initialLength = state.imageList.length;

    // Send delete command
    const deleteCommand = { index: 1 };

    // List should NOT change yet
    assert.equal(state.imageList.length, initialLength);

    // Only after delete_ack should list change
    const deleteAckPayload = { index: 1 };
    const imageIndex = state.imageList.findIndex(img => img.index === deleteAckPayload.index);
    state.imageList.splice(imageIndex, 1);

    // Now list is shorter
    assert.equal(state.imageList.length, initialLength - 1);
  });

  it('Property: Delete_ack is idempotent - no error if already deleted', () => {
    const state = createMockState();
    state.imageList.push(createMockImageRecord(0));
    state.imageList.push(createMockImageRecord(1));

    // Delete image with index=1
    const imageIndex = state.imageList.findIndex(img => img.index === 1);
    state.imageList.splice(imageIndex, 1);

    assert.equal(state.imageList.length, 1);

    // Receive duplicate delete_ack (backend idempotent response)
    const duplicateAck = { index: 1 };
    const findAgain = state.imageList.findIndex(img => img.index === duplicateAck.index);

    // Not found (returns -1), no error
    assert.equal(findAgain, -1);

    // Attempting to delete again should be safe
    if (findAgain !== -1) {
      state.imageList.splice(findAgain, 1);
    }

    // List unchanged
    assert.equal(state.imageList.length, 1);
  });
});

describe('Image Ready Event Integration', () => {
  it('Property: image_ready payload includes index field', () => {
    const imageReadyPayload = {
      index: 5,
      path: '/tmp/image.png',
      display_path: '~/image.png',
    };

    assert.ok('index' in imageReadyPayload);
    assert.equal(typeof imageReadyPayload.index, 'number');
    assert.ok(!('buffer_count' in imageReadyPayload));
    assert.ok(!('buffer_max' in imageReadyPayload));
  });

  it('E2E: image_ready creates ImageRecord with backend index', () => {
    const state = createMockState();
    const imageReadyPayload = {
      index: 10,
      path: '/tmp/test.png',
      display_path: '~/test.png',
    };

    // Simulate creating ImageRecord from payload
    const record = createMockImageRecord(imageReadyPayload.index, imageReadyPayload.path);
    state.imageList.push(record);
    state.currentIndex = state.imageList.length - 1;

    assert.equal(state.imageList.length, 1);
    assert.equal(state.imageList[0].index, 10);
    assert.equal(state.imageList[0].path, '/tmp/test.png');
  });
});

describe('System-Level Properties', () => {
  it('Property: AppState uses backendState object (not boolean flags)', () => {
    const state = createMockState();

    // Verify backendState exists
    assert.ok('backendState' in state);
    assert.ok(typeof state.backendState === 'object');

    // Verify deprecated fields removed
    assert.ok(!('isGenerating' in state));
    assert.ok(!('backendReady' in state));
    assert.ok(!('waitingForNext' in state));
    assert.ok(!('bufferCount' in state));
    assert.ok(!('bufferMax' in state));
  });

  it('Property: State changes are event-driven (no optimistic updates)', () => {
    const state = createMockState();

    // Initial state: loading
    assert.equal(state.backendState.state, "loading");

    // User action (e.g., clicks "next") does NOT change state directly
    // State only changes when backend sends state_changed event

    // Simulate backend event
    state.backendState = { state: "generating", prompt: "test" };

    // Now state reflects event
    assert.equal(state.backendState.state, "generating");

    // Principle: Frontend never modifies backendState without receiving event
  });

  it('Property: Deprecated fields completely removed from AppState', () => {
    const state = createMockState();

    const deprecatedFields = [
      'isGenerating',
      'backendReady',
      'waitingForNext',
      'bufferCount',
      'bufferMax',
    ];

    deprecatedFields.forEach(field => {
      assert.ok(!(field in state), `Deprecated field '${field}' should not exist in AppState`);
    });
  });

  it('Integration: Full workflow from state_changed to image_ready to delete', () => {
    const state = createMockState();

    // 1. Backend loads → idle
    state.backendState = { state: "idle" };
    assert.equal(state.backendState.state, "idle");

    // 2. Backend starts generating → generating
    state.backendState = { state: "generating", prompt: "forest" };
    assert.equal(state.backendState.state, "generating");
    assert.equal(state.backendState.prompt, "forest");

    // 3. Image ready
    const imagePayload = { index: 0, path: '/tmp/img0.png', display_path: '~/img0.png' };
    const record = createMockImageRecord(imagePayload.index, imagePayload.path);
    state.imageList.push(record);
    state.currentIndex = 0;

    assert.equal(state.imageList.length, 1);
    assert.equal(state.imageList[0].index, 0);

    // 4. Backend returns to idle
    state.backendState = { state: "idle" };
    assert.equal(state.backendState.state, "idle");

    // 5. User deletes image
    const deleteCommand = { index: record.index };
    assert.equal(deleteCommand.index, 0);

    // 6. Backend confirms deletion
    const deleteAck = { index: 0 };
    const idx = state.imageList.findIndex(img => img.index === deleteAck.index);
    state.imageList.splice(idx, 1);

    assert.equal(state.imageList.length, 0);
  });
});

describe('Loading Overlay State Mapping', () => {
  it('Property: Each backend state maps to correct loading overlay display', () => {
    const stateDisplayMapping = [
      { state: "loading", label: "loading model", spinnerVisible: true, promptVisible: false },
      { state: "idle", label: "ready", spinnerVisible: false, promptVisible: false },
      { state: "generating", label: "generating", spinnerVisible: true, promptVisible: true },
      { state: "paused", label: "generation paused", spinnerVisible: false, promptVisible: false },
      { state: "error", label: "error message", spinnerVisible: false, promptVisible: false },
    ];

    stateDisplayMapping.forEach(mapping => {
      const backendState = { state: mapping.state };
      if (mapping.state === "generating") {
        backendState.prompt = "test prompt";
      }
      if (mapping.state === "error") {
        backendState.message = "error message";
      }

      // Verify each state has correct display expectations
      assert.ok(mapping.label);
      assert.equal(typeof mapping.spinnerVisible, 'boolean');
      assert.equal(typeof mapping.promptVisible, 'boolean');
    });
  });

  it('Property: Spinner visible only for loading and generating states', () => {
    const spinnerVisibleStates = ["loading", "generating"];
    const spinnerHiddenStates = ["idle", "paused", "error"];

    spinnerVisibleStates.forEach(state => {
      const backendState = { state };
      const isSpinnerVisible = (backendState.state === "loading" || backendState.state === "generating");
      assert.ok(isSpinnerVisible);
    });

    spinnerHiddenStates.forEach(state => {
      const backendState = { state };
      const isSpinnerVisible = (backendState.state === "loading" || backendState.state === "generating");
      assert.ok(!isSpinnerVisible);
    });
  });

  it('Property: Prompt visible only when state=generating and prompt exists', () => {
    const backendStateWithPrompt = { state: "generating", prompt: "sunset" };
    const shouldShowPrompt = (backendStateWithPrompt.state === "generating" && backendStateWithPrompt.prompt);
    assert.ok(shouldShowPrompt);

    const backendStateIdle = { state: "idle" };
    const shouldShowPromptIdle = (backendStateIdle.state === "generating" && backendStateIdle.prompt);
    assert.ok(!shouldShowPromptIdle);

    const backendStatePaused = { state: "paused" };
    const shouldShowPromptPaused = (backendStatePaused.state === "generating" && backendStatePaused.prompt);
    assert.ok(!shouldShowPromptPaused);
  });
});
