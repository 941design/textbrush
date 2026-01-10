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

interface Resolution {
  width: number;
  height: number;
}

// Supported aspect ratios with their available resolutions (smallest to largest)
// Must match SUPPORTED_RATIOS in textbrush/cli.py
const ASPECT_RATIO_RESOLUTIONS: Record<string, Resolution[]> = {
  '1:1': [
    { width: 256, height: 256 },
    { width: 512, height: 512 },
    { width: 1024, height: 1024 },
  ],
  '16:9': [
    { width: 640, height: 360 },
    { width: 1280, height: 720 },
    { width: 1920, height: 1080 },
  ],
  '3:1': [
    { width: 900, height: 300 },
    { width: 1500, height: 500 },
    { width: 1800, height: 600 },
  ],
  '4:1': [
    { width: 1200, height: 300 },
    { width: 1600, height: 400 },
  ],
  '4:5': [
    { width: 540, height: 675 },
    { width: 1080, height: 1350 },
  ],
  '9:16': [
    { width: 360, height: 640 },
    { width: 1080, height: 1920 },
  ],
};

// Get list of supported aspect ratios
export const SUPPORTED_RATIOS = Object.keys(ASPECT_RATIO_RESOLUTIONS);

// Get default (first) resolution for an aspect ratio
function getDefaultResolution(ratio: string): Resolution {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length === 0) {
    return { width: 256, height: 256 };
  }
  const first = resolutions[0];
  return first ?? { width: 256, height: 256 };
}

// Get resolution index for current dimensions
function getResolutionIndex(ratio: string, width: number, height: number): number {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions) return 0;
  const index = resolutions.findIndex(r => r.width === width && r.height === height);
  return index >= 0 ? index : 0;
}

// Check if we can increase resolution
export function canIncreaseResolution(ratio: string, width: number, height: number): boolean {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length <= 1) return false;
  const index = getResolutionIndex(ratio, width, height);
  return index < resolutions.length - 1;
}

// Check if we can decrease resolution
export function canDecreaseResolution(ratio: string, width: number, height: number): boolean {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length <= 1) return false;
  const index = getResolutionIndex(ratio, width, height);
  return index > 0;
}

// Get next higher resolution
export function getNextResolution(ratio: string, width: number, height: number): Resolution | null {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions) return null;
  const index = getResolutionIndex(ratio, width, height);
  if (index < resolutions.length - 1) {
    const next = resolutions[index + 1];
    return next ?? null;
  }
  return null;
}

// Get next lower resolution
export function getPreviousResolution(ratio: string, width: number, height: number): Resolution | null {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions) return null;
  const index = getResolutionIndex(ratio, width, height);
  if (index > 0) {
    const prev = resolutions[index - 1];
    return prev ?? null;
  }
  return null;
}

interface ConfigValues {
  prompt: string;
  aspectRatio: string;
  width: number;
  height: number;
}

// Update resolution button states based on current dimensions
function updateResolutionButtons(ratio: string, width: number, height: number): void {
  const decreaseBtn = document.getElementById('resolution-decrease') as HTMLButtonElement | null;
  const increaseBtn = document.getElementById('resolution-increase') as HTMLButtonElement | null;

  if (decreaseBtn) {
    decreaseBtn.disabled = !canDecreaseResolution(ratio, width, height);
  }
  if (increaseBtn) {
    increaseBtn.disabled = !canIncreaseResolution(ratio, width, height);
  }
}

/**
 * Initialize configuration controls in the UI.
 */
export function initConfigControls(
  initialPrompt: string,
  initialAspectRatio: string,
  initialWidth: number,
  initialHeight: number,
  state: AppState,
  elements: Elements
): void {
  // Validate and set aspect ratio
  state.aspectRatio = SUPPORTED_RATIOS.includes(initialAspectRatio) ? initialAspectRatio : '1:1';

  // Use dimensions from launch args (already resolved by Rust backend)
  state.width = initialWidth;
  state.height = initialHeight;

  // Get existing HTML elements (they're already in the DOM from index.html)
  const promptInput = document.getElementById('prompt-input') as HTMLInputElement | null;
  const dimensionDisplay = document.getElementById('dimension-display') as HTMLElement | null;
  const aspectRatioRadios = document.querySelectorAll<HTMLInputElement>('input[name="aspect-ratio"]');
  const decreaseBtn = document.getElementById('resolution-decrease') as HTMLButtonElement | null;
  const increaseBtn = document.getElementById('resolution-increase') as HTMLButtonElement | null;

  // Set initial values
  if (promptInput) {
    promptInput.value = initialPrompt;
    elements.promptInput = promptInput;
  }

  // Update dimension display
  if (dimensionDisplay) {
    dimensionDisplay.textContent = `${state.width}×${state.height}`;
  }

  // Convert NodeList to array and set initial checked state
  const radios = Array.from(aspectRatioRadios);
  radios.forEach(radio => {
    radio.checked = radio.value === state.aspectRatio;
  });
  elements.aspectRatioRadios = aspectRatioRadios;

  // Initial button state update
  updateResolutionButtons(state.aspectRatio, state.width, state.height);

  // Prompt input event listeners
  if (promptInput) {
    promptInput.addEventListener('blur', () => {
      const config = getCurrentConfig(elements, state);
      void handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
    });

    promptInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        promptInput.blur();
      }
    });
  }

  // Aspect ratio radio event listeners
  radios.forEach(radio => {
    radio.addEventListener('change', () => {
      const ratio = radio.value;
      const dims = getDefaultResolution(ratio);

      // Update state and display
      state.width = dims.width;
      state.height = dims.height;
      if (dimensionDisplay) {
        dimensionDisplay.textContent = `${dims.width}×${dims.height}`;
      }

      // Update button states
      updateResolutionButtons(ratio, dims.width, dims.height);

      const config = getCurrentConfig(elements, state);
      void handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
    });
  });

  // Resolution decrease button
  if (decreaseBtn) {
    decreaseBtn.addEventListener('click', () => {
      const prevRes = getPreviousResolution(state.aspectRatio, state.width, state.height);
      if (prevRes) {
        // Update UI immediately with new resolution
        if (dimensionDisplay) {
          dimensionDisplay.textContent = `${prevRes.width}×${prevRes.height}`;
        }
        updateResolutionButtons(state.aspectRatio, prevRes.width, prevRes.height);

        // Get current prompt and aspect ratio
        const config = getCurrentConfig(elements, state);

        // Pass new dimensions directly - state will be updated by handleConfigUpdate if successful
        // (Don't update state.width/height here, as handleConfigUpdate compares against state)
        void handleConfigUpdate(config.prompt, config.aspectRatio, prevRes.width, prevRes.height, state);
      }
    });
  }

  // Resolution increase button
  if (increaseBtn) {
    increaseBtn.addEventListener('click', () => {
      const nextRes = getNextResolution(state.aspectRatio, state.width, state.height);
      if (nextRes) {
        // Update UI immediately with new resolution
        if (dimensionDisplay) {
          dimensionDisplay.textContent = `${nextRes.width}×${nextRes.height}`;
        }
        updateResolutionButtons(state.aspectRatio, nextRes.width, nextRes.height);

        // Get current prompt and aspect ratio
        const config = getCurrentConfig(elements, state);

        // Pass new dimensions directly - state will be updated by handleConfigUpdate if successful
        // (Don't update state.width/height here, as handleConfigUpdate compares against state)
        void handleConfigUpdate(config.prompt, config.aspectRatio, nextRes.width, nextRes.height, state);
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

  // Dimensions are now controlled via predefined resolutions, no validation needed
  const width = widthValue;
  const height = heightValue;

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

    // Update generationPrompt since backend clears buffer on config update.
    // Any new images will use the new prompt, so spinner should reflect this.
    state.generationPrompt = trimmedPrompt;

    // Update loading prompt immediately if overlay is visible
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingPrompt = document.getElementById('loading-prompt');
    if (loadingOverlay && !loadingOverlay.classList.contains('hidden') && loadingPrompt) {
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
 * Get current configuration from UI inputs and state.
 */
export function getCurrentConfig(elements: Elements, state: AppState): ConfigValues {
  const promptValue = elements.promptInput ? elements.promptInput.value : '';

  let aspectRatioValue = '1:1';
  if (elements.aspectRatioRadios) {
    const radios = Array.from(elements.aspectRatioRadios);
    const checked = radios.find(radio => radio.checked);
    if (checked) {
      aspectRatioValue = checked.value;
    }
  }

  // Width and height now come from state (controlled by +/- buttons)
  return {
    prompt: promptValue,
    aspectRatio: aspectRatioValue,
    width: state.width,
    height: state.height,
  };
}
