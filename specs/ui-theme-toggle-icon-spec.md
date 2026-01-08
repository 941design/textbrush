# Feature Specification: Theme Toggle Icon

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The current theme toggle button uses the character `◐` (Unicode U+25D0, Circle with Left Half Black). While functional, this symbol:

1. **May not render consistently** across different fonts and platforms
2. **Is not immediately recognizable** as a theme toggle
3. **Doesn't indicate current theme** or what clicking will do
4. **Lacks visual polish** compared to standard sun/moon icons

Users familiar with dark/light mode toggles expect to see sun (light mode) or moon (dark mode) icons.

## Core Functionality

Replace the theme toggle icon with standard sun/moon SVG icons that:
- Indicate the current theme visually
- Animate smoothly between states
- Are universally recognizable

## Functional Requirements

### FR1: Theme-Appropriate Icons

**Requirement:** Show different icon based on current theme

**Behavior:**
- Dark theme active: Show sun icon (indicates "switch to light")
- Light theme active: Show moon icon (indicates "switch to dark")

**Alternative Interpretation:**
- Dark theme active: Show moon icon (indicates "you're in dark mode")
- Light theme active: Show sun icon (indicates "you're in light mode")

**Recommendation:** Use first interpretation—icon shows what clicking will do, not current state. This is more common in modern UIs.

### FR2: SVG Icons

**Requirement:** Use inline SVG for icons

**Icons:**

**Sun Icon (shown in dark mode):**
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="5"></circle>
    <line x1="12" y1="1" x2="12" y2="3"></line>
    <line x1="12" y1="21" x2="12" y2="23"></line>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
    <line x1="1" y1="12" x2="3" y2="12"></line>
    <line x1="21" y1="12" x2="23" y2="12"></line>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
</svg>
```

**Moon Icon (shown in light mode):**
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
</svg>
```

### FR3: Smooth Transition

**Requirement:** Animate between icons on theme change

**Options:**

**Option A - Crossfade:**
- Sun fades out, moon fades in (or vice versa)
- Duration: 200ms
- Simple, reliable

**Option B - Morph:**
- Sun morphs into moon shape
- More complex, requires animation library or complex SVG
- Not recommended due to complexity

**Option C - Rotate/Scale:**
- Icon rotates 180° and scales down during transition
- New icon rotates in from opposite direction
- Medium complexity

**Recommendation:** Option A (crossfade) for simplicity.

### FR4: Icon Sizing

**Requirement:** Icon size matches button dimensions

**Sizing:**
- Icon viewBox: 24x24
- Rendered size: 18x18 (matches current 18px font-size)
- Centered in 36x36 button

### FR5: Accessibility

**Requirement:** Icon is accessible

**Implementation:**
- SVG has `aria-hidden="true"`
- Button has descriptive `aria-label`
- Label updates based on theme: "Switch to light theme" / "Switch to dark theme"

**Example:**
```html
<button class="theme-toggle" aria-label="Switch to light theme">
    <span class="theme-icon sun" aria-hidden="true">
        <!-- sun SVG -->
    </span>
    <span class="theme-icon moon" aria-hidden="true">
        <!-- moon SVG -->
    </span>
</button>
```

## Critical Constraints

### Technical Constraints

1. **No Animation Libraries:**
   - Use CSS transitions only
   - No JavaScript animation frameworks
   - Keep implementation simple

2. **Icon Consistency:**
   - Same stroke width as other SVG icons (if implemented)
   - Same styling approach (currentColor)
   - Consistent with design system

3. **State Synchronization:**
   - Icon state must match actual theme
   - No flickering on page load
   - Handles system theme preference correctly

### User Experience Constraints

1. **Recognition:**
   - Icons must be immediately recognizable
   - Sun = light, Moon = dark is universal
   - No ambiguity about function

2. **Feedback:**
   - Click should provide immediate visual feedback
   - Transition should feel smooth and intentional
   - No jarring state changes

3. **Consistency:**
   - Button size and position unchanged
   - Hover/focus states preserved
   - Matches overall UI aesthetic

## Design Options Analysis

### Icon Style Options

**Option 1: Outline Style (Recommended)**
- Matches other icons if SVG icon spec is implemented
- Clean, minimal appearance
- Works well in both themes

**Option 2: Filled Style**
- More prominent
- May be too bold for subtle toggle
- Not consistent with outline approach elsewhere

**Option 3: Hybrid (outline + filled)**
- Sun rays as lines, circle filled
- More complex
- May not scale well

### Transition Options

**Crossfade (Recommended):**
```css
.theme-icon {
    position: absolute;
    opacity: 0;
    transition: opacity 200ms ease;
}

.theme-icon.active {
    opacity: 1;
}
```

**Rotate:**
```css
.theme-toggle svg {
    transition: transform 200ms ease;
}

.theme-toggle:active svg {
    transform: rotate(180deg);
}
```

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<button
    class="theme-toggle"
    id="theme-toggle"
    type="button"
    title="Toggle theme"
    aria-label="Switch to light theme"
>
    <span class="theme-icon theme-icon-sun" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
    </span>
    <span class="theme-icon theme-icon-moon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
    </span>
</button>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.theme-toggle {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    background: transparent;
    border: 1px solid var(--border-default);
    border-radius: 6px;
    color: var(--text-primary);
    cursor: pointer;
    transition: all var(--transition-fast);
    flex-shrink: 0;
}

.theme-icon {
    position: absolute;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transition: opacity 200ms ease;
}

.theme-icon svg {
    width: 18px;
    height: 18px;
}

/* Dark theme: show sun (to switch to light) */
:root[data-theme="dark"] .theme-icon-sun,
:root:not([data-theme]) .theme-icon-sun {
    opacity: 1;
}

/* Light theme: show moon (to switch to dark) */
:root[data-theme="light"] .theme-icon-moon {
    opacity: 1;
}

.theme-toggle:hover {
    background: var(--bg-secondary);
    border-color: var(--border-focus);
}

.theme-toggle:active {
    transform: scale(0.95);
}

.theme-toggle:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}
```

### JavaScript (`src-tauri/ui/theme-manager.js`)

**Changes Required:**
```javascript
// Update aria-label when theme changes
export function updateThemeToggleLabel() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';

    toggle.setAttribute('aria-label', `Switch to ${nextTheme} theme`);
    toggle.title = `Switch to ${nextTheme} theme`;
}

// Call after theme toggle
export function toggleTheme() {
    // ... existing toggle logic
    updateThemeToggleLabel();
}

// Call on init
export function initTheme() {
    // ... existing init logic
    updateThemeToggleLabel();
}
```

## Out of Scope

- Animated icon morphing (sun rays spinning, etc.)
- System theme auto-detection indicator
- Theme preview on hover
- Multiple theme options (beyond dark/light)
- Icon customization
- Animated sun rays or moon stars

## Success Criteria

### Functional Acceptance

1. **Icon Display:**
   - Sun icon shown when in dark theme
   - Moon icon shown when in light theme

2. **Transition:**
   - Smooth crossfade between icons
   - No flash or jump

3. **Accessibility:**
   - Correct aria-label for current state
   - Screen reader announces theme switch

4. **Consistency:**
   - Icons render consistently across platforms
   - Match design system styling

### Non-Functional Acceptance

1. **Performance:** No perceptible delay on toggle
2. **Visual Quality:** Icons crisp at all sizes
3. **Maintainability:** Easy to update icon designs

## Implementation Notes

**Estimated Effort:** Small (30 minutes - 1 hour)

**Testing Requirements:**
- Icon display in both themes
- Transition animation
- Accessibility label updates
- Cross-platform rendering

**Dependencies:**
- If Control Button Icons spec is implemented first, ensure consistency
- Uses existing theme-manager.js

**Rollout Plan:**
1. Add SVG icons to index.html
2. Update CSS for icon visibility and transitions
3. Update theme-manager.js for aria-label
4. Test in both themes
5. Verify accessibility

**Icon Source:**
- Icons based on Feather Icons (MIT license)
- Sun: feather "sun" icon
- Moon: feather "moon" icon
