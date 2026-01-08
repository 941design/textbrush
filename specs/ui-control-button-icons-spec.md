# Feature Specification: Control Button Icons

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The control buttons currently use text emoji characters for icons:
- Abort: ⊘ (circled division slash)
- Navigate: ↔ (left-right arrow)
- Accept: ✓ (check mark)

These emoji characters have several issues:
1. **Inconsistent rendering** across platforms and fonts
2. **Limited styling** - color and size are constrained
3. **Accessibility concerns** - may not render in high contrast modes
4. **Professional appearance** - emoji can look informal

Proper SVG icons would provide consistent, scalable, styleable graphics.

## Core Functionality

Replace emoji button icons with inline SVG icons that can be styled with CSS, ensuring consistent appearance across platforms and better integration with the design system.

## Functional Requirements

### FR1: SVG Icon Set

**Requirement:** Create or source SVG icons for all control buttons

**Icons Needed:**
| Button | Current | Proposed Icon |
|--------|---------|---------------|
| Abort | ⊘ | X in circle or stop sign |
| Navigate | ↔ | Left-right arrows or shuffle |
| Accept | ✓ | Checkmark in circle |
| Delete | 🗑 | Trash can outline |
| Theme | ◐ | Sun/moon combination |

**Icon Style:**
- Outline style (not filled) for consistency
- 24x24px viewBox
- Single path for simplicity
- currentColor for fill (CSS-controllable)

### FR2: CSS Styling Integration

**Requirement:** Icons styled via CSS custom properties

**Behavior:**
- Icon color inherits from button text color
- Icon size controlled by CSS (default 20px)
- Hover states can change icon color
- Transitions apply to icon color changes

**Implementation:**
```css
.btn-icon svg {
    width: 20px;
    height: 20px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}

.btn-accept:hover .btn-icon svg {
    stroke: var(--accent-success);
}
```

### FR3: Inline SVG vs. External

**Requirement:** Use inline SVG for simplicity and styling control

**Rationale:**
- No additional HTTP requests
- Full CSS control over colors
- No external dependencies
- Easy to maintain in HTML

**Alternative Considered:**
- Icon font (Font Awesome, etc.) - adds dependency, limited styling
- External SVG files - requires sprite management, CORS considerations
- CSS icons (using borders/pseudo-elements) - complex, limited shapes

### FR4: Accessibility

**Requirement:** Icons remain accessible

**Behavior:**
- SVG has `aria-hidden="true"` (label provides meaning)
- Button retains text label for screen readers
- Icons don't replace text labels

**Implementation:**
```html
<button class="control-btn btn-accept">
    <span class="btn-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24">
            <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
    </span>
    <span class="btn-label">Accept</span>
    <span class="btn-shortcut">Enter</span>
</button>
```

### FR5: Reduced Motion Support

**Requirement:** Respect prefers-reduced-motion

**Behavior:**
- Icon color transitions disabled when user prefers reduced motion
- No animations on icons
- Static appearance maintained

**Implementation:**
```css
@media (prefers-reduced-motion: reduce) {
    .btn-icon svg {
        transition: none;
    }
}
```

## Critical Constraints

### Technical Constraints

1. **No External Dependencies:**
   - Icons must be inline or bundled
   - No icon font libraries
   - No runtime icon loading

2. **File Size:**
   - Keep SVG paths simple
   - Optimize SVG code (remove unnecessary attributes)
   - Total icon overhead < 5KB

3. **Browser Support:**
   - Inline SVG supported in all target browsers
   - currentColor works in all modern browsers
   - No IE11 considerations needed

### User Experience Constraints

1. **Recognition:**
   - Icons must be immediately recognizable
   - Follow common conventions (checkmark = success, X = cancel)
   - Consistent with platform idioms

2. **Size:**
   - Icons large enough to see clearly (minimum 16px)
   - Not so large they dominate the button
   - Proportional to button text

3. **Color:**
   - Sufficient contrast in both themes
   - Color changes on hover should be subtle
   - Disabled state clearly different

## Icon Specifications

### Abort Icon (X in Circle)
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="15" y1="9" x2="9" y2="15"></line>
    <line x1="9" y1="9" x2="15" y2="15"></line>
</svg>
```

### Navigate Icon (Arrows)
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="15 18 21 12 15 6"></polyline>
    <polyline points="9 6 3 12 9 18"></polyline>
</svg>
```

### Accept Icon (Checkmark)
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="20 6 9 17 4 12"></polyline>
</svg>
```

### Delete Icon (Trash)
```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="3 6 5 6 21 6"></polyline>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
</svg>
```

### Theme Icon (Sun/Moon)
```svg
<!-- Sun (light mode indicator) -->
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

<!-- Moon (dark mode indicator) -->
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
</svg>
```

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
Replace emoji spans with inline SVG in each button.

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.btn-icon {
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-icon svg {
    width: 20px;
    height: 20px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: stroke var(--transition-fast);
}

.control-btn:hover .btn-icon svg {
    stroke: var(--text-primary);
}

.btn-accept:hover .btn-icon svg {
    stroke: var(--accent-success);
}

.btn-abort:hover .btn-icon svg {
    stroke: var(--accent-danger);
}

.btn-delete:hover .btn-icon svg {
    stroke: var(--accent-warning);
}
```

### JavaScript

**No JavaScript changes required** - icons are purely presentational.

## Out of Scope

- Animated icons (morphing, spinning)
- Icon library integration
- Custom icon upload
- Icon size preferences
- Per-button icon customization

## Success Criteria

### Functional Acceptance

1. **Icon Rendering:**
   - All icons render consistently across platforms
   - Icons visible in both light and dark themes

2. **Hover States:**
   - Icon color changes on button hover
   - Transitions are smooth

3. **Accessibility:**
   - Screen readers ignore icons (aria-hidden)
   - Text labels remain for accessibility

4. **Theme Support:**
   - Icons adapt to light/dark theme
   - Sufficient contrast in both modes

### Non-Functional Acceptance

1. **Performance:** No measurable impact on load time
2. **Consistency:** Icons match across all supported platforms
3. **Maintainability:** Icons easy to update or replace

## Implementation Notes

**Estimated Effort:** Small (1-2 hours)

**Testing Requirements:**
- Visual testing on macOS and Linux
- Dark/light theme testing
- Hover state verification
- Screen reader testing

**Dependencies:**
- None (uses inline SVG)

**Icon Sources:**
- Icons based on Feather Icons (MIT license)
- Can be customized as needed
- No attribution required

**Rollout Plan:**
1. Create SVG markup for each icon
2. Update index.html to use inline SVG
3. Add CSS for SVG styling
4. Test on all platforms
5. Verify accessibility
6. Remove old emoji references

**Future Enhancements (Not in Scope):**
- Icon animation on click
- Loading spinner icon for async operations
- Custom icon theme packs
