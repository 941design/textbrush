// Property-based tests for HistoryManager module
// Uses simple assertion testing with property generation

import * as HistoryManager from './history-manager.js';

// Simple assertion helpers
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`Assertion failed: ${message}\n  Expected: ${expected}\n  Actual: ${actual}`);
  }
}

function assertArrayEqual(actual, expected, message) {
  if (actual.length !== expected.length) {
    throw new Error(
      `Assertion failed: ${message}\n  Expected length: ${expected.length}\n  Actual length: ${actual.length}`
    );
  }
  for (let i = 0; i < actual.length; i++) {
    if (actual[i] !== expected[i]) {
      throw new Error(
        `Assertion failed: ${message}\n  At index ${i}: expected ${expected[i]}, got ${actual[i]}`
      );
    }
  }
}

// Mock URL.revokeObjectURL
global.URL = {
  revokeObjectURL: (url) => {
    // Mock implementation
  },
};

// ============================================================================
// PROPERTY-BASED TESTS
// ============================================================================

// Helper to generate test data
function generateImageEntry(seed = Math.random()) {
  return {
    image_data: `data-${seed}`,
    seed: Math.floor(seed * 1000),
    blobUrl: `blob:${seed}`,
    path: undefined,
  };
}

function createState(historyLength = 0, currentIndex = -1) {
  const imageHistory = Array.from({ length: historyLength }, (_, i) =>
    generateImageEntry(i)
  );
  return {
    imageHistory,
    historyIndex: currentIndex,
    bufferCount: 0,
  };
}

// ============================================================================
// navigateToPrevious Tests
// ============================================================================

function test_navigateToPrevious_atBeginningReturnsFalse() {
  const state = createState(3, 0);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  const result = HistoryManager.navigateToPrevious(state, mockDisplay);

  assert(!result, 'navigateToPrevious should return false at beginning');
  assertEqual(state.historyIndex, 0, 'index should not change');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
}

function test_navigateToPrevious_emptyHistoryReturnsFalse() {
  const state = createState(0, -1);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  const result = HistoryManager.navigateToPrevious(state, mockDisplay);

  assert(!result, 'navigateToPrevious should return false on empty history');
  assertEqual(state.historyIndex, -1, 'index should remain -1');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
}

function test_navigateToPrevious_validPositionDecrements() {
  const state = createState(5, 2);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  const result = HistoryManager.navigateToPrevious(state, mockDisplay);

  assert(result, 'navigateToPrevious should return true');
  assertEqual(state.historyIndex, 1, 'index should decrement by 1');
  assertEqual(callLog.length, 1, 'displayImage should be called once');
  assertEqual(callLog[0].image_data, 'data-1', 'should display image at index 1');
}

function test_navigateToPrevious_idempotentAtBoundary() {
  const state = createState(3, 0);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  HistoryManager.navigateToPrevious(state, mockDisplay);
  HistoryManager.navigateToPrevious(state, mockDisplay);
  HistoryManager.navigateToPrevious(state, mockDisplay);

  assertEqual(state.historyIndex, 0, 'should remain at beginning');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
}

function test_navigateToPrevious_property_indexDecrementsFromEnd() {
  // Property: navigating from end (index = length - 1) should decrement by 1
  for (let len = 2; len <= 10; len++) {
    const state = createState(len, len - 1);
    const mockDisplay = () => {};

    HistoryManager.navigateToPrevious(state, mockDisplay);

    assertEqual(
      state.historyIndex,
      len - 2,
      `for history length ${len}, index should be ${len - 2}`
    );
  }
}

function test_navigateToPrevious_property_neverGoesNegative() {
  // Property: index should never become negative
  for (let i = 0; i < 20; i++) {
    const state = createState(5, Math.max(0, Math.floor(Math.random() * 5)));
    const mockDisplay = () => {};

    // Try navigating backward multiple times
    for (let j = 0; j < 10; j++) {
      HistoryManager.navigateToPrevious(state, mockDisplay);
    }

    assert(state.historyIndex >= 0, 'index should never become negative');
  }
}

// ============================================================================
// navigateToNext Tests
// ============================================================================

function test_navigateToNext_navigatesForwardInHistory() {
  const state = createState(5, 1);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);
  const mockRequest = () => {};

  const result = HistoryManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true');
  assertEqual(state.historyIndex, 2, 'index should increment to 2');
  assertEqual(callLog.length, 1, 'displayImage should be called once');
}

function test_navigateToNext_atEndWithBuffer() {
  const state = createState(3, 2);
  state.bufferCount = 1;
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);
  const requestLog = [];
  const mockRequest = () => requestLog.push(true);

  const result = HistoryManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true with buffer');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
  assertEqual(requestLog.length, 1, 'requestNextImage should be called');
  assertEqual(state.historyIndex, 2, 'index should not change (buffer request)');
}

function test_navigateToNext_atEndAlwaysRequests() {
  // Even when buffer is empty, should request next (backend decides buffer vs generate)
  const state = createState(3, 2);
  state.bufferCount = 0;
  const mockDisplay = () => {};
  let requestCalled = false;
  const mockRequest = () => { requestCalled = true; };

  const result = HistoryManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true at end (always requests)');
  assert(requestCalled, 'requestNextImage should be called even with empty buffer');
}

function test_navigateToNext_emptyHistory() {
  // With empty history, should request new image (e.g., after deleting all images)
  const state = createState(0, -1);
  state.bufferCount = 0;
  const mockDisplay = () => {};
  let requestCalled = false;
  const mockRequest = () => { requestCalled = true; };

  const result = HistoryManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true on empty history (requests new image)');
  assert(requestCalled, 'requestNextImage should be called on empty history');
}

function test_navigateToNext_property_bufferPriority() {
  // Property: at end of history, buffer request takes priority
  for (let i = 0; i < 20; i++) {
    const state = createState(3, 2);
    state.bufferCount = 1;
    const requestLog = [];
    const mockDisplay = () => {};
    const mockRequest = () => requestLog.push(true);

    HistoryManager.navigateToNext(state, mockDisplay, mockRequest);

    assertEqual(
      requestLog.length,
      1,
      'buffer request should be called when at end with buffer'
    );
  }
}

function test_navigateToNext_property_neverExceedsLength() {
  // Property: index should never exceed history length - 1
  for (let len = 1; len <= 10; len++) {
    for (let idx = 0; idx < len; idx++) {
      const state = createState(len, idx);
      const mockDisplay = () => {};
      const mockRequest = () => {};

      HistoryManager.navigateToNext(state, mockDisplay, mockRequest);

      assert(
        state.historyIndex < state.imageHistory.length,
        `index ${state.historyIndex} should be less than length ${state.imageHistory.length}`
      );
    }
  }
}

// ============================================================================
// deleteCurrentImage Tests
// ============================================================================

function test_deleteCurrentImage_invalidIndex() {
  const state = createState(3, -1);
  const mockDisplay = () => {};
  const mockEmpty = () => {};

  const deleted = HistoryManager.deleteCurrentImage(state, mockDisplay, mockEmpty);

  assert(deleted === null, 'should return null for invalid index');
}

function test_deleteCurrentImage_indexOutOfBounds() {
  const state = createState(3, 5);
  const mockDisplay = () => {};
  const mockEmpty = () => {};

  const deleted = HistoryManager.deleteCurrentImage(state, mockDisplay, mockEmpty);

  assert(deleted === null, 'should return null for out-of-bounds index');
}

function test_deleteCurrentImage_lastImage() {
  const state = createState(1, 0);
  const emptyLog = [];
  const mockDisplay = () => {};
  const mockEmpty = () => emptyLog.push(true);

  const deleted = HistoryManager.deleteCurrentImage(state, mockDisplay, mockEmpty);

  assert(deleted !== null, 'should return deleted entry');
  assertEqual(state.imageHistory.length, 0, 'history should be empty');
  assertEqual(state.historyIndex, -1, 'index should be -1');
  assertEqual(emptyLog.length, 1, 'showEmptyState should be called');
}

function test_deleteCurrentImage_fromMiddle() {
  const state = createState(5, 2);
  const displayLog = [];
  const mockDisplay = (entry) => displayLog.push(entry);
  const mockEmpty = () => {};

  const deleted = HistoryManager.deleteCurrentImage(state, mockDisplay, mockEmpty);

  assert(deleted !== null, 'should return deleted entry');
  assertEqual(state.imageHistory.length, 4, 'should have 4 images left');
  assertEqual(state.historyIndex, 2, 'index should stay at 2');
  assertEqual(displayLog.length, 1, 'displayImage should be called');
  assertEqual(displayLog[0].image_data, 'data-3', 'should display what was next (now at index 2)');
}

function test_deleteCurrentImage_fromEnd() {
  const state = createState(5, 4);
  const displayLog = [];
  const mockDisplay = (entry) => displayLog.push(entry);
  const mockEmpty = () => {};

  const deleted = HistoryManager.deleteCurrentImage(state, mockDisplay, mockEmpty);

  assert(deleted !== null, 'should return deleted entry');
  assertEqual(state.imageHistory.length, 4, 'should have 4 images left');
  assertEqual(state.historyIndex, 3, 'index should adjust to new end');
  assertEqual(displayLog.length, 1, 'displayImage should be called');
  assertEqual(displayLog[0].image_data, 'data-3', 'should display new end');
}

function test_deleteCurrentImage_revokesBlobUrl() {
  const revokeLog = [];
  global.URL.revokeObjectURL = (url) => revokeLog.push(url);

  const state = createState(3, 1);
  state.imageHistory[1].blobUrl = 'blob:test-123';

  HistoryManager.deleteCurrentImage(state, () => {}, () => {});

  assertEqual(revokeLog.length, 1, 'revokeObjectURL should be called');
  assertEqual(revokeLog[0], 'blob:test-123', 'should revoke correct URL');
}

function test_deleteCurrentImage_property_doesNotRevokeNull() {
  // Property: should not crash when blobUrl is null
  for (let i = 0; i < 10; i++) {
    const state = createState(3, 1);
    state.imageHistory[1].blobUrl = null;

    try {
      HistoryManager.deleteCurrentImage(state, () => {}, () => {});
    } catch (error) {
      throw new Error('should handle null blobUrl gracefully: ' + error.message);
    }
  }
}

function test_deleteCurrentImage_property_indexAlwaysValid() {
  // Property: after deletion, index should always be valid
  for (let len = 1; len <= 10; len++) {
    for (let idx = 0; idx < len; idx++) {
      const state = createState(len, idx);
      HistoryManager.deleteCurrentImage(state, () => {}, () => {});

      if (state.imageHistory.length > 0) {
        assert(
          state.historyIndex >= 0 && state.historyIndex < state.imageHistory.length,
          `index ${state.historyIndex} invalid for length ${state.imageHistory.length}`
        );
      } else {
        assertEqual(state.historyIndex, -1, 'index should be -1 when empty');
      }
    }
  }
}

// ============================================================================
// getAllRetainedPaths Tests
// ============================================================================

function test_getAllRetainedPaths_emptyHistory() {
  const state = createState(0, -1);

  const paths = HistoryManager.getAllRetainedPaths(state);

  assertArrayEqual(paths, [], 'should return empty array');
}

function test_getAllRetainedPaths_noPathsSet() {
  const state = createState(3, 0);

  const paths = HistoryManager.getAllRetainedPaths(state);

  assertArrayEqual(paths, [], 'should return empty array when no paths set');
}

function test_getAllRetainedPaths_allPathsSet() {
  const state = createState(3, 0);
  state.imageHistory[0].path = '/path/to/image-0.png';
  state.imageHistory[1].path = '/path/to/image-1.png';
  state.imageHistory[2].path = '/path/to/image-2.png';

  const paths = HistoryManager.getAllRetainedPaths(state);

  assertArrayEqual(
    paths,
    ['/path/to/image-0.png', '/path/to/image-1.png', '/path/to/image-2.png'],
    'should return all paths in order'
  );
}

function test_getAllRetainedPaths_filtersMissing() {
  const state = createState(4, 0);
  state.imageHistory[0].path = '/path/0.png';
  state.imageHistory[1].path = null;
  state.imageHistory[2].path = undefined;
  state.imageHistory[3].path = '/path/3.png';

  const paths = HistoryManager.getAllRetainedPaths(state);

  assertArrayEqual(
    paths,
    ['/path/0.png', '/path/3.png'],
    'should filter out null/undefined paths'
  );
}

function test_getAllRetainedPaths_property_readOnly() {
  // Property: should not modify state
  for (let i = 0; i < 10; i++) {
    const state = createState(3, 0);
    const originalLength = state.imageHistory.length;
    const originalIndex = state.historyIndex;

    HistoryManager.getAllRetainedPaths(state);

    assertEqual(
      state.imageHistory.length,
      originalLength,
      'should not modify history length'
    );
    assertEqual(state.historyIndex, originalIndex, 'should not modify index');
  }
}

// ============================================================================
// getPositionIndicator Tests
// ============================================================================

function test_getPositionIndicator_emptyHistory() {
  const state = createState(0, -1);

  const indicator = HistoryManager.getPositionIndicator(state);

  assertEqual(indicator, '', 'should return empty string for empty history');
}

function test_getPositionIndicator_singleImage() {
  const state = createState(1, 0);

  const indicator = HistoryManager.getPositionIndicator(state);

  assertEqual(indicator, '[1]/1]', 'should return [1]/1]');
}

function test_getPositionIndicator_middleOfHistory() {
  const state = createState(5, 2);

  const indicator = HistoryManager.getPositionIndicator(state);

  assertEqual(indicator, '[3]/5]', 'should return [3]/5]');
}

function test_getPositionIndicator_endOfHistory() {
  const state = createState(5, 4);

  const indicator = HistoryManager.getPositionIndicator(state);

  assertEqual(indicator, '[5]/5]', 'should return [5]/5]');
}

function test_getPositionIndicator_property_alwaysValid() {
  // Property: indicator should match invariant [current]/[total] format
  for (let len = 1; len <= 20; len++) {
    for (let idx = 0; idx < len; idx++) {
      const state = createState(len, idx);
      const indicator = HistoryManager.getPositionIndicator(state);

      const match = indicator.match(/\[(\d+)\]\/(\d+)\]/);
      assert(match, `indicator format invalid: ${indicator}`);

      const current = parseInt(match[1], 10);
      const total = parseInt(match[2], 10);

      assertEqual(current, idx + 1, `current should be ${idx + 1}`);
      assertEqual(total, len, `total should be ${len}`);
    }
  }
}

// ============================================================================
// Test Runner
// ============================================================================

const tests = [
  // navigateToPrevious
  test_navigateToPrevious_atBeginningReturnsFalse,
  test_navigateToPrevious_emptyHistoryReturnsFalse,
  test_navigateToPrevious_validPositionDecrements,
  test_navigateToPrevious_idempotentAtBoundary,
  test_navigateToPrevious_property_indexDecrementsFromEnd,
  test_navigateToPrevious_property_neverGoesNegative,

  // navigateToNext
  test_navigateToNext_navigatesForwardInHistory,
  test_navigateToNext_atEndWithBuffer,
  test_navigateToNext_atEndAlwaysRequests,
  test_navigateToNext_emptyHistory,
  test_navigateToNext_property_bufferPriority,
  test_navigateToNext_property_neverExceedsLength,

  // deleteCurrentImage
  test_deleteCurrentImage_invalidIndex,
  test_deleteCurrentImage_indexOutOfBounds,
  test_deleteCurrentImage_lastImage,
  test_deleteCurrentImage_fromMiddle,
  test_deleteCurrentImage_fromEnd,
  test_deleteCurrentImage_revokesBlobUrl,
  test_deleteCurrentImage_property_doesNotRevokeNull,
  test_deleteCurrentImage_property_indexAlwaysValid,

  // getAllRetainedPaths
  test_getAllRetainedPaths_emptyHistory,
  test_getAllRetainedPaths_noPathsSet,
  test_getAllRetainedPaths_allPathsSet,
  test_getAllRetainedPaths_filtersMissing,
  test_getAllRetainedPaths_property_readOnly,

  // getPositionIndicator
  test_getPositionIndicator_emptyHistory,
  test_getPositionIndicator_singleImage,
  test_getPositionIndicator_middleOfHistory,
  test_getPositionIndicator_endOfHistory,
  test_getPositionIndicator_property_alwaysValid,
];

function runTests() {
  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      test();
      passed++;
      console.log(`✓ ${test.name}`);
    } catch (error) {
      failed++;
      console.error(`✗ ${test.name}`);
      console.error(`  ${error.message}`);
    }
  }

  console.log(`\n${passed}/${tests.length} tests passed`);

  if (failed > 0) {
    process.exit(1);
  }
}

// Export for testing frameworks
export { runTests };

// Run tests if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runTests();
}
