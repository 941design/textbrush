// Font Size Manager
// Handles font size preferences with localStorage persistence

export type FontSize = 'small' | 'medium' | 'large';

const FONT_SIZE_KEY = 'textbrush-font-size';
const VALID_SIZES: FontSize[] = ['small', 'medium', 'large'];
const DEFAULT_SIZE: FontSize = 'medium';

/**
 * Initialize font size from localStorage or use default.
 * Should be called early in app initialization.
 */
export function initFontSize(): FontSize {
  const saved = localStorage.getItem(FONT_SIZE_KEY);

  if (saved && isValidFontSize(saved)) {
    applyFontSize(saved);
    return saved;
  }

  // Default to medium
  applyFontSize(DEFAULT_SIZE);
  return DEFAULT_SIZE;
}

/**
 * Set font size and persist to localStorage.
 */
export function setFontSize(size: FontSize): void {
  if (!isValidFontSize(size)) {
    console.warn(`Invalid font size: ${size}, using default`);
    size = DEFAULT_SIZE;
  }

  applyFontSize(size);
  localStorage.setItem(FONT_SIZE_KEY, size);
}

/**
 * Get current font size from DOM.
 */
export function getCurrentFontSize(): FontSize {
  const size = document.documentElement.getAttribute('data-font-size');
  return isValidFontSize(size) ? size : DEFAULT_SIZE;
}

/**
 * Type guard to check if a value is a valid font size.
 */
function isValidFontSize(value: unknown): value is FontSize {
  return typeof value === 'string' && VALID_SIZES.includes(value as FontSize);
}

/**
 * Apply font size to DOM.
 */
function applyFontSize(size: FontSize): void {
  document.documentElement.setAttribute('data-font-size', size);
}
