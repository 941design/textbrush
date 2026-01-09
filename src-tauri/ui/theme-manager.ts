// Theme Management Module
// Handles light/dark theme switching, persistence, and system preference detection

type Theme = 'light' | 'dark';

/**
 * Initialize theme system and apply saved/system preference.
 */
export function initTheme(): Theme {
  const saved = localStorage.getItem('textbrush-theme');

  let theme: Theme;
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
 */
export function toggleTheme(): Theme {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const newTheme: Theme = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('textbrush-theme', newTheme);
  return newTheme;
}

/**
 * Get current active theme.
 */
export function getCurrentTheme(): Theme {
  const theme = document.documentElement.getAttribute('data-theme');
  return theme === 'light' ? 'light' : 'dark';
}
