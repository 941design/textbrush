// Integration Tests for UI Enhancements
// Tests end-to-end workflows across ThemeManager, ListManager, and ButtonFlash modules

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import * as ThemeManager from './theme-manager.js';
import * as ListManager from './list-manager.js';
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
          <button id="prev-btn">Prev</button>
          <button id="pause-btn">Pause</button>
          <button id="next-btn">Next</button>
          <button id="delete-btn">Delete</button>
          <button id="accept-btn">Done</button>
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
    it('should navigate through list and update position indicator', () => {
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3' }
        ],
        currentIndex: 1,
        bufferCount: 0
      };

      const displayedImages = [];
      const displayImage = (entry) => {
        displayedImages.push(entry.seed);
      };

      // Navigate to previous
      const prevResult = ListManager.navigateToPrev(state, displayImage);
      assert.strictEqual(prevResult, true, 'Navigation to previous succeeded');
      assert.strictEqual(state.currentIndex, 0, 'Index decremented to 0');
      assert.deepStrictEqual(displayedImages, [1], 'First image displayed');

      // Position indicator at start
      let indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[1/3]', 'Position indicator shows 1 of 3');

      // Try to go before start
      const prevAtStart = ListManager.navigateToPrev(state, displayImage);
      assert.strictEqual(prevAtStart, false, 'Cannot navigate before start');
      assert.strictEqual(state.currentIndex, 0, 'Index remains at 0');

      // Navigate forward
      const nextResult = ListManager.navigateToNext(state, displayImage, () => {});
      assert.strictEqual(nextResult, true, 'Navigation to next succeeded');
      assert.strictEqual(state.currentIndex, 1, 'Index incremented to 1');
      assert.deepStrictEqual(displayedImages, [1, 2], 'Second image displayed');

      // Position indicator in middle
      indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[2/3]', 'Position indicator shows 2 of 3');

      // Navigate to end
      ListManager.navigateToNext(state, displayImage, () => {});
      assert.strictEqual(state.currentIndex, 2, 'At end of list');

      // Position indicator at end
      indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[3/3]', 'Position indicator shows 3 of 3');
    });
  });

  describe('E2E: Image Deletion and Navigation', () => {
    it('should delete image and navigate appropriately', () => {
      // Note: Asset URLs from Tauri convertFileSrc don't need revoking like blob URLs
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'asset://localhost/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'asset://localhost/img2.png' },
          { image_data: 'img3', seed: 3, blobUrl: 'asset://localhost/img3.png' }
        ],
        currentIndex: 1
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
      const deleted = ListManager.deleteCurrentImage(state, displayImage, showEmptyState);

      // Verify deletion
      assert.strictEqual(deleted.seed, 2, 'Deleted entry returned');
      assert.strictEqual(state.imageList.length, 2, 'List length reduced to 2');
      assert.strictEqual(state.currentIndex, 1, 'Index adjusted to valid position');
      assert.deepStrictEqual(displayedImages, [3], 'Next image displayed after deletion');

      // Note: Asset URLs from Tauri don't need revoking - managed by Tauri runtime
      assert.strictEqual(showEmptyCalled.value, false, 'Empty state not shown (images remain)');

      // Verify remaining images
      assert.strictEqual(state.imageList[0].seed, 1, 'First image still present');
      assert.strictEqual(state.imageList[1].seed, 3, 'Third image now at index 1');
    });

    it('should show empty state when last image deleted', () => {
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1' }
        ],
        currentIndex: 0
      };

      let emptyShown = false;
      const showEmptyState = () => {
        emptyShown = true;
      };

      // Delete last image
      ListManager.deleteCurrentImage(state, () => {}, showEmptyState);

      // Verify empty state
      assert.strictEqual(state.imageList.length, 0, 'List is empty');
      assert.strictEqual(state.currentIndex, -1, 'Index set to -1');
      assert.strictEqual(emptyShown, true, 'Empty state shown');

      // Position indicator should be empty
      const indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '', 'Position indicator empty for no list');
    });
  });

  describe('E2E: Button Flash on Keyboard Shortcuts', () => {
    it('should flash corresponding button when keyboard shortcut pressed', () => {
      const skipBtn = document.getElementById('next-btn');
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

      // Test Space -> pause button
      const spaceResult = ButtonFlash.flashButtonForKey(' ');
      assert.strictEqual(spaceResult, true, 'Pause button flashed for Space');

      // Test unmapped key
      const unmappedResult = ButtonFlash.flashButtonForKey('x');
      assert.strictEqual(unmappedResult, false, 'Unmapped key returns false');
    });

    it('should flash delete button for Cmd/Ctrl+Delete', () => {
      const deleteBtn = document.getElementById('delete-btn');

      // Test Delete with modifier
      const result = ButtonFlash.flashButtonForKey('Delete', true);
      assert.strictEqual(result, true, 'Delete button flashed for Cmd/Ctrl+Delete');
      assert.ok(deleteBtn.classList.contains('btn-pressed'), 'Delete button has btn-pressed class');

      // Test Delete without modifier - should not flash
      deleteBtn.classList.remove('btn-pressed');
      const noModResult = ButtonFlash.flashButtonForKey('Delete', false);
      assert.strictEqual(noModResult, false, 'Delete without modifier returns false');
      assert.ok(!deleteBtn.classList.contains('btn-pressed'), 'Delete button not flashed without modifier');
    });
  });

  describe('E2E: Multi-Path Accept (getAllRetainedPaths)', () => {
    it('should collect all outputPaths from accepted list entries', () => {
      // getAllRetainedPaths returns outputPath (set when image is accepted), not preview path
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1', path: '/preview/img1.png', outputPath: '/output/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2', path: '/preview/img2.png', outputPath: '/output/img2.png' },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3', path: '/preview/img3.png', outputPath: '/output/img3.png' }
        ],
        currentIndex: 1
      };

      const paths = ListManager.getAllRetainedPaths(state);

      assert.strictEqual(paths.length, 3, 'Three paths collected');
      assert.deepStrictEqual(
        paths,
        ['/output/img1.png', '/output/img2.png', '/output/img3.png'],
        'Output paths collected in order'
      );
    });

    it('should filter out entries without outputPaths (not accepted)', () => {
      // Only images with outputPath (accepted) should be included
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'blob:1', path: '/preview/img1.png', outputPath: '/output/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'blob:2', path: '/preview/img2.png', outputPath: null },
          { image_data: 'img3', seed: 3, blobUrl: 'blob:3', path: '/preview/img3.png', outputPath: '/output/img3.png' }
        ],
        currentIndex: 1
      };

      const paths = ListManager.getAllRetainedPaths(state);

      assert.strictEqual(paths.length, 2, 'Only entries with outputPath collected');
      assert.deepStrictEqual(
        paths,
        ['/output/img1.png', '/output/img3.png'],
        'Null outputPaths filtered out'
      );
    });

    it('should return empty array for empty list', () => {
      const state = {
        imageList: [],
        currentIndex: -1
      };

      const paths = ListManager.getAllRetainedPaths(state);

      assert.strictEqual(paths.length, 0, 'Empty array for no list');
      assert.deepStrictEqual(paths, [], 'Returns empty array');
    });
  });

  describe('E2E: Complete Workflow Integration', () => {
    it('should support full user session: navigate, delete, theme toggle, and collect paths', () => {
      // Initialize theme
      localStorage.clear();
      const theme = ThemeManager.initTheme();
      assert.ok(theme, 'Theme initialized');

      // Setup list with accepted images (have outputPath)
      const state = {
        imageList: [
          { image_data: 'img1', seed: 1, blobUrl: 'asset://img1', path: '/preview/img1.png', outputPath: '/output/img1.png' },
          { image_data: 'img2', seed: 2, blobUrl: 'asset://img2', path: '/preview/img2.png', outputPath: '/output/img2.png' },
          { image_data: 'img3', seed: 3, blobUrl: 'asset://img3', path: '/preview/img3.png', outputPath: '/output/img3.png' }
        ],
        currentIndex: 0,
        bufferCount: 0
      };

      // Navigate forward
      ListManager.navigateToNext(state, () => {}, () => {});
      assert.strictEqual(state.currentIndex, 1, 'Navigated to index 1');

      // Flash button for visual feedback
      ButtonFlash.flashButtonForKey('ArrowRight');
      assert.ok(document.getElementById('next-btn').classList.contains('btn-pressed'), 'Button flashed');

      // Delete unwanted image
      ListManager.deleteCurrentImage(state, () => {}, () => {});
      assert.strictEqual(state.imageList.length, 2, 'Image deleted');

      // Toggle theme
      const newTheme = ThemeManager.toggleTheme();
      assert.notStrictEqual(newTheme, theme, 'Theme toggled');
      assert.strictEqual(localStorage.getItem('textbrush-theme'), newTheme, 'Theme persisted');

      // Collect retained paths (outputPath from accepted images)
      const paths = ListManager.getAllRetainedPaths(state);
      assert.strictEqual(paths.length, 2, 'Two paths retained after deletion');
      assert.deepStrictEqual(
        paths,
        ['/output/img1.png', '/output/img3.png'],
        'Correct output paths collected'
      );

      // Verify position indicator
      const indicator = ListManager.getPositionIndicator(state);
      assert.strictEqual(indicator, '[2/2]', 'Position indicator correct after deletion');
    });

    it('E2E Multi-Path Acceptance Workflow', () => {
      // Property: Complete workflow from multiple image generation through acceptance
      // validates that all retained paths are collected and multi-path exit is used.

      // Setup: Simulate generating 4 accepted images with outputPaths
      const state = {
        imageList: [
          { image_data: 'img1', seed: 101, blobUrl: 'asset://101', path: '/preview/101.png', outputPath: '/output/image-101.png' },
          { image_data: 'img2', seed: 102, blobUrl: 'asset://102', path: '/preview/102.png', outputPath: '/output/image-102.png' },
          { image_data: 'img3', seed: 103, blobUrl: 'asset://103', path: '/preview/103.png', outputPath: '/output/image-103.png' },
          { image_data: 'img4', seed: 104, blobUrl: 'asset://104', path: '/preview/104.png', outputPath: '/output/image-104.png' }
        ],
        currentIndex: 3,
        bufferCount: 0
      };

      // Step 1: Navigate backward to review images
      ListManager.navigateToPrev(state, () => {});
      assert.strictEqual(state.currentIndex, 2, 'Navigated to image 3');

      // Step 2: Delete unwanted image (index 2, seed 103)
      ListManager.deleteCurrentImage(state, () => {}, () => {});
      assert.strictEqual(state.imageList.length, 3, 'One image deleted');

      // Step 3: Navigate forward
      // After deletion at index 2, we're now viewing what was index 3 (seed 104), now at index 2
      assert.strictEqual(state.currentIndex, 2, 'Index adjusted after deletion');
      assert.strictEqual(state.imageList[2].seed, 104, 'Now viewing last image');

      // Step 4: Collect all retained paths (should exclude deleted image-103.png)
      const allPaths = ListManager.getAllRetainedPaths(state);
      assert.strictEqual(allPaths.length, 3, 'Three paths retained after deletion');
      assert.deepStrictEqual(
        allPaths,
        ['/output/image-101.png', '/output/image-102.png', '/output/image-104.png'],
        'Correct output paths collected, deleted image excluded'
      );

      // Step 5: Simulate acceptance workflow
      // In real workflow:
      // - User presses Enter
      // - Backend saves current image (already saved in this test)
      // - handleAccepted stores path in list entry
      // - handleAccepted calls getAllRetainedPaths()
      // - handleAccepted calls print_paths_and_exit(allPaths)

      // Verify multi-path exit would be called (paths.length > 1)
      assert.ok(allPaths.length > 1, 'Multi-path exit condition met');

      // Verify edge case: if all paths were deleted, would exit as abort
      state.imageList = [];
      const emptyPaths = ListManager.getAllRetainedPaths(state);
      assert.strictEqual(emptyPaths.length, 0, 'Empty paths when all deleted');
    });
  });
});
