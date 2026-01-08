// Integration Tests for UI Enhancements
// Tests end-to-end workflows across ThemeManager, HistoryManager, and ButtonFlash modules

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import * as ThemeManager from './theme-manager.js';
import * as HistoryManager from './history-manager.js';
import * as ButtonFlash from './button-flash.js';

describe('UI Enhancements Integration Tests', () => {
  let dom;
  let window;
  let document;

  before(() => {
    // Setup minimal DOM environment for integration tests
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <head></head>
        <body>
          <button id="skip-btn">Skip</button>
          <button id="accept-btn">Accept</button>
          <button id="abort-btn">Abort</button>
          <div id="image-container"></div>
        </body>
      </html>
    `, {
      url: 'http://localhost',
      pretendToBeVisual: true,
    });

    window = dom.window;
    document = window.document;

    // Setup globals
    global.window = window;
    global.document = document;
    global.localStorage = {
      storage: {},
      getItem(key) { return this.storage[key] || null; },
      setItem(key, value) { this.storage[key] = value; },
      removeItem(key) { delete this.storage[key]; },
      clear() { this.storage = {}; }
    };
    global.URL = {
      revokeObjectURL: () => {},
      createObjectURL: () => 'blob:mock'
    };

    // Mock window.matchMedia for theme detection
    window.matchMedia = (query) => ({
      matches: query.includes('dark'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {}
    });
  });

  after(() => {
    delete global.window;
    delete global.document;
    delete global.localStorage;
    delete global.URL;
  });

  describe('E2E: Theme Toggle Workflow', () => {
    it('should toggle theme, update CSS, and persist to localStorage', () => {
      // Setup
      localStorage.clear();

      // Initialize theme (should default to system preference or dark)
      const initialTheme = ThemeManager.initTheme();
      assert.ok(initialTheme === 'light' || initialTheme === 'dark', 'Initial theme is valid');

      // Verify DOM attribute set
      const domTheme = document.documentElement.getAttribute('data-theme');
      assert.strictEqual(domTheme, initialTheme, 'DOM reflects initialized theme');

      // Toggle theme
      const newTheme = ThemeManager.toggleTheme();
      assert.notStrictEqual(newTheme, initialTheme, 'Theme changed after toggle');

      // Verify persistence
      const savedTheme = localStorage.getItem('textbrush-theme');
      assert.strictEqual(savedTheme, newTheme, 'Theme persisted to localStorage');

      // Verify DOM updated
      const updatedDomTheme = document.documentElement.getAttribute('data-theme');
      assert.strictEqual(updatedDomTheme, newTheme, 'DOM updated with new theme');

      // Toggle back
      const returnedTheme = ThemeManager.toggleTheme();
      assert.strictEqual(returnedTheme, initialTheme, 'Theme returns to original after second toggle');
    });

    it('should restore theme from localStorage on subsequent init', () => {
      // Setup - manually set localStorage
      localStorage.setItem('textbrush-theme', 'light');

      // Initialize
      const theme = ThemeManager.initTheme();

      // Verify restoration
      assert.strictEqual(theme, 'light', 'Theme restored from localStorage');
      assert.strictEqual(
        document.documentElement.getAttribute('data-theme'),
        'light',
        'DOM reflects restored theme'
      );
    });
  });

  describe('E2E: Bidirectional Navigation', () => {
    it('should navigate through history and update position indicator', () => {
      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3' }
        ],
        historyIndex: 1,
        bufferCount: 0
      };

      const displayedImages = [];
      const displayImage = (entry) => {
        displayedImages.push(entry.seed);
      };

      // Navigate to previous
      const prevResult = HistoryManager.navigateToPrevious(state, displayImage);
      assert.strictEqual(prevResult, true, 'Navigation to previous succeeded');
      assert.strictEqual(state.historyIndex, 0, 'Index decremented to 0');
      assert.deepStrictEqual(displayedImages, [1], 'First image displayed');

      // Position indicator at start
      let indicator = HistoryManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[1]/3]', 'Position indicator shows 1 of 3');

      // Try to go before start
      const prevAtStart = HistoryManager.navigateToPrevious(state, displayImage);
      assert.strictEqual(prevAtStart, false, 'Cannot navigate before start');
      assert.strictEqual(state.historyIndex, 0, 'Index remains at 0');

      // Navigate forward
      const nextResult = HistoryManager.navigateToNext(state, displayImage, () => {});
      assert.strictEqual(nextResult, true, 'Navigation to next succeeded');
      assert.strictEqual(state.historyIndex, 1, 'Index incremented to 1');
      assert.deepStrictEqual(displayedImages, [1, 2], 'Second image displayed');

      // Position indicator in middle
      indicator = HistoryManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[2]/3]', 'Position indicator shows 2 of 3');

      // Navigate to end
      HistoryManager.navigateToNext(state, displayImage, () => {});
      assert.strictEqual(state.historyIndex, 2, 'At end of history');

      // Position indicator at end
      indicator = HistoryManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[3]/3]', 'Position indicator shows 3 of 3');
    });
  });

  describe('E2E: Image Deletion with Blob URL Cleanup', () => {
    it('should delete image, revoke blob URL, and navigate appropriately', () => {
      const revokedUrls = [];
      global.URL.revokeObjectURL = (url) => {
        revokedUrls.push(url);
      };

      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3' }
        ],
        historyIndex: 1
      };

      const displayedImages = [];
      const displayImage = (entry) => {
        displayedImages.push(entry.seed);
      };

      const showEmptyCalled = { value: false };
      const showEmptyState = () => {
        showEmptyCalled.value = true;
      };

      // Delete middle image
      const deleted = HistoryManager.deleteCurrentImage(state, displayImage, showEmptyState);

      // Verify deletion
      assert.strictEqual(deleted.seed, 2, 'Deleted entry returned');
      assert.strictEqual(state.imageHistory.length, 2, 'History length reduced to 2');
      assert.strictEqual(state.historyIndex, 1, 'Index adjusted to valid position');
      assert.deepStrictEqual(displayedImages, [3], 'Next image displayed after deletion');

      // Verify blob URL revoked
      assert.deepStrictEqual(revokedUrls, ['blob:2'], 'Blob URL was revoked');
      assert.strictEqual(showEmptyCalled.value, false, 'Empty state not shown (images remain)');

      // Verify remaining images
      assert.strictEqual(state.imageHistory[0].seed, 1, 'First image still present');
      assert.strictEqual(state.imageHistory[1].seed, 3, 'Third image now at index 1');
    });

    it('should show empty state when last image deleted', () => {
      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1' }
        ],
        historyIndex: 0
      };

      let emptyShown = false;
      const showEmptyState = () => {
        emptyShown = true;
      };

      // Delete last image
      HistoryManager.deleteCurrentImage(state, () => {}, showEmptyState);

      // Verify empty state
      assert.strictEqual(state.imageHistory.length, 0, 'History is empty');
      assert.strictEqual(state.historyIndex, -1, 'Index set to -1');
      assert.strictEqual(emptyShown, true, 'Empty state shown');

      // Position indicator should be empty
      const indicator = HistoryManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '', 'Position indicator empty for no history');
    });
  });

  describe('E2E: Button Flash on Keyboard Shortcuts', () => {
    it('should flash corresponding button when keyboard shortcut pressed', () => {
      const skipBtn = document.getElementById('skip-btn');
      const acceptBtn = document.getElementById('accept-btn');
      const abortBtn = document.getElementById('abort-btn');

      // Test ArrowRight -> skip button
      const skipResult = ButtonFlash.flashButtonForKey('ArrowRight');
      assert.strictEqual(skipResult, true, 'Skip button flashed for ArrowRight');
      assert.ok(skipBtn.classList.contains('btn-pressed'), 'Skip button has btn-pressed class');

      // Test Enter -> accept button
      const acceptResult = ButtonFlash.flashButtonForKey('Enter');
      assert.strictEqual(acceptResult, true, 'Accept button flashed for Enter');
      assert.ok(acceptBtn.classList.contains('btn-pressed'), 'Accept button has btn-pressed class');

      // Test Escape -> abort button
      const abortResult = ButtonFlash.flashButtonForKey('Escape');
      assert.strictEqual(abortResult, true, 'Abort button flashed for Escape');
      assert.ok(abortBtn.classList.contains('btn-pressed'), 'Abort button has btn-pressed class');

      // Test Space -> skip button
      const spaceResult = ButtonFlash.flashButtonForKey(' ');
      assert.strictEqual(spaceResult, true, 'Skip button flashed for Space');

      // Test unmapped key
      const unmappedResult = ButtonFlash.flashButtonForKey('x');
      assert.strictEqual(unmappedResult, false, 'Unmapped key returns false');
    });

    it('should flash image container for Cmd/Ctrl+Delete', () => {
      const imageContainer = document.getElementById('image-container');

      // Test Delete with modifier
      const result = ButtonFlash.flashButtonForKey('Delete', true);
      assert.strictEqual(result, true, 'Image container flashed for Cmd/Ctrl+Delete');
      assert.ok(imageContainer.classList.contains('btn-pressed'), 'Image container has btn-pressed class');

      // Test Delete without modifier - should not flash
      imageContainer.classList.remove('btn-pressed');
      const noModResult = ButtonFlash.flashButtonForKey('Delete', false);
      assert.strictEqual(noModResult, false, 'Delete without modifier returns false');
      assert.ok(!imageContainer.classList.contains('btn-pressed'), 'Image container not flashed without modifier');
    });
  });

  describe('E2E: Multi-Path Accept (getAllRetainedPaths)', () => {
    it('should collect all paths from history entries', () => {
      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1', path: '/tmp/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2', path: '/tmp/img2.png' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3', path: '/tmp/img3.png' }
        ],
        historyIndex: 1
      };

      const paths = HistoryManager.getAllRetainedPaths(state);

      assert.strictEqual(paths.length, 3, 'Three paths collected');
      assert.deepStrictEqual(
        paths,
        ['/tmp/img1.png', '/tmp/img2.png', '/tmp/img3.png'],
        'Paths collected in order'
      );
    });

    it('should filter out entries without paths', () => {
      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1', path: '/tmp/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2', path: null },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3', path: '/tmp/img3.png' }
        ],
        historyIndex: 1
      };

      const paths = HistoryManager.getAllRetainedPaths(state);

      assert.strictEqual(paths.length, 2, 'Only entries with paths collected');
      assert.deepStrictEqual(
        paths,
        ['/tmp/img1.png', '/tmp/img3.png'],
        'Null paths filtered out'
      );
    });

    it('should return empty array for empty history', () => {
      const state = {
        imageHistory: [],
        historyIndex: -1
      };

      const paths = HistoryManager.getAllRetainedPaths(state);

      assert.strictEqual(paths.length, 0, 'Empty array for no history');
      assert.deepStrictEqual(paths, [], 'Returns empty array');
    });
  });

  describe('E2E: Complete Workflow Integration', () => {
    it('should support full user session: navigate, delete, theme toggle, and collect paths', () => {
      // Initialize theme
      localStorage.clear();
      const theme = ThemeManager.initTheme();
      assert.ok(theme, 'Theme initialized');

      // Setup history
      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1', path: '/tmp/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2', path: '/tmp/img2.png' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3', path: '/tmp/img3.png' }
        ],
        historyIndex: 0,
        bufferCount: 0
      };

      const revokedUrls = [];
      global.URL.revokeObjectURL = (url) => {
        revokedUrls.push(url);
      };

      // Navigate forward
      HistoryManager.navigateToNext(state, () => {}, () => {});
      assert.strictEqual(state.historyIndex, 1, 'Navigated to index 1');

      // Flash button for visual feedback
      ButtonFlash.flashButtonForKey('ArrowRight');
      assert.ok(document.getElementById('skip-btn').classList.contains('btn-pressed'), 'Button flashed');

      // Delete unwanted image
      HistoryManager.deleteCurrentImage(state, () => {}, () => {});
      assert.strictEqual(state.imageHistory.length, 2, 'Image deleted');
      assert.deepStrictEqual(revokedUrls, ['blob:2'], 'Blob revoked');

      // Toggle theme
      const newTheme = ThemeManager.toggleTheme();
      assert.notStrictEqual(newTheme, theme, 'Theme toggled');
      assert.strictEqual(localStorage.getItem('textbrush-theme'), newTheme, 'Theme persisted');

      // Collect retained paths
      const paths = HistoryManager.getAllRetainedPaths(state);
      assert.strictEqual(paths.length, 2, 'Two paths retained after deletion');
      assert.deepStrictEqual(
        paths,
        ['/tmp/img1.png', '/tmp/img3.png'],
        'Correct paths collected'
      );

      // Verify position indicator
      const indicator = HistoryManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[2]/2]', 'Position indicator correct after deletion');
    });

    it('E2E Multi-Path Acceptance Workflow', () => {
      // Property: Complete workflow from multiple image generation through acceptance
      // validates that all retained paths are collected and multi-path exit is used.

      // Setup: Simulate generating 4 images with paths
      const state = {
        imageHistory: [
          { image_data: 'img1', seed: 101, blobUrl: 'blob:101', path: '/output/image-101.png' },
          { image_data: 'img2', seed: 102, blobUrl: 'blob:102', path: '/output/image-102.png' },
          { image_data: 'img3', seed: 103, blobUrl: 'blob:103', path: '/output/image-103.png' },
          { image_data: 'img4', seed: 104, blobUrl: 'blob:104', path: '/output/image-104.png' }
        ],
        historyIndex: 3,
        bufferCount: 0
      };

      const revokedUrls = [];
      global.URL.revokeObjectURL = (url) => {
        revokedUrls.push(url);
      };

      // Step 1: Navigate backward to review images
      HistoryManager.navigateToPrevious(state, () => {});
      assert.strictEqual(state.historyIndex, 2, 'Navigated to image 3');

      // Step 2: Delete unwanted image (index 2, seed 103)
      HistoryManager.deleteCurrentImage(state, () => {}, () => {});
      assert.strictEqual(state.imageHistory.length, 3, 'One image deleted');
      assert.deepStrictEqual(revokedUrls, ['blob:103'], 'Deleted image blob revoked');

      // Step 3: Navigate forward
      // After deletion at index 2, we're now viewing what was index 3 (seed 104), now at index 2
      assert.strictEqual(state.historyIndex, 2, 'Index adjusted after deletion');
      assert.strictEqual(state.imageHistory[2].seed, 104, 'Now viewing last image');

      // Step 4: Collect all retained paths (should exclude deleted image-103.png)
      const allPaths = HistoryManager.getAllRetainedPaths(state);
      assert.strictEqual(allPaths.length, 3, 'Three paths retained after deletion');
      assert.deepStrictEqual(
        allPaths,
        ['/output/image-101.png', '/output/image-102.png', '/output/image-104.png'],
        'Correct paths collected, deleted image excluded'
      );

      // Step 5: Simulate acceptance workflow
      // In real workflow:
      // - User presses Enter
      // - Backend saves current image (already saved in this test)
      // - handleAccepted stores path in history entry
      // - handleAccepted calls getAllRetainedPaths()
      // - handleAccepted calls print_paths_and_exit(allPaths)

      // Verify multi-path exit would be called (paths.length > 1)
      assert.ok(allPaths.length > 1, 'Multi-path exit condition met');

      // Verify edge case: if all paths were deleted, would exit as abort
      state.imageHistory = [];
      const emptyPaths = HistoryManager.getAllRetainedPaths(state);
      assert.strictEqual(emptyPaths.length, 0, 'Empty paths when all deleted');
    });
  });
});
