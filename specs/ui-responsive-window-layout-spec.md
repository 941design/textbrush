# Feature Specification: Responsive Window Layout

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The spec originally stated "Fixed size: 800x700 pixels, non-resizable" but recent commits indicate resizable window support was added. If the window is resizable, the UI should adapt gracefully to different sizes while maintaining usability.

Current issues with resizing:
1. Image container has fixed 512x512px dimensions
2. Control buttons may become cramped or too spread out
3. Status bar elements may overflow or have awkward spacing
4. No minimum size enforcement may break layout

## Core Functionality

Make the UI fully responsive within a reasonable size range, maintaining usability from minimum size up to large displays. The layout should scale proportionally and degrade gracefully.

## Functional Requirements

### FR1: Minimum Window Size

**Requirement:** Enforce minimum window dimensions

**Values:**
- Minimum width: 600px
- Minimum height: 500px

**Behavior:**
- Window cannot be resized smaller than minimum
- Configured in Tauri window settings
- Prevents layout breaking

### FR2: Image Viewer Scaling

**Requirement:** Image container scales with available space

**Behavior:**
- Image container uses percentage-based sizing, not fixed pixels
- Maintains aspect ratio based on selected ratio
- Maximum size: 90% of available viewer space
- Minimum size: 256px on smallest dimension

**Implementation:**
```css
.image-container {
    max-width: min(90%, calc(100vh - 200px)); /* Account for controls/status */
    max-height: min(90%, calc(100vh - 200px));
    width: var(--container-width);
    height: var(--container-height);
}
```

### FR3: Control Button Responsiveness

**Requirement:** Control buttons adapt to window width

**Behavior:**
- Buttons maintain minimum touch target (44x44px)
- Gap between buttons scales with available width
- On very narrow windows, button labels may hide (icon-only)
- Shortcut text always visible

**Breakpoints:**
- Width >= 700px: Full buttons (icon + label + shortcut)
- Width 600-699px: Compact buttons (icon + shortcut, smaller padding)
- Width < 600px: Not supported (minimum width)

### FR4: Status Bar Responsiveness

**Requirement:** Status bar elements adapt to available width

**Behavior:**
- Priority order for space allocation:
  1. Theme toggle (fixed width)
  2. Position indicator (fixed width)
  3. Buffer indicator (can compress dots)
  4. Seed display (can truncate)
  5. Prompt input (flexible, minimum 200px)
- Elements wrap or stack on very narrow widths

**Truncation Rules:**
- Seed: "Seed: 12345" → "12345" → hidden
- Buffer: 8 dots → 4 dots → count only
- Prompt input: Shrinks but maintains minimum

### FR5: Dynamic Layout Calculation

**Requirement:** Recalculate layout on window resize

**Behavior:**
- Listen to window resize events
- Debounce calculations (100ms)
- Update CSS custom properties for container size
- Smooth transitions during resize (if not dragging)

**Implementation:**
```javascript
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        updateContainerSize(state.aspectRatio);
        updateLayoutBreakpoint();
    }, 100);
});
```

### FR6: CSS-Based Breakpoints

**Requirement:** Use CSS media queries for layout changes

**Breakpoints:**
```css
/* Full layout */
@media (min-width: 700px) {
    .control-btn { /* full size */ }
}

/* Compact layout */
@media (min-width: 600px) and (max-width: 699px) {
    .control-btn {
        padding: var(--spacing-sm) var(--spacing-md);
        min-width: 80px;
    }
    .btn-label {
        font-size: 11px;
    }
}
```

## Critical Constraints

### Technical Constraints

1. **Tauri Configuration:**
   - Minimum size set in `tauri.conf.json`
   - Window resize events forwarded to webview
   - No maximum size (let OS handle)

2. **Performance:**
   - Resize calculations must be fast
   - Avoid layout thrashing (batch DOM reads/writes)
   - Use CSS for animations during resize

3. **Cross-Platform:**
   - macOS and Linux may handle resize differently
   - Test drag resize vs. maximize/restore
   - Window management varies by platform

### User Experience Constraints

1. **Usability:**
   - UI must remain usable at all supported sizes
   - No overlapping elements
   - All controls remain accessible

2. **Visual Quality:**
   - No stretched or distorted elements
   - Proportional spacing
   - Text remains readable

3. **Smooth Transitions:**
   - Layout changes during resize should be smooth
   - No jarring jumps or flashes

## Integration Points

### Tauri Config (`src-tauri/tauri.conf.json`)

**Changes Required:**
```json
{
    "windows": [
        {
            "width": 800,
            "height": 700,
            "minWidth": 600,
            "minHeight": 500,
            "resizable": true
        }
    ]
}
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
/* Responsive image container */
.image-container {
    width: var(--container-width, 512px);
    height: var(--container-height, 512px);
    max-width: calc(100vw - var(--spacing-lg) * 2);
    max-height: calc(100vh - 200px);
    transition: width 200ms ease-out, height 200ms ease-out;
}

/* Compact layout for narrow windows */
@media (max-width: 699px) {
    .control-btn {
        padding: var(--spacing-sm) var(--spacing-md);
        min-width: 70px;
    }

    .btn-label {
        font-size: 11px;
    }

    .status-bar {
        padding: var(--spacing-xs) var(--spacing-md);
    }

    .prompt-input {
        min-width: 150px;
    }
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Responsive container sizing
function updateContainerSize(aspectRatio) {
    const viewer = document.querySelector('.viewer');
    if (!viewer) return;

    const padding = 48; // 24px on each side
    const availableWidth = viewer.clientWidth - padding;
    const availableHeight = viewer.clientHeight - padding;

    let width, height;

    switch (aspectRatio) {
        case '16:9':
            width = Math.min(availableWidth, availableHeight * 16 / 9);
            height = width * 9 / 16;
            break;
        case '9:16':
            height = Math.min(availableHeight, availableWidth * 16 / 9);
            width = height * 9 / 16;
            break;
        default: // '1:1'
            const size = Math.min(availableWidth, availableHeight);
            width = height = size;
    }

    // Enforce minimum
    width = Math.max(width, 256);
    height = Math.max(height, 256);

    document.documentElement.style.setProperty('--container-width', `${width}px`);
    document.documentElement.style.setProperty('--container-height', `${height}px`);
}

// Resize handler
function handleResize() {
    updateContainerSize(state.aspectRatio);
}

// Debounced resize listener
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(handleResize, 100);
});

// Initial sizing
handleResize();
```

## Out of Scope

- Mobile/touch layouts
- Split-screen or multi-window
- Remembering window size across sessions
- Maximum window size constraints
- Full-screen mode
- Picture-in-picture

## Success Criteria

### Functional Acceptance

1. **Minimum Size:**
   - Window cannot resize below 600x500
   - Layout remains usable at minimum size

2. **Scaling:**
   - Image container scales with window
   - Controls adapt to available space

3. **Breakpoints:**
   - Compact layout at narrow widths
   - Full layout at wider widths

4. **Resize Behavior:**
   - Smooth transitions during resize
   - No layout breaking or overflow

### Non-Functional Acceptance

1. **Performance:** No lag during resize
2. **Cross-Platform:** Works on macOS and Linux
3. **Usability:** All features accessible at all sizes

## Implementation Notes

**Estimated Effort:** Medium (2-3 hours)

**Testing Requirements:**
- Resize to various dimensions
- Test at minimum size
- Test rapid resize (drag)
- Test maximize/restore
- Test on both platforms

**Dependencies:**
- Tauri config changes for minWidth/minHeight
- May need to coordinate with Dynamic Image Container Sizing spec

**Rollout Plan:**
1. Update Tauri config with min sizes
2. Add CSS media queries for breakpoints
3. Implement container resize calculation
4. Add resize event listener
5. Test at various sizes
6. Test on macOS and Linux

**Risk Assessment:**
- Low risk: Standard responsive CSS techniques
- Medium complexity: Coordinate with other UI specs
- Platform differences: May need platform-specific testing
