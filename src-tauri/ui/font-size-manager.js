// Font Size Manager
// Handles font size preferences with localStorage persistence
const FONT_SIZE_KEY = 'textbrush-font-size';
const VALID_SIZES = ['small', 'medium', 'large'];
const DEFAULT_SIZE = 'medium';
/**
 * Initialize font size from localStorage or use default.
 * Should be called early in app initialization.
 */
export function initFontSize() {
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
export function setFontSize(size) {
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
export function getCurrentFontSize() {
    const size = document.documentElement.getAttribute('data-font-size');
    return isValidFontSize(size) ? size : DEFAULT_SIZE;
}
/**
 * Type guard to check if a value is a valid font size.
 */
function isValidFontSize(value) {
    return typeof value === 'string' && VALID_SIZES.includes(value);
}
/**
 * Apply font size to DOM.
 */
function applyFontSize(size) {
    document.documentElement.setAttribute('data-font-size', size);
}
