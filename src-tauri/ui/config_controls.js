// UI Configuration Controls - Frontend Implementation
//
// Responsibilities:
// 1. Replace read-only prompt display with editable text input
// 2. Add radio button group for aspect ratio selection
// 3. Add width/height input fields for custom dimensions
// 4. Handle blur/Enter events to trigger configuration update
// 5. Manage local state synchronization

const { invoke } = window.__TAURI__.core;

// Default dimensions for each aspect ratio
const ASPECT_RATIO_DIMENSIONS = {
    '1:1': { width: 1024, height: 1024 },
    '16:9': { width: 1344, height: 768 },
    '9:16': { width: 768, height: 1344 },
};

/**
 * Initialize configuration controls in the UI.
 *
 * CONTRACT:
 *   Inputs:
 *     - initialPrompt: string, initial prompt from CLI launch args
 *     - initialAspectRatio: string, initial aspect ratio from CLI (default "1:1")
 *     - state: object, application state object to sync with
 *     - elements: object, cached DOM element references
 *
 *   Outputs: none (modifies DOM, sets up event listeners)
 *
 *   Invariants:
 *     - Prompt display element (#prompt-display) is replaced with text input
 *     - Aspect ratio radio button group is added to status bar
 *     - Width/height input fields are added for custom dimensions
 *     - Input fields are populated with initial values
 *     - Event listeners are attached for blur/Enter on prompt input
 *     - Event listeners are attached for change on aspect ratio radios
 *     - Event listeners are attached for dimension inputs
 *     - State object is updated with current config values
 *
 *   Properties:
 *     - UI consistency: input fields always reflect actual generation config
 *     - Event-driven: config updates triggered by blur or Enter keypress
 *     - Non-blocking: invoke calls return immediately, backend handles restart
 *     - Error handling: validation errors shown inline (prompt non-empty)
 *     - Dimension sync: changing aspect ratio updates dimension fields
 *
 *   Algorithm:
 *     1. Cache initial config values in local state
 *     2. Replace prompt display with text input
 *     3. Create aspect ratio radio button group
 *     4. Create width/height input fields
 *     5. Attach event listeners for all controls
 *     6. Store references to input elements in state/elements
 *
 * Integration:
 *   - Called from init() after launch args are retrieved
 *   - Modifies existing status bar section
 *   - Coordinates with existing state management
 */
export function initConfigControls(initialPrompt, initialAspectRatio, state, elements) {
    state.aspectRatio = initialAspectRatio || '1:1';

    // Initialize dimensions from aspect ratio
    const initialDims = ASPECT_RATIO_DIMENSIONS[state.aspectRatio] || { width: 1024, height: 1024 };
    state.width = initialDims.width;
    state.height = initialDims.height;

    // Get existing HTML elements (they're already in the DOM from index.html)
    const promptInput = document.getElementById('prompt-input');
    const widthInput = document.getElementById('width-input');
    const heightInput = document.getElementById('height-input');
    const aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');

    // Set initial values
    if (promptInput) {
        promptInput.value = initialPrompt;
        elements.promptInput = promptInput;
    }

    if (widthInput) {
        widthInput.value = state.width;
        elements.widthInput = widthInput;
    }

    if (heightInput) {
        heightInput.value = state.height;
        elements.heightInput = heightInput;
    }

    // Convert NodeList to array and set initial checked state
    const radios = Array.from(aspectRatioRadios);
    radios.forEach(radio => {
        radio.checked = radio.value === state.aspectRatio;
    });
    elements.aspectRatioRadios = radios;

    // Prompt input event listeners
    if (promptInput) {
        promptInput.addEventListener('blur', () => {
            const config = getCurrentConfig(elements);
            handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
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
                widthInput.value = dims.width;
                heightInput.value = dims.height;
                dimensionChangeFromAspectRatio = false;
            }
            const config = getCurrentConfig(elements);
            handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
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
        handleConfigUpdate(config.prompt, config.aspectRatio, config.width, config.height, state);
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
 *
 * CONTRACT:
 *   Inputs:
 *     - promptValue: string, current value from prompt input field
 *     - aspectRatioValue: string, current selected aspect ratio
 *     - widthValue: number, current width value
 *     - heightValue: number, current height value
 *     - state: object, application state to update
 *
 *   Outputs: Promise<void> (async operation)
 *
 *   Invariants:
 *     - Prompt must be non-empty (validation)
 *     - Dimensions must be valid (64-2048, divisible by 64)
 *     - If validation fails: show inline error, do not invoke backend
 *     - If validation passes:
 *       * Update local state with new values
 *       * Invoke Rust command: update_generation_config(prompt, aspect_ratio, width, height)
 *       * Wait for command result
 *       * If error: show error message, revert state
 *     - Backend will send BUFFER_STATUS event when restart complete
 *
 *   Properties:
 *     - Validation: prompt non-empty, dimensions in valid range
 *     - Async: returns Promise, uses await for invoke
 *     - Error handling: shows user-friendly error messages
 *     - State sync: updates state.prompt, state.aspectRatio, state.width, state.height
 *     - No redundant updates: detect if config actually changed
 *
 *   Algorithm:
 *     1. Validate prompt (non-empty)
 *     2. Validate dimensions (within range)
 *     3. Check if config actually changed
 *     4. Update local state
 *     5. Invoke backend command with all config values
 *     6. Handle success/error
 *
 * Error Display:
 *   - Show inline error message near input field
 *   - Use aria-live for accessibility
 *   - Auto-clear error after 3 seconds
 */
export async function handleConfigUpdate(promptValue, aspectRatioValue, widthValue, heightValue, state) {
    const trimmedPrompt = promptValue.trim();

    if (trimmedPrompt === '') {
        const promptInput = document.getElementById('prompt-input');
        if (promptInput) {
            showValidationError('Prompt cannot be empty', promptInput);
        }
        return;
    }

    // Validate dimensions
    const width = parseInt(widthValue, 10);
    const height = parseInt(heightValue, 10);

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
    if (trimmedPrompt === state.prompt &&
        aspectRatioValue === state.aspectRatio &&
        width === state.width &&
        height === state.height) {
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
            height: height
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
            showValidationError(`Update failed: ${error}`, promptInput);
        }
    }
}

/**
 * Show validation error message to user.
 *
 * CONTRACT:
 *   Inputs:
 *     - message: string, error message to display
 *     - inputElement: DOM element, the input field that caused the error
 *
 *   Outputs: none (updates DOM)
 *
 *   Invariants:
 *     - Error message is displayed near the input element
 *     - Error has appropriate styling (red, accessible)
 *     - Previous error messages are cleared
 *     - Error auto-clears after 5 seconds
 *
 *   Properties:
 *     - Accessible: uses aria-live region
 *     - Temporary: auto-clears after timeout
 *     - Visual feedback: clear error indication
 *
 *   Algorithm:
 *     1. Clear any existing error messages
 *     2. Create error element with message
 *     3. Add aria-live="polite" and role="alert"
 *     4. Style with error class
 *     5. Insert after input element
 *     6. Set timeout to remove error after 5 seconds
 */
export function showValidationError(message, inputElement) {
    const existingErrors = document.querySelectorAll('.validation-error');
    existingErrors.forEach(error => error.remove());

    const errorElement = document.createElement('div');
    errorElement.className = 'validation-error';
    errorElement.textContent = message;
    errorElement.setAttribute('role', 'alert');
    errorElement.setAttribute('aria-live', 'polite');

    if (inputElement && inputElement.parentNode) {
        inputElement.parentNode.insertBefore(errorElement, inputElement.nextSibling);
    }

    setTimeout(() => {
        errorElement.remove();
    }, 3000);
}

/**
 * Get current configuration from UI inputs.
 *
 * CONTRACT:
 *   Inputs:
 *     - elements: object, cached DOM element references
 *
 *   Outputs:
 *     - object with { prompt: string, aspectRatio: string, width: number, height: number }
 *
 *   Invariants:
 *     - Returns current values from input fields
 *     - Values are not validated (caller's responsibility)
 *
 *   Properties:
 *     - Read-only: does not modify state or DOM
 *     - Simple: just reads input.value and radio.checked
 *
 *   Algorithm:
 *     1. Get prompt from prompt input field
 *     2. Find checked radio button in aspect ratio group
 *     3. Get width and height from dimension inputs
 *     4. Return object with all values
 */
export function getCurrentConfig(elements) {
    const promptValue = elements.promptInput ? elements.promptInput.value : '';

    let aspectRatioValue = '1:1';
    if (elements.aspectRatioRadios) {
        const checked = elements.aspectRatioRadios.find(radio => radio.checked);
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
        height: heightValue
    };
}
