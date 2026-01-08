// Theme Management Module
// Handles light/dark theme switching, persistence, and system preference detection

/**
 * Initialize theme system and apply saved/system preference.
 *
 * CONTRACT:
 *   Inputs: None
 *
 *   Outputs: Current theme ("light" or "dark")
 *
 *   Invariants:
 *     - Checks localStorage for saved theme preference (key: "textbrush-theme")
 *     - If no saved preference: detect system preference via window.matchMedia('(prefers-color-scheme: dark)')
 *     - Applies theme by setting data-theme attribute on document.documentElement
 *     - Returns current theme string
 *
 *   Properties:
 *     - Persistence: Reads from localStorage on init
 *     - System respect: Falls back to OS preference if no saved theme
 *     - Idempotent: Safe to call multiple times (applies current theme)
 *     - Default: If no preference found and matchMedia unavailable, defaults to "dark"
 *
 *   Algorithm:
 *     1. Try read "textbrush-theme" from localStorage
 *     2. If found and valid ("light" or "dark"): use that
 *     3. If not found:
 *        a. Check window.matchMedia('(prefers-color-scheme: dark)').matches
 *        b. If matches: theme = "dark", else theme = "light"
 *     4. Set document.documentElement.setAttribute('data-theme', theme)
 *     5. Return theme
 */
export function initTheme() {
  const saved = localStorage.getItem('textbrush-theme');

  let theme;
  if (saved === 'light' || saved === 'dark') {
    theme = saved;
  } else {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    theme = prefersDark ? 'dark' : 'light';
  }

  document.documentElement.setAttribute('data-theme', theme);
  return theme;
}

/**
 * Toggle between light and dark themes.
 *
 * CONTRACT:
 *   Inputs: None
 *
 *   Outputs: New theme after toggle ("light" or "dark")
 *
 *   Invariants:
 *     - Reads current theme from data-theme attribute on document.documentElement
 *     - Toggles to opposite: "light" → "dark", "dark" → "light"
 *     - Applies new theme via data-theme attribute
 *     - Saves to localStorage (key: "textbrush-theme")
 *     - Returns new theme string
 *
 *   Properties:
 *     - Toggle operation: current theme determines next theme
 *     - Persistence: Saves to localStorage immediately
 *     - Instantaneous: CSS variables update immediately (no page reload)
 *     - Symmetric: toggling twice returns to original theme
 *
 *   Algorithm:
 *     1. Read current theme from document.documentElement.getAttribute('data-theme')
 *     2. Calculate new theme: if current is "light" then "dark" else "light"
 *     3. Set document.documentElement.setAttribute('data-theme', newTheme)
 *     4. Save localStorage.setItem('textbrush-theme', newTheme)
 *     5. Return newTheme
 */
export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('textbrush-theme', newTheme);
  return newTheme;
}

/**
 * Get current active theme.
 *
 * CONTRACT:
 *   Inputs: None
 *
 *   Outputs: Current theme ("light" or "dark")
 *
 *   Invariants:
 *     - Reads data-theme attribute from document.documentElement
 *     - If attribute not set: defaults to "dark"
 *     - Returns string "light" or "dark"
 *
 *   Properties:
 *     - Read-only: Does not modify state
 *     - Fast: Synchronous DOM attribute read
 *     - Safe default: Returns "dark" if attribute missing
 *
 *   Algorithm:
 *     1. Read document.documentElement.getAttribute('data-theme')
 *     2. If null or undefined: return "dark"
 *     3. Otherwise: return attribute value
 */
export function getCurrentTheme() {
  return document.documentElement.getAttribute('data-theme') || 'dark';
}
