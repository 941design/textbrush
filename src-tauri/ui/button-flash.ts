// Button Flash Animation Utilities
// Provides visual feedback by flashing buttons when keyboard shortcuts are pressed

/**
 * Flash a button element with press animation.
 */
export function flashButton(buttonElement: Element | null): void {
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
 */
export function flashButtonById(buttonId: string): boolean {
  const element = document.getElementById(buttonId);

  if (!element) {
    return false;
  }

  flashButton(element);
  return true;
}

/**
 * Map keyboard event to button ID and flash.
 */
export function flashButtonForKey(key: string, ctrlOrCmd = false): boolean {
  switch (key) {
    case 'ArrowLeft':
      return flashButtonById('previous-btn');

    case 'ArrowRight':
      return flashButtonById('skip-btn');

    case ' ':
      return flashButtonById('pause-btn');

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
