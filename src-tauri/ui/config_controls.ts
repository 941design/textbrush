// UI Configuration Controls - Frontend Implementation
//
// Responsibilities:
// 1. Replace read-only prompt display with editable text input
// 2. Own the single output-size group: one radio per aspect ratio, each
//    labelled with the pixel dimensions it currently produces, plus the
//    -/+ ladder step shared by all of them
// 3. Handle blur/Enter events to trigger configuration update
// 4. Manage local state synchronization

import { invoke } from '@tauri-apps/api/core';
import type { AppState, Elements } from './types';

interface Resolution {
  width: number;
  height: number;
}

// The one output-size table: every aspect ratio with its resolution
// ladder, smallest to largest. Must match SUPPORTED_RATIOS in
// textbrush/cli.py (key set, order, and every entry).
//
// There is no second table for editing models: 4:3 and 3:4 hold exactly
// the dimensions textbrush/validation.py names landscape-small/medium/
// large and portrait-small/medium/large, so every model is offered the
// same group and the backend still recognises those six sizes by name.
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
  '4:3': [
    { width: 512, height: 384 },
    { width: 768, height: 576 },
    { width: 1024, height: 768 },
  ],
  '3:4': [
    { width: 384, height: 512 },
    { width: 576, height: 768 },
    { width: 768, height: 1024 },
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

// Resolution at a ladder position, clamped into the ladder. Ladders have
// different lengths (4:1 has two entries, 1:1 has three), so switching
// ratios carries the step position across and clamps it rather than
// dropping back to the smallest size.
export function resolutionAtStep(ratio: string, step: number): Resolution {
  const resolutions = ASPECT_RATIO_RESOLUTIONS[ratio];
  if (!resolutions || resolutions.length === 0) {
    return { width: 256, height: 256 };
  }
  const clamped = Math.min(Math.max(step, 0), resolutions.length - 1);
  return resolutions[clamped] ?? { width: 256, height: 256 };
}

/**
 * The ratio whose ladder holds exactly these dimensions, or null.
 *
 * Used to reconcile a backend-acknowledged canvas back onto the group.
 * A size no ladder holds (a config file can name one) returns null, and
 * the caller keeps the ratio it had rather than guessing.
 */
export function ratioForDimensions(width: number, height: number): string | null {
  for (const [ratio, resolutions] of Object.entries(ASPECT_RATIO_RESOLUTIONS)) {
    if (resolutions.some(entry => entry.width === width && entry.height === height)) {
      return ratio;
    }
  }
  return null;
}

// Get resolution index for current dimensions
export function getResolutionIndex(ratio: string, width: number, height: number): number {
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

/**
 * Hook the owner of the editing seam installs to claim an output-size
 * change.
 *
 * Return true to say "I sent this update myself". A model that takes
 * reference images must route a size change through the acknowledged-
 * configuration seam, because its references are decoded against the
 * canvas and have to be decoded again when the canvas moves; and while
 * no model is selected at all there is no backend to send anything to.
 * Returning false leaves the plain prompt/dimension update to this
 * module, which is the right channel for a text-only model.
 */
export type OutputSizeHandler = (ratio: string, width: number, height: number) => boolean;

// Serialize backend config updates to preserve call order under rapid UI interactions.
let configUpdateQueue: Promise<void> = Promise.resolve();

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
 * Write each option's actual pixel dimensions into its label.
 *
 * Every ratio is always visible and always carries the size it would
 * produce at the current ladder step, so the group can be read as one
 * list of concrete output sizes rather than as ratios whose meaning
 * depends on a separate control.
 */
export function renderRatioDimensions(step: number): void {
  const labels = document.querySelectorAll<HTMLElement>('.ratio-dimensions');
  labels.forEach((label) => {
    const ratio = label.dataset.ratio;
    if (!ratio) return;
    const { width, height } = resolutionAtStep(ratio, step);
    label.textContent = `${width}×${height}`;
  });
}

/**
 * Reconcile the output-size group to `state.aspectRatio/width/height`.
 *
 * Exported so the owner of the backend acknowledgement can call it: the
 * acknowledged canvas is backend truth, and the group must show the size
 * the next image will actually be generated at.
 */
export function syncOutputSizeControls(state: AppState): void {
  syncControlsFromState(state);
}

function syncControlsFromState(state: AppState): void {
  const dimensionDisplay = document.getElementById('dimension-display') as HTMLElement | null;
  if (dimensionDisplay) {
    dimensionDisplay.textContent = `${state.width}×${state.height}`;
  }

  const aspectRatioRadios = document.querySelectorAll<HTMLInputElement>('input[name="aspect-ratio"]');
  Array.from(aspectRatioRadios).forEach((radio) => {
    radio.checked = radio.value === state.aspectRatio;
  });

  updateResolutionButtons(state.aspectRatio, state.width, state.height);
  renderRatioDimensions(getResolutionIndex(state.aspectRatio, state.width, state.height));
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
  elements: Elements,
  onOutputSizeChange?: OutputSizeHandler
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
  syncControlsFromState(state);

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

  // One channel for every output-size change, whichever control made it.
  const applyOutputSize = (ratio: string, dims: Resolution): void => {
    // Optimistically update the controls while the owner of the update
    // (the handler, or handleConfigUpdate) owns state mutation.
    if (dimensionDisplay) {
      dimensionDisplay.textContent = `${dims.width}×${dims.height}`;
    }
    updateResolutionButtons(ratio, dims.width, dims.height);
    renderRatioDimensions(getResolutionIndex(ratio, dims.width, dims.height));

    if (onOutputSizeChange?.(ratio, dims.width, dims.height)) {
      // Claimed by the editing seam (or deliberately dropped because no
      // model is selected yet); state comes back from the backend ack.
      state.aspectRatio = ratio;
      state.width = dims.width;
      state.height = dims.height;
      return;
    }
    const config = getCurrentConfig(elements, state);
    void handleConfigUpdate(config.prompt, ratio, dims.width, dims.height, state);
  };

  // Aspect ratio radio event listeners
  radios.forEach(radio => {
    radio.addEventListener('change', () => {
      const ratio = radio.value;
      // Carry the ladder position across the switch: the user picked a
      // shape, not a size, and dropping to the smallest entry of the new
      // ladder would silently undo the size they had set.
      const step = getResolutionIndex(state.aspectRatio, state.width, state.height);
      applyOutputSize(ratio, resolutionAtStep(ratio, step));
    });
  });

  // Resolution decrease button
  if (decreaseBtn) {
    decreaseBtn.addEventListener('click', () => {
      const prevRes = getPreviousResolution(state.aspectRatio, state.width, state.height);
      if (prevRes) {
        applyOutputSize(state.aspectRatio, prevRes);
      }
    });
  }

  // Resolution increase button
  if (increaseBtn) {
    increaseBtn.addEventListener('click', () => {
      const nextRes = getNextResolution(state.aspectRatio, state.width, state.height);
      if (nextRes) {
        applyOutputSize(state.aspectRatio, nextRes);
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
  const attemptedPrompt = trimmedPrompt;
  const attemptedAspectRatio = aspectRatioValue;
  const attemptedWidth = width;
  const attemptedHeight = height;

  configUpdateQueue = configUpdateQueue
    .then(async () => {
      try {
        await invoke('update_generation_config', {
          prompt: attemptedPrompt,
          aspectRatio: attemptedAspectRatio,
          width: attemptedWidth,
          height: attemptedHeight,
        });
        console.log('Configuration updated successfully');
        // generationPrompt will be updated by state_changed event from backend (FR9: No optimistic updates)
      } catch (error) {
        console.error('Configuration update failed:', error);

        // Only roll back if this failed update still matches current UI state.
        // If user has already made a newer change, keep that newer state.
        const isStillCurrent =
          state.prompt === attemptedPrompt &&
          state.aspectRatio === attemptedAspectRatio &&
          state.width === attemptedWidth &&
          state.height === attemptedHeight;

        if (isStillCurrent) {
          state.prompt = previousPrompt;
          state.aspectRatio = previousAspectRatio;
          state.width = previousWidth;
          state.height = previousHeight;
          syncControlsFromState(state);
        }

        const promptInput = document.getElementById('prompt-input');
        if (promptInput) {
          showValidationError(`Update failed: ${String(error)}`, promptInput);
        }
      }
    })
    .catch((queueError: unknown) => {
      // Prevent queue poisoning from unexpected errors.
      console.error('Configuration update queue error:', queueError);
    });

  await configUpdateQueue;
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

  // One vocabulary for every model: the checked ratio plus the explicit
  // pixel dimensions the ladder resolved. Editing models used to answer
  // with 'custom' and preset dimensions here; they no longer need to,
  // because they are offered the same output-size group as text models
  // and the backend accepts any ratio alongside explicit dimensions.
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
