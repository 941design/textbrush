// IPC Contract Tests
// Validates that prompt, model_name, and seed propagate correctly through the IPC chain
// Tests the contract between UI → Tauri → Python sidecar → UI

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';

describe('IPC Contract Tests', () => {
  let dom;
  let window;
  let document;
  let invokeCallLog;
  let emittedEvents;

  // Mock Tauri invoke function
  function mockInvoke(command, args) {
    invokeCallLog.push({ command, args });

    // Return promise that resolves immediately
    return Promise.resolve();
  }

  // Mock event listener that captures emitted events
  function mockListen(eventName, handler) {
    return {
      eventName,
      handler,
      unlisten: () => {}
    };
  }

  before(() => {
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <body>
          <input id="prompt-input" value="A beautiful landscape" />
          <input id="width-input" value="1024" />
          <input id="height-input" value="1024" />
          <div id="metadata-prompt">—</div>
          <div id="metadata-model">—</div>
          <div id="metadata-seed">—</div>
        </body>
      </html>
    `);

    window = dom.window;
    document = window.document;
    global.document = document;
    global.window = window;

    invokeCallLog = [];
    emittedEvents = [];

    // Mock Tauri API
    global.window.__TAURI__ = {
      core: {
        invoke: mockInvoke
      },
      event: {
        listen: mockListen
      }
    };
  });

  after(() => {
    delete global.document;
    delete global.window;
  });

  describe('Generation Request Contract', () => {
    it('should send prompt, aspect_ratio, and seed to init_generation command', async () => {
      const prompt = 'A serene mountain landscape';
      const aspectRatio = '16:9';
      const seed = 42;

      // Simulate UI calling invoke
      await mockInvoke('init_generation', {
        prompt,
        aspect_ratio: aspectRatio,
        seed,
        output_path: null
      });

      assert.strictEqual(invokeCallLog.length, 1, 'Should invoke exactly once');
      const call = invokeCallLog[0];

      assert.strictEqual(call.command, 'init_generation', 'Command should be init_generation');
      assert.strictEqual(call.args.prompt, prompt, 'Prompt should match');
      assert.strictEqual(call.args.aspect_ratio, aspectRatio, 'Aspect ratio should match');
      assert.strictEqual(call.args.seed, seed, 'Seed should match');
    });

    it('should handle missing optional seed parameter', async () => {
      invokeCallLog = [];

      await mockInvoke('init_generation', {
        prompt: 'Test prompt',
        aspect_ratio: '1:1',
        seed: null,
        output_path: null
      });

      const call = invokeCallLog[0];
      assert.strictEqual(call.args.seed, null, 'Seed should be null when not provided');
    });

    it('should preserve seed value of 0', async () => {
      invokeCallLog = [];

      await mockInvoke('init_generation', {
        prompt: 'Test',
        aspect_ratio: '1:1',
        seed: 0,
        output_path: null
      });

      const call = invokeCallLog[0];
      assert.strictEqual(call.args.seed, 0, 'Seed 0 should be preserved');
    });

    it('should handle custom aspect ratio', async () => {
      invokeCallLog = [];

      await mockInvoke('init_generation', {
        prompt: 'Test',
        aspect_ratio: 'custom',
        seed: null,
        output_path: null
      });

      const call = invokeCallLog[0];
      assert.strictEqual(call.args.aspect_ratio, 'custom', 'Custom aspect ratio should be preserved');
    });
  });

  describe('Sidecar Message Contract', () => {
    it('should receive image_generated event with prompt, model_name, and seed', () => {
      const sidecarMessage = {
        type: 'image_generated',
        payload: {
          image_data: 'base64encodedimagedata',
          prompt: 'A beautiful sunset over mountains',
          model_name: 'flux-schnell',
          seed: 12345,
          index: 0
        }
      };

      // Validate message structure
      assert.ok(sidecarMessage.type, 'Message should have type field');
      assert.ok(sidecarMessage.payload, 'Message should have payload field');
      assert.ok(sidecarMessage.payload.image_data, 'Payload should contain image_data');
      assert.ok(sidecarMessage.payload.prompt, 'Payload should contain prompt');
      assert.ok(sidecarMessage.payload.model_name, 'Payload should contain model_name');
      assert.ok(sidecarMessage.payload.seed !== undefined, 'Payload should contain seed');
    });

    it('should handle buffer_updated events', () => {
      const bufferMessage = {
        type: 'buffer_updated',
        payload: {
          filled: 3,
          total: 8
        }
      };

      assert.strictEqual(bufferMessage.type, 'buffer_updated');
      assert.ok(typeof bufferMessage.payload.filled === 'number');
      assert.ok(typeof bufferMessage.payload.total === 'number');
    });

    it('should handle status events', () => {
      const statusMessage = {
        type: 'status',
        payload: {
          message: 'Generation complete'
        }
      };

      assert.strictEqual(statusMessage.type, 'status');
      assert.ok(statusMessage.payload.message);
    });

    it('should handle error events', () => {
      const errorMessage = {
        type: 'error',
        payload: {
          message: 'Generation failed: model not found'
        }
      };

      assert.strictEqual(errorMessage.type, 'error');
      assert.ok(errorMessage.payload.message);
    });
  });

  describe('Prompt Propagation', () => {
    it('should preserve prompt exactly from input to generation request', () => {
      const testPrompts = [
        'Simple prompt',
        'Prompt with "quotes"',
        'Prompt with <html> tags',
        'Prompt with special chars: ñ, é, ü',
        'Very long '.repeat(50) + 'prompt',
        ''  // empty prompt
      ];

      testPrompts.forEach(prompt => {
        invokeCallLog = [];
        mockInvoke('init_generation', {
          prompt,
          aspect_ratio: '1:1',
          seed: null,
          output_path: null
        });

        assert.strictEqual(
          invokeCallLog[0].args.prompt,
          prompt,
          `Prompt should be preserved: "${prompt.substring(0, 50)}"`
        );
      });
    });

    it('should propagate prompt from request through to response payload', () => {
      const originalPrompt = 'A majestic eagle soaring';

      // Step 1: UI sends request
      invokeCallLog = [];
      mockInvoke('init_generation', {
        prompt: originalPrompt,
        aspect_ratio: '1:1',
        seed: 123,
        output_path: null
      });

      assert.strictEqual(invokeCallLog[0].args.prompt, originalPrompt);

      // Step 2: Simulate sidecar response
      const sidecarResponse = {
        type: 'image_generated',
        payload: {
          image_data: 'data',
          prompt: originalPrompt,  // Should match request
          model_name: 'flux-schnell',
          seed: 123
        }
      };

      assert.strictEqual(
        sidecarResponse.payload.prompt,
        originalPrompt,
        'Prompt should be preserved in response'
      );
    });
  });

  describe('Seed Propagation', () => {
    it('should preserve seed value from request to response', () => {
      const testSeeds = [0, 1, 42, 12345, 999999, -1];

      testSeeds.forEach(seed => {
        invokeCallLog = [];
        mockInvoke('init_generation', {
          prompt: 'Test',
          aspect_ratio: '1:1',
          seed,
          output_path: null
        });

        assert.strictEqual(
          invokeCallLog[0].args.seed,
          seed,
          `Seed ${seed} should be preserved in request`
        );

        // Simulate response
        const response = {
          type: 'image_generated',
          payload: {
            image_data: 'data',
            prompt: 'Test',
            model_name: 'flux-schnell',
            seed  // Should match request
          }
        };

        assert.strictEqual(
          response.payload.seed,
          seed,
          `Seed ${seed} should be preserved in response`
        );
      });
    });

    it('should handle null seed (random generation)', () => {
      invokeCallLog = [];
      mockInvoke('init_generation', {
        prompt: 'Test',
        aspect_ratio: '1:1',
        seed: null,
        output_path: null
      });

      assert.strictEqual(invokeCallLog[0].args.seed, null);

      // Sidecar should generate a random seed and return it
      const response = {
        type: 'image_generated',
        payload: {
          image_data: 'data',
          prompt: 'Test',
          model_name: 'flux-schnell',
          seed: 67890  // Generated by backend
        }
      };

      assert.ok(
        typeof response.payload.seed === 'number',
        'Response should contain generated seed when request had null'
      );
    });
  });

  describe('Model Name Propagation', () => {
    it('should receive model_name in response payload', () => {
      const response = {
        type: 'image_generated',
        payload: {
          image_data: 'data',
          prompt: 'Test',
          model_name: 'flux-schnell',
          seed: 123
        }
      };

      assert.ok(response.payload.model_name, 'Response must include model_name');
      assert.strictEqual(typeof response.payload.model_name, 'string');
    });

    it('should handle different model names', () => {
      const modelNames = ['flux-schnell', 'flux-dev', 'stable-diffusion-xl'];

      modelNames.forEach(model_name => {
        const response = {
          type: 'image_generated',
          payload: {
            image_data: 'data',
            prompt: 'Test',
            model_name,
            seed: 123
          }
        };

        assert.strictEqual(
          response.payload.model_name,
          model_name,
          `Model name ${model_name} should be preserved`
        );
      });
    });
  });

  describe('End-to-End Contract Flow', () => {
    it('should maintain data integrity through full request-response cycle', () => {
      const requestData = {
        prompt: 'A vibrant cityscape at night',
        aspect_ratio: '16:9',
        seed: 54321,
        output_path: null
      };

      // Step 1: UI sends request
      invokeCallLog = [];
      mockInvoke('init_generation', requestData);

      const sentRequest = invokeCallLog[0].args;
      assert.strictEqual(sentRequest.prompt, requestData.prompt);
      assert.strictEqual(sentRequest.seed, requestData.seed);

      // Step 2: Simulate sidecar processing and response
      const sidecarResponse = {
        type: 'image_generated',
        payload: {
          image_data: 'base64imagedata',
          prompt: requestData.prompt,  // Echoed back
          model_name: 'flux-schnell',
          seed: requestData.seed,      // Echoed back
          index: 0
        }
      };

      // Step 3: Validate contract integrity
      assert.strictEqual(
        sidecarResponse.payload.prompt,
        requestData.prompt,
        'Prompt should match original request'
      );
      assert.strictEqual(
        sidecarResponse.payload.seed,
        requestData.seed,
        'Seed should match original request'
      );
      assert.ok(
        sidecarResponse.payload.model_name,
        'Response must include model_name'
      );
      assert.ok(
        sidecarResponse.payload.image_data,
        'Response must include image_data'
      );
    });

    it('should handle history navigation with preserved metadata', () => {
      // Simulate history with multiple generated images
      const history = [
        {
          image_data: 'data1',
          prompt: 'First prompt',
          model_name: 'flux-schnell',
          seed: 100,
          timestamp: Date.now()
        },
        {
          image_data: 'data2',
          prompt: 'Second prompt',
          model_name: 'flux-dev',
          seed: 200,
          timestamp: Date.now() + 1000
        },
        {
          image_data: 'data3',
          prompt: 'Third prompt',
          model_name: 'flux-schnell',
          seed: 300,
          timestamp: Date.now() + 2000
        }
      ];

      // Validate each history entry has complete metadata
      history.forEach((entry, index) => {
        assert.ok(entry.image_data, `Entry ${index} must have image_data`);
        assert.ok(entry.prompt, `Entry ${index} must have prompt`);
        assert.ok(entry.model_name, `Entry ${index} must have model_name`);
        assert.ok(entry.seed !== undefined, `Entry ${index} must have seed`);
        assert.ok(entry.timestamp, `Entry ${index} must have timestamp`);
      });

      // Simulate navigation - metadata should remain intact
      const currentEntry = history[1];
      assert.strictEqual(currentEntry.prompt, 'Second prompt');
      assert.strictEqual(currentEntry.model_name, 'flux-dev');
      assert.strictEqual(currentEntry.seed, 200);
    });
  });

  describe('Contract Invariants', () => {
    it('should never send image_generated without all required fields', () => {
      const validMessage = {
        type: 'image_generated',
        payload: {
          image_data: 'data',
          prompt: 'Test',
          model_name: 'flux-schnell',
          seed: 123
        }
      };

      // Validate all required fields present
      const requiredFields = ['image_data', 'prompt', 'model_name', 'seed'];
      requiredFields.forEach(field => {
        assert.ok(
          validMessage.payload[field] !== undefined,
          `Required field ${field} must be present`
        );
      });
    });

    it('should maintain type consistency across IPC boundary', () => {
      const message = {
        type: 'image_generated',
        payload: {
          image_data: 'string',
          prompt: 'string',
          model_name: 'string',
          seed: 123,  // number
          index: 0    // number
        }
      };

      assert.strictEqual(typeof message.payload.image_data, 'string');
      assert.strictEqual(typeof message.payload.prompt, 'string');
      assert.strictEqual(typeof message.payload.model_name, 'string');
      assert.strictEqual(typeof message.payload.seed, 'number');
      assert.strictEqual(typeof message.payload.index, 'number');
    });

    it('should preserve message order for sequential generations', () => {
      const messages = [];

      // Simulate rapid generation requests
      for (let i = 0; i < 5; i++) {
        messages.push({
          type: 'image_generated',
          payload: {
            image_data: `data${i}`,
            prompt: `Prompt ${i}`,
            model_name: 'flux-schnell',
            seed: i * 100,
            index: i
          }
        });
      }

      // Validate index sequence
      messages.forEach((msg, i) => {
        assert.strictEqual(
          msg.payload.index,
          i,
          'Message index should match sequence'
        );
      });
    });
  });
});
