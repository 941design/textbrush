// UI Configuration Controls - Frontend Implementation Stub
//
// Responsibilities:
// 1. Replace read-only prompt display with editable text input
// 2. Add radio button group for aspect ratio selection
// 3. Handle blur/Enter events to trigger configuration update
// 4. Manage local state synchronization

const { invoke } = window.__TAURI__.core;

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
 *     - Input fields are populated with initial values
 *     - Event listeners are attached for blur/Enter on prompt input
 *     - Event listeners are attached for change on aspect ratio radios
 *     - State object is updated with current config values
 *
 *   Properties:
 *     - UI consistency: input fields always reflect actual generation config
 *     - Event-driven: config updates triggered by blur or Enter keypress
 *     - Non-blocking: invoke calls return immediately, backend handles restart
 *     - Error handling: validation errors shown inline (prompt non-empty)
 *
 *   Algorithm:
 *     1. Cache initial config values in local state
 *     2. Replace prompt display with text input:
 *        a. Find #prompt-display element
 *        b. Create text input with initial prompt value
 *        c. Set attributes: id, class, placeholder, title, aria-label
 *        d. Replace element in DOM
 *     3. Create aspect ratio radio button group:
 *        a. Create container div with class "aspect-ratio-controls"
 *        b. Create label "Aspect Ratio:"
 *        c. For each option ("1:1", "16:9", "9:16"):
 *           - Create radio input with name="aspect_ratio", value=option
 *           - Create label for radio
 *           - Set checked state based on initialAspectRatio
 *        d. Insert into status bar after prompt input
 *     4. Attach event listeners:
 *        a. Prompt input:
 *           - blur event → handleConfigUpdate()
 *           - keydown event → if Enter key, blur input (triggers update)
 *        b. Aspect ratio radios:
 *           - change event → handleConfigUpdate()
 *     5. Store references to input elements in state/elements
 *
 * Integration:
 *   - Called from init() after launch args are retrieved
 *   - Modifies existing status bar section
 *   - Coordinates with existing state management
 */
export function initConfigControls(initialPrompt, initialAspectRatio, state, elements) {
    state.aspectRatio = initialAspectRatio || '1:1';

    const promptInput = document.createElement('input');
    promptInput.type = 'text';
    promptInput.id = 'prompt-input';
    promptInput.className = 'prompt-input';
    promptInput.value = initialPrompt;
    promptInput.placeholder = 'Enter prompt...';
    promptInput.title = 'Image generation prompt';
    promptInput.setAttribute('aria-label', 'Image generation prompt');

    if (elements.promptDisplay && elements.promptDisplay.parentNode) {
        elements.promptDisplay.parentNode.replaceChild(promptInput, elements.promptDisplay);
    }
    elements.promptInput = promptInput;

    const aspectRatioContainer = document.createElement('div');
    aspectRatioContainer.className = 'aspect-ratio-controls';

    const label = document.createElement('span');
    label.className = 'aspect-ratio-label';
    label.textContent = 'Aspect Ratio:';
    aspectRatioContainer.appendChild(label);

    const ratios = ['1:1', '16:9', '9:16'];
    const radios = [];

    ratios.forEach(ratio => {
        const radioWrapper = document.createElement('label');
        radioWrapper.className = 'aspect-ratio-option';

        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'aspect_ratio';
        radio.value = ratio;
        radio.checked = ratio === state.aspectRatio;
        radio.setAttribute('aria-label', `Aspect ratio ${ratio}`);

        const labelText = document.createTextNode(ratio);

        radioWrapper.appendChild(radio);
        radioWrapper.appendChild(labelText);
        aspectRatioContainer.appendChild(radioWrapper);
        radios.push(radio);
    });

    const statusRight = document.querySelector('.status-right');
    if (statusRight && statusRight.parentNode) {
        statusRight.parentNode.insertBefore(aspectRatioContainer, statusRight);
    }

    elements.aspectRatioControls = aspectRatioContainer;
    elements.aspectRatioRadios = radios;

    promptInput.addEventListener('blur', () => {
        const config = getCurrentConfig(elements);
        handleConfigUpdate(config.prompt, config.aspectRatio, state);
    });

    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            promptInput.blur();
        }
    });

    radios.forEach(radio => {
        radio.addEventListener('change', () => {
            const config = getCurrentConfig(elements);
            handleConfigUpdate(config.prompt, config.aspectRatio, state);
        });
    });
}

/**
 * Handle configuration update (prompt or aspect ratio changed).
 *
 * CONTRACT:
 *   Inputs:
 *     - promptValue: string, current value from prompt input field
 *     - aspectRatioValue: string, current selected aspect ratio
 *     - state: object, application state to update
 *
 *   Outputs: Promise<void> (async operation)
 *
 *   Invariants:
 *     - Prompt must be non-empty (validation)
 *     - Aspect ratio must be one of "1:1", "16:9", "9:16" (validation)
 *     - If validation fails: show inline error, do not invoke backend
 *     - If validation passes:
 *       * Update local state with new values
 *       * Invoke Rust command: update_generation_config(prompt, aspect_ratio)
 *       * Wait for command result
 *       * If error: show error message, revert state
 *     - Backend will send BUFFER_STATUS event when restart complete
 *
 *   Properties:
 *     - Validation: prompt non-empty, aspect ratio valid
 *     - Async: returns Promise, uses await for invoke
 *     - Error handling: shows user-friendly error messages
 *     - State sync: updates state.prompt and state.aspectRatio
 *     - No redundant updates: detect if config actually changed
 *
 *   Algorithm:
 *     1. Validate prompt:
 *        a. Trim whitespace
 *        b. If empty: show error "Prompt cannot be empty", return
 *     2. Validate aspect ratio:
 *        a. Check against allowed values ["1:1", "16:9", "9:16"]
 *        b. If invalid: show error, return
 *     3. Check if config actually changed:
 *        a. Compare with state.prompt and state.aspectRatio
 *        b. If same: no-op, return
 *     4. Update local state:
 *        a. state.prompt = promptValue
 *        b. state.aspectRatio = aspectRatioValue
 *     5. Invoke backend command:
 *        a. Try: await invoke('update_generation_config', { prompt, aspect_ratio })
 *        b. If error:
 *           - Show error message to user
 *           - Revert state to previous values
 *           - Log error
 *        c. If success:
 *           - Log success
 *           - Wait for BUFFER_STATUS event (UI will update automatically)
 *     6. Return
 *
 * Error Display:
 *   - Show inline error message near input field
 *   - Use aria-live for accessibility
 *   - Auto-clear error after 5 seconds or on next valid input
 */
export async function handleConfigUpdate(promptValue, aspectRatioValue, state) {
    const trimmedPrompt = promptValue.trim();

    if (trimmedPrompt === '') {
        const promptInput = document.getElementById('prompt-input');
        if (promptInput) {
            showValidationError('Prompt cannot be empty', promptInput);
        }
        return;
    }

    const validAspectRatios = ['1:1', '16:9', '9:16'];
    if (!validAspectRatios.includes(aspectRatioValue)) {
        const aspectRatioControls = document.querySelector('.aspect-ratio-controls');
        if (aspectRatioControls) {
            showValidationError('Invalid aspect ratio', aspectRatioControls);
        }
        return;
    }

    if (trimmedPrompt === state.prompt && aspectRatioValue === state.aspectRatio) {
        return;
    }

    const previousPrompt = state.prompt;
    const previousAspectRatio = state.aspectRatio;

    state.prompt = trimmedPrompt;
    state.aspectRatio = aspectRatioValue;

    try {
        await invoke('update_generation_config', {
            prompt: trimmedPrompt,
            aspect_ratio: aspectRatioValue
        });
        console.log('Configuration updated successfully');
    } catch (error) {
        console.error('Configuration update failed:', error);

        state.prompt = previousPrompt;
        state.aspectRatio = previousAspectRatio;

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
 *     - object with { prompt: string, aspectRatio: string }
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
 *     3. Return object with both values
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

    return {
        prompt: promptValue,
        aspectRatio: aspectRatioValue
    };
}
