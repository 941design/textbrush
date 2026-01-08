// Button Flash Animation Utilities
// Provides visual feedback by flashing buttons when keyboard shortcuts are pressed

/**
 * Flash a button element with press animation.
 *
 * CONTRACT:
 *   Inputs:
 *     - buttonElement: DOM element (button) to flash
 *
 *   Outputs: None (applies CSS class, removes after animation)
 *
 *   Invariants:
 *     - Adds 'btn-pressed' class to buttonElement
 *     - Removes 'btn-pressed' class after 150ms (animation duration)
 *     - Does not block execution (uses setTimeout)
 *     - Safe to call on null/undefined element (no-op)
 *
 *   Properties:
 *     - Non-blocking: returns immediately, cleanup happens via setTimeout
 *     - CSS-driven: animation defined in animations.css (@keyframes btnPress)
 *     - Duration match: removal timeout matches animation duration (150ms)
 *     - Accessibility: respects prefers-reduced-motion (CSS handles this)
 *     - Idempotent: calling multiple times rapid-fire is safe (class add is idempotent)
 *
 *   Algorithm:
 *     1. Check if buttonElement is null/undefined
 *     2. If yes: return (no-op)
 *     3. Add 'btn-pressed' class to buttonElement.classList
 *     4. Set timeout for 150ms:
 *        a. Remove 'btn-pressed' class from buttonElement.classList
 *     5. Return immediately
 */
export function flashButton(buttonElement) {
  if (!buttonElement) {
    return;
  }

  buttonElement.classList.add('btn-pressed');

  setTimeout(() => {
    buttonElement.classList.remove('btn-pressed');
  }, 150);
}

/**
 * Flash button by ID selector.
 *
 * CONTRACT:
 *   Inputs:
 *     - buttonId: String ID of button element (e.g., "skip-btn", "accept-btn")
 *
 *   Outputs: Boolean (true if button found and flashed, false if not found)
 *
 *   Invariants:
 *     - Queries DOM for element with ID = buttonId
 *     - If found: calls flashButton(element)
 *     - If not found: no-op, returns false
 *
 *   Properties:
 *     - Convenience wrapper: avoids manual getElementById in callers
 *     - Safe: handles missing elements gracefully
 *     - Feedback: returns boolean to indicate success
 *
 *   Algorithm:
 *     1. Call document.getElementById(buttonId)
 *     2. If result is null: return false
 *     3. Call flashButton(element)
 *     4. Return true
 */
export function flashButtonById(buttonId) {
  const element = document.getElementById(buttonId);

  if (!element) {
    return false;
  }

  flashButton(element);
  return true;
}

/**
 * Map keyboard event to button ID and flash.
 *
 * CONTRACT:
 *   Inputs:
 *     - key: String keyboard key (e.g., "ArrowLeft", "Enter", "Escape")
 *     - ctrlOrCmd: Boolean indicating if Ctrl (Windows/Linux) or Cmd (macOS) is pressed
 *
 *   Outputs: Boolean (true if button flashed, false if no mapping)
 *
 *   Invariants:
 *     - Maps keys to button IDs:
 *       * "ArrowLeft" → "previous-btn" (if exists)
 *       * "ArrowRight" or " " (space) → "skip-btn"
 *       * "Enter" → "accept-btn"
 *       * "Escape" → "abort-btn"
 *       * "Delete" or "Backspace" (with ctrlOrCmd) → flash image area (custom)
 *     - Calls flashButtonById with mapped ID
 *     - Returns true if mapping exists, false otherwise
 *
 *   Properties:
 *     - Mapping logic: single source of truth for key-to-button associations
 *     - Modifier aware: handles Ctrl/Cmd for deletion
 *     - Extensible: easy to add new key mappings
 *
 *   Algorithm:
 *     1. Check key value:
 *        - If "ArrowLeft": flashButtonById("previous-btn")
 *        - If "ArrowRight" or " ": flashButtonById("skip-btn")
 *        - If "Enter": flashButtonById("accept-btn")
 *        - If "Escape": flashButtonById("abort-btn")
 *        - If ("Delete" or "Backspace") AND ctrlOrCmd: flash image container (TBD)
 *        - Else: return false
 *     2. Return true if matched, false otherwise
 */
export function flashButtonForKey(key, ctrlOrCmd = false) {
  switch (key) {
    case 'ArrowLeft':
      return flashButtonById('previous-btn');

    case 'ArrowRight':
    case ' ':
      return flashButtonById('skip-btn');

    case 'Enter':
      return flashButtonById('accept-btn');

    case 'Escape':
      return flashButtonById('abort-btn');

    case 'Delete':
    case 'Backspace':
      if (ctrlOrCmd) {
        const imageContainer = document.getElementById('image-container');
        if (imageContainer) {
          flashButton(imageContainer);
          return true;
        }
        return false;
      }
      return false;

    default:
      return false;
  }
}
