// Property-based tests for ListManager module
// Uses simple assertion testing with property generation

import * as ListManager from './list-manager.js';

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

// Helper to generate test data (ImageRecord structure)
function generateImageEntry(seed = Math.random()) {
  return {
    path: `/preview/img-${seed}.png`,
    seed: Math.floor(seed * 1000),
    blobUrl: null,  // No longer using blob URLs
    prompt: `test prompt ${seed}`,
    model: 'test-model',
    aspectRatio: '1:1',
    width: 1024,
    height: 1024,
    outputPath: undefined,  // Set when accepted
  };
}

function createState(listLength = 0, currentIndex = -1) {
  const imageList = Array.from({ length: listLength }, (_, i) =>
    generateImageEntry(i)
  );
  return {
    imageList,
    currentIndex: currentIndex,
    bufferCount: 0,
  };
}

// ============================================================================
// navigateToPrev Tests
// ============================================================================

function test_navigateToPrev_atBeginningReturnsFalse() {
  const state = createState(3, 0);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  const result = ListManager.navigateToPrev(state, mockDisplay);

  assert(!result, 'navigateToPrev should return false at beginning');
  assertEqual(state.currentIndex, 0, 'index should not change');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
}

function test_navigateToPrev_emptyListReturnsFalse() {
  const state = createState(0, -1);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  const result = ListManager.navigateToPrev(state, mockDisplay);

  assert(!result, 'navigateToPrev should return false on empty list');
  assertEqual(state.currentIndex, -1, 'index should remain -1');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
}

function test_navigateToPrev_validPositionDecrements() {
  const state = createState(5, 2);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  const result = ListManager.navigateToPrev(state, mockDisplay);

  assert(result, 'navigateToPrev should return true');
  assertEqual(state.currentIndex, 1, 'index should decrement by 1');
  assertEqual(callLog.length, 1, 'displayImage should be called once');
  assertEqual(callLog[0].path, '/preview/img-1.png', 'should display image at index 1');
}

function test_navigateToPrev_idempotentAtBoundary() {
  const state = createState(3, 0);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);

  ListManager.navigateToPrev(state, mockDisplay);
  ListManager.navigateToPrev(state, mockDisplay);
  ListManager.navigateToPrev(state, mockDisplay);

  assertEqual(state.currentIndex, 0, 'should remain at beginning');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
}

function test_navigateToPrev_property_indexDecrementsFromEnd() {
  // Property: navigating from end (index = length - 1) should decrement by 1
  for (let len = 2; len <= 10; len++) {
    const state = createState(len, len - 1);
    const mockDisplay = () => {};

    ListManager.navigateToPrev(state, mockDisplay);

    assertEqual(
      state.currentIndex,
      len - 2,
      `for list length ${len}, index should be ${len - 2}`
    );
  }
}

function test_navigateToPrev_property_neverGoesNegative() {
  // Property: index should never become negative
  for (let i = 0; i < 20; i++) {
    const state = createState(5, Math.max(0, Math.floor(Math.random() * 5)));
    const mockDisplay = () => {};

    // Try navigating backward multiple times
    for (let j = 0; j < 10; j++) {
      ListManager.navigateToPrev(state, mockDisplay);
    }

    assert(state.currentIndex >= 0, 'index should never become negative');
  }
}

// ============================================================================
// navigateToNext Tests
// ============================================================================

function test_navigateToNext_navigatesForwardInList() {
  const state = createState(5, 1);
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);
  const mockRequest = () => {};

  const result = ListManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true');
  assertEqual(state.currentIndex, 2, 'index should increment to 2');
  assertEqual(callLog.length, 1, 'displayImage should be called once');
}

function test_navigateToNext_atEndWithBuffer() {
  const state = createState(3, 2);
  state.bufferCount = 1;
  const callLog = [];
  const mockDisplay = (entry) => callLog.push(entry);
  const requestLog = [];
  const mockRequest = () => requestLog.push(true);

  const result = ListManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true with buffer');
  assertEqual(callLog.length, 0, 'displayImage should not be called');
  assertEqual(requestLog.length, 1, 'requestNextImage should be called');
  assertEqual(state.currentIndex, 2, 'index should not change (buffer request)');
}

function test_navigateToNext_atEndAlwaysRequests() {
  // Even when buffer is empty, should request next (backend decides buffer vs generate)
  const state = createState(3, 2);
  state.bufferCount = 0;
  const mockDisplay = () => {};
  let requestCalled = false;
  const mockRequest = () => { requestCalled = true; };

  const result = ListManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true at end (always requests)');
  assert(requestCalled, 'requestNextImage should be called even with empty buffer');
}

function test_navigateToNext_emptyList() {
  // With empty list, should request new image (e.g., after deleting all images)
  const state = createState(0, -1);
  state.bufferCount = 0;
  const mockDisplay = () => {};
  let requestCalled = false;
  const mockRequest = () => { requestCalled = true; };

  const result = ListManager.navigateToNext(state, mockDisplay, mockRequest);

  assert(result, 'navigateToNext should return true on empty list (requests new image)');
  assert(requestCalled, 'requestNextImage should be called on empty list');
}

function test_navigateToNext_property_bufferPriority() {
  // Property: at end of list, buffer request takes priority
  for (let i = 0; i < 20; i++) {
    const state = createState(3, 2);
    state.bufferCount = 1;
    const requestLog = [];
    const mockDisplay = () => {};
    const mockRequest = () => requestLog.push(true);

    ListManager.navigateToNext(state, mockDisplay, mockRequest);

    assertEqual(
      requestLog.length,
      1,
      'buffer request should be called when at end with buffer'
    );
  }
}

function test_navigateToNext_property_neverExceedsLength() {
  // Property: index should never exceed list length - 1
  for (let len = 1; len <= 10; len++) {
    for (let idx = 0; idx < len; idx++) {
      const state = createState(len, idx);
      const mockDisplay = () => {};
      const mockRequest = () => {};

      ListManager.navigateToNext(state, mockDisplay, mockRequest);

      assert(
        state.currentIndex < state.imageList.length,
        `index ${state.currentIndex} should be less than length ${state.imageList.length}`
      );
    }
  }
}

// ============================================================================
// getPositionIndicator Tests
// ============================================================================

function test_getPositionIndicator_emptyList() {
  const state = createState(0, -1);

  const indicator = ListManager.getPositionIndicator(state);

  assertEqual(indicator, '', 'should return empty string for empty list');
}

function test_getPositionIndicator_singleImage() {
  const state = createState(1, 0);

  const indicator = ListManager.getPositionIndicator(state);

  assertEqual(indicator, '[1/1]', 'should return [1/1]');
}

function test_getPositionIndicator_middleOfList() {
  const state = createState(5, 2);

  const indicator = ListManager.getPositionIndicator(state);

  assertEqual(indicator, '[3/5]', 'should return [3/5]');
}

function test_getPositionIndicator_endOfList() {
  const state = createState(5, 4);

  const indicator = ListManager.getPositionIndicator(state);

  assertEqual(indicator, '[5/5]', 'should return [5/5]');
}

function test_getPositionIndicator_property_alwaysValid() {
  // Property: indicator should match invariant [current]/[total] format
  for (let len = 1; len <= 20; len++) {
    for (let idx = 0; idx < len; idx++) {
      const state = createState(len, idx);
      const indicator = ListManager.getPositionIndicator(state);

      const match = indicator.match(/\[(\d+)\/(\d+)\]/);
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
  // navigateToPrev
  test_navigateToPrev_atBeginningReturnsFalse,
  test_navigateToPrev_emptyListReturnsFalse,
  test_navigateToPrev_validPositionDecrements,
  test_navigateToPrev_idempotentAtBoundary,
  test_navigateToPrev_property_indexDecrementsFromEnd,
  test_navigateToPrev_property_neverGoesNegative,

  // navigateToNext
  test_navigateToNext_navigatesForwardInList,
  test_navigateToNext_atEndWithBuffer,
  test_navigateToNext_atEndAlwaysRequests,
  test_navigateToNext_emptyList,
  test_navigateToNext_property_bufferPriority,
  test_navigateToNext_property_neverExceedsLength,

  // getPositionIndicator
  test_getPositionIndicator_emptyList,
  test_getPositionIndicator_singleImage,
  test_getPositionIndicator_middleOfList,
  test_getPositionIndicator_endOfList,
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
