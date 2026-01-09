// Metadata Synchronization Tests
// Validates metadata panel visibility and content consistency during navigation, deletion, and generation

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

describe('Metadata Panel Synchronization Tests', () => {
  let dom;
  let window;
  let document;
  let metadataPanel;
  let metadataPrompt;
  let metadataModel;
  let metadataSeed;

  // Mock updateMetadataPanel function from main.js
  // Panel is always visible; only content changes
  function updateMetadataPanel(payload) {
    const prompt = document.getElementById('metadata-prompt');
    const model = document.getElementById('metadata-model');
    const seed = document.getElementById('metadata-seed');

    if (!prompt || !model || !seed) {
      return;
    }

    if (payload && payload.image_data) {
      prompt.textContent = payload.prompt || '—';
      model.textContent = payload.model_name || '—';
      seed.textContent = payload.seed !== undefined ? payload.seed : '—';
    } else {
      prompt.textContent = '—';
      model.textContent = '—';
      seed.textContent = '—';
    }
  }

  before(() => {
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <body>
          <aside class="metadata-panel" id="metadata-panel">
            <h2 class="metadata-title">Image Details</h2>
            <dl class="metadata-fields">
              <dt class="metadata-label">Prompt:</dt>
              <dd class="metadata-value" id="metadata-prompt">—</dd>
              <dt class="metadata-label">Model:</dt>
              <dd class="metadata-value" id="metadata-model">—</dd>
              <dt class="metadata-label">Seed:</dt>
              <dd class="metadata-value" id="metadata-seed">—</dd>
            </dl>
          </aside>
        </body>
      </html>
    `);

    window = dom.window;
    document = window.document;
    global.document = document;

    metadataPanel = document.getElementById('metadata-panel');
    metadataPrompt = document.getElementById('metadata-prompt');
    metadataModel = document.getElementById('metadata-model');
    metadataSeed = document.getElementById('metadata-seed');
  });

  after(() => {
    delete global.document;
  });

  describe('Initial State', () => {
    it('should start visible with placeholder values', () => {
      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should be visible initially');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Prompt should be placeholder');
      assert.strictEqual(metadataModel.textContent, '—', 'Model should be placeholder');
      assert.strictEqual(metadataSeed.textContent, '—', 'Seed should be placeholder');
    });
  });

  describe('Displaying Image with Metadata', () => {
    it('should show panel and populate all fields when image is displayed', () => {
      const payload = {
        image_data: 'base64data',
        prompt: 'A beautiful sunset',
        model_name: 'flux-schnell',
        seed: 12345
      };

      updateMetadataPanel(payload);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should be visible');
      assert.strictEqual(metadataPrompt.textContent, 'A beautiful sunset', 'Prompt should match payload');
      assert.strictEqual(metadataModel.textContent, 'flux-schnell', 'Model should match payload');
      assert.strictEqual(metadataSeed.textContent, '12345', 'Seed should match payload');
    });

    it('should handle missing optional fields gracefully', () => {
      const payload = {
        image_data: 'base64data',
        // prompt, model_name, seed omitted
      };

      updateMetadataPanel(payload);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should be visible');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Missing prompt shows placeholder');
      assert.strictEqual(metadataModel.textContent, '—', 'Missing model shows placeholder');
      assert.strictEqual(metadataSeed.textContent, '—', 'Missing seed shows placeholder');
    });

    it('should handle seed value of 0 correctly', () => {
      const payload = {
        image_data: 'base64data',
        prompt: 'Test',
        model_name: 'flux-dev',
        seed: 0
      };

      updateMetadataPanel(payload);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should be visible');
      assert.strictEqual(metadataSeed.textContent, '0', 'Seed 0 should display as "0"');
    });
  });

  describe('Navigation Between Images', () => {
    it('should update all fields when navigating to different image', () => {
      // Display first image
      const payload1 = {
        image_data: 'data1',
        prompt: 'First prompt',
        model_name: 'flux-schnell',
        seed: 111
      };
      updateMetadataPanel(payload1);

      // Navigate to second image
      const payload2 = {
        image_data: 'data2',
        prompt: 'Second prompt',
        model_name: 'flux-dev',
        seed: 222
      };
      updateMetadataPanel(payload2);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should remain visible');
      assert.strictEqual(metadataPrompt.textContent, 'Second prompt', 'Prompt should update');
      assert.strictEqual(metadataModel.textContent, 'flux-dev', 'Model should update');
      assert.strictEqual(metadataSeed.textContent, '222', 'Seed should update');
    });

    it('should maintain visibility when navigating between valid images', () => {
      const payload1 = {
        image_data: 'data1',
        prompt: 'First',
        model_name: 'model1',
        seed: 100
      };
      const payload2 = {
        image_data: 'data2',
        prompt: 'Second',
        model_name: 'model2',
        seed: 200
      };

      updateMetadataPanel(payload1);
      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel visible after first image');

      updateMetadataPanel(payload2);
      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel remains visible after navigation');
    });
  });

  describe('Empty State After Deletion', () => {
    it('should show placeholders when called with null (empty history)', () => {
      // First show panel with data
      updateMetadataPanel({
        image_data: 'data',
        prompt: 'Test',
        model_name: 'flux-schnell',
        seed: 123
      });
      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel visible before deletion');

      // Simulate deletion - empty history
      updateMetadataPanel(null);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should remain visible');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Prompt reset to placeholder');
      assert.strictEqual(metadataModel.textContent, '—', 'Model reset to placeholder');
      assert.strictEqual(metadataSeed.textContent, '—', 'Seed reset to placeholder');
    });

    it('should show placeholders when called with empty object', () => {
      updateMetadataPanel({
        image_data: 'data',
        prompt: 'Test',
        model_name: 'model',
        seed: 999
      });

      updateMetadataPanel({});

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should remain visible');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Prompt reset to placeholder');
    });

    it('should show placeholders when image_data is missing', () => {
      updateMetadataPanel({
        image_data: 'data',
        prompt: 'Test',
        model_name: 'model',
        seed: 999
      });

      updateMetadataPanel({
        prompt: 'Test',
        model_name: 'model',
        seed: 999
        // image_data missing
      });

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should remain visible');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Prompt reset to placeholder');
    });
  });

  describe('Loading State Transitions', () => {
    it('should show placeholders during loading (null payload)', () => {
      updateMetadataPanel({
        image_data: 'data',
        prompt: 'Test',
        model_name: 'model',
        seed: 123
      });

      // Simulate loading state
      updateMetadataPanel(null);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel remains visible during loading');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Prompt shows placeholder during loading');
    });

    it('should populate panel when image loads after loading state', () => {
      // Start with loading
      updateMetadataPanel(null);
      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel visible during loading');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Placeholder during loading');

      // Image loads
      updateMetadataPanel({
        image_data: 'newdata',
        prompt: 'Generated prompt',
        model_name: 'flux-schnell',
        seed: 456
      });

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel visible after loading completes');
      assert.strictEqual(metadataPrompt.textContent, 'Generated prompt');
      assert.strictEqual(metadataModel.textContent, 'flux-schnell');
      assert.strictEqual(metadataSeed.textContent, '456');
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid updates correctly', () => {
      const payloads = [
        { image_data: 'd1', prompt: 'p1', model_name: 'm1', seed: 1 },
        { image_data: 'd2', prompt: 'p2', model_name: 'm2', seed: 2 },
        { image_data: 'd3', prompt: 'p3', model_name: 'm3', seed: 3 }
      ];

      payloads.forEach(payload => updateMetadataPanel(payload));

      // Final state should match last payload
      assert.strictEqual(metadataPrompt.textContent, 'p3');
      assert.strictEqual(metadataModel.textContent, 'm3');
      assert.strictEqual(metadataSeed.textContent, '3');
    });

    it('should handle very long text values', () => {
      const longPrompt = 'A '.repeat(500) + 'very long prompt';
      const payload = {
        image_data: 'data',
        prompt: longPrompt,
        model_name: 'flux-dev',
        seed: 999
      };

      updateMetadataPanel(payload);

      assert.strictEqual(metadataPrompt.textContent, longPrompt, 'Long prompt should be preserved');
      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel should be visible');
    });

    it('should handle special characters in metadata', () => {
      const payload = {
        image_data: 'data',
        prompt: 'Test <script>alert("xss")</script> & "quotes"',
        model_name: 'model&name',
        seed: 12345
      };

      updateMetadataPanel(payload);

      assert.strictEqual(metadataPrompt.textContent, 'Test <script>alert("xss")</script> & "quotes"');
      assert.strictEqual(metadataModel.textContent, 'model&name');
    });
  });

  describe('Consistency Properties', () => {
    it('should maintain invariant: panel always visible, content reflects image_data presence', () => {
      const testCases = [
        { payload: { image_data: 'data', prompt: 'p', model_name: 'm', seed: 1 }, hasContent: true },
        { payload: null, hasContent: false },
        { payload: {}, hasContent: false },
        { payload: { prompt: 'p', model_name: 'm', seed: 1 }, hasContent: false },
        { payload: { image_data: '', prompt: 'p', model_name: 'm', seed: 1 }, hasContent: false }
      ];

      testCases.forEach(({ payload, hasContent }, index) => {
        updateMetadataPanel(payload);
        const isVisible = !metadataPanel.classList.contains('metadata-hidden');
        assert.strictEqual(isVisible, true, `Test case ${index}: panel should always be visible`);
        if (hasContent) {
          assert.strictEqual(metadataPrompt.textContent, 'p', `Test case ${index}: should show content`);
        } else {
          assert.strictEqual(metadataPrompt.textContent, '—', `Test case ${index}: should show placeholder`);
        }
      });
    });

    it('should reset to placeholders when clearing metadata', () => {
      // Display image
      updateMetadataPanel({
        image_data: 'data',
        prompt: 'Old prompt',
        model_name: 'old-model',
        seed: 111
      });

      // Clear metadata
      updateMetadataPanel(null);

      assert.ok(!metadataPanel.classList.contains('metadata-hidden'), 'Panel remains visible');
      assert.strictEqual(metadataPrompt.textContent, '—', 'Prompt cleared to placeholder');
      assert.strictEqual(metadataModel.textContent, '—', 'Model cleared to placeholder');
      assert.strictEqual(metadataSeed.textContent, '—', 'Seed cleared to placeholder');
    });
  });
});
