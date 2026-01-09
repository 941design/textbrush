// UI Configuration Controls - Frontend Implementation
//
// Responsibilities:
// 1. Replace read-only prompt display with editable text input
// 2. Add radio button group for aspect ratio selection
// 3. Add width/height input fields for custom dimensions
// 4. Handle blur/Enter events to trigger configuration update
// 5. Manage local state synchronization

import { invoke } from '@tauri-apps/api/core';
import type { AppState, Elements } from './types';

interface Dimensions {
  width: number;
  height: number;
}

// Default dimensions for each aspect ratio
const ASPECT_RATIO_DIMENSIONS: Record<string, Dimensions> = {
  '1:1': { width: 1024, height: 1024 },
  '16:9': { width: 1344, height: 768 },
  '9:16': { width: 768, height: 1344 },
};

interface ConfigValues {
  prompt: string;
  aspectRatio: string;
  width: number;
  height: number;
}

/**
 * Initialize configuration controls in the UI.
 */
export function initConfigControls(
  initialPrompt: string,
  initialAspectRatio: string,
  state: AppState,
  elements: Elements
): void {
  state.aspectRatio = initialAspectRatio || '1:1';

  // Initialize dimensions from aspect ratio
  const initialDims = ASPECT_RATIO_DIMENSIONS[state.aspectRatio] || { width: 1024, height: 1024 };
  state.width = initialDims.width;
  state.height = initialDims.height;

  // Get existing HTML elements (they're already in the DOM from index.html)
  const promptInput = document.getElementById('prompt-input') as HTMLInputElement | null;
  const widthInput = document.getElementById('width-input') as HTMLInputElement | null;
  const heightInput = document.getElementById('height-input') as HTMLInputElement | null;
  const aspectRatioRadios = document.querySelectorAll<HTMLInputElement>('input[name="aspect-ratio"]');

  // Set initial values
  if (promptInput) {
    promptInput.value = initialPrompt;
    elements.promptInput = promptInput;
  }

  if (widthInput) {
    widthInput.value = String(state.width);
    elements.widthInput = widthInput;
  }

  if (heightInput) {
    heightInput.value = String(state.height);
    elements.heightInput = heightInput;
  }

  // Convert NodeList to array and set initial checked state
  const radios = Array.from(aspectRatioRadios);
  radios.forEach(radio => {
    radio.checked = radio.value === state.aspectRatio;
  });
  elements.aspectRatioRadios = aspectRatioRadios;

  // Prompt input event listeners
  if (promptInput) {
    promptInput.addEventListener('blur', () => {
      const config = getCurrentConfig(elements);
      void handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
    });

    promptInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        promptInput.blur();
      }
    });
  }

  // Flag to track whether dimension changes are aspect-ratio-initiated
  let dimensionChangeFromAspectRatio = false;

  // Aspect ratio radio event listeners
  radios.forEach(radio => {
    radio.addEventListener('change', () => {
      // Update dimension fields when aspect ratio changes (except for custom)
      const ratio = radio.value;
      const dims = ASPECT_RATIO_DIMENSIONS[ratio];
      if (dims && widthInput && heightInput) {
        dimensionChangeFromAspectRatio = true;
        widthInput.value = String(dims.width);
        heightInput.value = String(dims.height);
        dimensionChangeFromAspectRatio = false;
      }
      const config = getCurrentConfig(elements);
      void handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
    });
  });

  // Helper to select custom aspect ratio
  const selectCustomAspectRatio = () => {
    const customRadio = radios.find(r => r.value === 'custom');
    if (customRadio && !customRadio.checked) {
      customRadio.checked = true;
    }
  };

  // Dimension input event listeners
  const handleDimensionChange = () => {
    // If dimension change was triggered by user (not aspect ratio change), select custom
    if (!dimensionChangeFromAspectRatio) {
      selectCustomAspectRatio();
    }
    const config = getCurrentConfig(elements);
    void handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
  };

  if (widthInput) {
    widthInput.addEventListener('blur', handleDimensionChange);
    widthInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        widthInput.blur();
      }
    });
  }

  if (heightInput) {
    heightInput.addEventListener('blur', handleDimensionChange);
    heightInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        heightInput.blur();
      }
    });
  }
}

/**
 * Handle configuration update (prompt, aspect ratio, or dimensions changed).
 */
export async function handleConfigUpdate(
  promptValue: string,
  aspectRatioValue: string,
  widthValue: number,
  heightValue: number,
  state: AppState
): Promise<void> {
  const trimmedPrompt = promptValue.trim();

  if (trimmedPrompt === '') {
    const promptInput = document.getElementById('prompt-input');
    if (promptInput) {
      showValidationError('Prompt cannot be empty', promptInput);
    }
    return;
  }

  // Validate dimensions
  const width = widthValue;
  const height = heightValue;

  if (isNaN(width) || width < 64 || width > 2048) {
    const widthInput = document.getElementById('width-input');
    if (widthInput) {
      showValidationError('Width must be 64-2048', widthInput);
    }
    return;
  }

  if (isNaN(height) || height < 64 || height > 2048) {
    const heightInput = document.getElementById('height-input');
    if (heightInput) {
      showValidationError('Height must be 64-2048', heightInput);
    }
    return;
  }

  // Check if config actually changed
  if (
    trimmedPrompt === state.prompt &&
    aspectRatioValue === state.aspectRatio &&
    width === state.width &&
    height === state.height
  ) {
    return;
  }

  const previousPrompt = state.prompt;
  const previousAspectRatio = state.aspectRatio;
  const previousWidth = state.width;
  const previousHeight = state.height;

  state.prompt = trimmedPrompt;
  state.aspectRatio = aspectRatioValue;
  state.width = width;
  state.height = height;

  try {
    await invoke('update_generation_config', {
      prompt: trimmedPrompt,
      aspectRatio: aspectRatioValue,
      width: width,
      height: height,
    });
    console.log('Configuration updated successfully');

    // Update loading prompt caption
    const loadingPrompt = document.getElementById('loading-prompt');
    if (loadingPrompt) {
      loadingPrompt.textContent = trimmedPrompt;
    }
  } catch (error) {
    console.error('Configuration update failed:', error);

    state.prompt = previousPrompt;
    state.aspectRatio = previousAspectRatio;
    state.width = previousWidth;
    state.height = previousHeight;

    const promptInput = document.getElementById('prompt-input');
    if (promptInput) {
      showValidationError(`Update failed: ${String(error)}`, promptInput);
    }
  }
}

/**
 * Show validation error message to user.
 */
export function showValidationError(message: string, inputElement: Element): void {
  const existingErrors = document.querySelectorAll('.validation-error');
  existingErrors.forEach(error => error.remove());

  const errorElement = document.createElement('div');
  errorElement.className = 'validation-error';
  errorElement.textContent = message;
  errorElement.setAttribute('role', 'alert');
  errorElement.setAttribute('aria-live', 'polite');

  if (inputElement.parentNode) {
    inputElement.parentNode.insertBefore(errorElement, inputElement.nextSibling);
  }

  setTimeout(() => {
    errorElement.remove();
  }, 3000);
}

/**
 * Get current configuration from UI inputs.
 */
export function getCurrentConfig(elements: Elements): ConfigValues {
  const promptValue = elements.promptInput ? elements.promptInput.value : '';

  let aspectRatioValue = '1:1';
  if (elements.aspectRatioRadios) {
    const radios = Array.from(elements.aspectRatioRadios);
    const checked = radios.find(radio => radio.checked);
    if (checked) {
      aspectRatioValue = checked.value;
    }
  }

  const widthValue = elements.widthInput ? parseInt(elements.widthInput.value, 10) : 1024;
  const heightValue = elements.heightInput ? parseInt(elements.heightInput.value, 10) : 1024;

  return {
    prompt: promptValue,
    aspectRatio: aspectRatioValue,
    width: widthValue,
    height: heightValue,
  };
}
