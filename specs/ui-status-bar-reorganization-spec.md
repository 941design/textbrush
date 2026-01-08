# Feature Specification: Status Bar Reorganization

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The status bar currently contains three distinct concerns:

1. **Configuration controls** (prompt input, aspect ratio selection)
2. **Status information** (buffer count, seed display)
3. **UI controls** (theme toggle)

These are crammed into a single horizontal bar, creating visual density and potential confusion about what's editable vs. informational. On narrower windows, the layout becomes cramped.

## Core Functionality

Reorganize the status bar into logical groups, optionally moving configuration controls to a collapsible panel or dedicated section. Maintain quick access to settings while improving visual hierarchy.

## Functional Requirements

### FR1: Separate Configuration from Status

**Requirement:** Visual distinction between editable controls and read-only status

**Option A - Collapsible Settings Panel:**
- Settings icon (gear) in status bar
- Clicking reveals dropdown/panel with prompt and aspect ratio
- Panel closes on outside click or Esc
- Settings remembered when panel closed

**Option B - Top Configuration Bar:**
- Move prompt and aspect ratio to a thin bar above the viewer
- Status bar contains only status info and theme toggle
- Always visible, no collapse

**Option C - Overlay Settings:**
- Settings accessible via keyboard shortcut (e.g., Cmd+,)
- Modal overlay for configuration
- Status bar is purely informational

### FR2: Status Bar Simplification

**Requirement:** Status bar shows only runtime information

**Retained Elements:**
- Position indicator (if implemented): `[2/5]`
- Buffer indicator: dots + count
- Seed display: current seed
- Theme toggle: light/dark switch

**Removed Elements (moved elsewhere):**
- Prompt input
- Aspect ratio radio buttons

### FR3: Settings Persistence Indicator

**Requirement:** Show when settings differ from initial launch args

**Behavior:**
- If user changed prompt or aspect ratio in-session, show indicator
- Small badge or icon change on settings button
- Indicates pending config changes

### FR4: Responsive Layout

**Requirement:** Layout adapts to window width

**Behavior:**
- On narrow windows, elements stack or truncate gracefully
- Priority order for truncation:
  1. Seed display (can abbreviate)
  2. Buffer dots (can reduce to text only)
  3. Position indicator (always visible)
- Minimum width before stacking: 600px

### FR5: Quick Access Shortcuts

**Requirement:** Settings accessible without panel interaction

**Behavior:**
- Prompt: Cmd+P or / to focus prompt input
- Aspect Ratio: Cmd+1/2/3 for 1:1/16:9/9:16
- Shortcuts work even when panel is closed
- Panel opens automatically when shortcut used

## Critical Constraints

### Technical Constraints

1. **State Preservation:**
   - Config changes must be sent to backend
   - Panel state (open/closed) persisted to localStorage
   - No data loss on panel close

2. **Animation Performance:**
   - Panel open/close must be smooth (60fps)
   - Use CSS transforms, not height animation
   - No layout thrashing during transitions

3. **Focus Management:**
   - Trap focus in panel when open (accessibility)
   - Return focus to trigger element on close
   - Esc closes panel

### User Experience Constraints

1. **Discoverability:**
   - Settings must remain findable
   - Icon should be recognizable (gear/cog)
   - Tooltip on hover explains functionality

2. **Quick Access:**
   - Users who frequently change settings shouldn't be slowed down
   - Consider keeping prompt visible if frequently edited
   - Balance simplicity with power-user efficiency

3. **Consistency:**
   - Collapsible pattern should match platform conventions
   - Animation timing consistent with rest of UI

## Design Options Analysis

### Option A: Collapsible Panel

**Pros:**
- Maximum space efficiency
- Clean status bar when collapsed
- Settings grouped logically

**Cons:**
- Extra click to access settings
- May feel hidden to new users
- Animation complexity

### Option B: Top Configuration Bar

**Pros:**
- Always visible settings
- Clear separation of concerns
- No animation needed

**Cons:**
- Takes vertical space from viewer
- May feel cluttered with two bars
- Less flexible for future additions

### Option C: Overlay Settings

**Pros:**
- Maximum viewer space
- Modal pattern is familiar
- Can include more settings in future

**Cons:**
- Most clicks to access
- Interrupts workflow for simple changes
- May feel heavy for quick tweaks

**Recommendation:** Option A (Collapsible Panel) for best balance of efficiency and cleanliness. Option B is simpler to implement if panel complexity is a concern.

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes for Option A:**
```html
<section class="status-bar">
    <button class="settings-toggle" id="settings-toggle" aria-expanded="false">
        <span class="settings-icon">⚙</span>
    </button>

    <div class="settings-panel hidden" id="settings-panel" role="dialog" aria-label="Settings">
        <div class="prompt-control">
            <label for="prompt-input" class="control-label">Prompt:</label>
            <input type="text" class="prompt-input" id="prompt-input" ... />
        </div>
        <div class="aspect-ratio-control">
            <!-- aspect ratio radios -->
        </div>
    </div>

    <div class="status-info">
        <div class="position-indicator" id="position-indicator">[—]</div>
        <div class="buffer-indicator" id="buffer-indicator">...</div>
        <div class="seed-display" id="seed-display">seed: —</div>
    </div>

    <button class="theme-toggle" id="theme-toggle">...</button>
</section>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.settings-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: 6px;
    cursor: pointer;
    transition: all var(--transition-fast);
}

.settings-panel {
    position: absolute;
    bottom: 100%;
    left: 0;
    width: 100%;
    padding: var(--spacing-md);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: 8px 8px 0 0;
    transform: translateY(100%);
    opacity: 0;
    pointer-events: none;
    transition: transform 200ms ease-out, opacity 200ms ease-out;
}

.settings-panel.visible {
    transform: translateY(0);
    opacity: 1;
    pointer-events: auto;
}

.status-info {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    flex: 1;
    justify-content: flex-end;
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Settings panel toggle
function toggleSettingsPanel() {
    const panel = elements.settingsPanel;
    const toggle = elements.settingsToggle;
    const isOpen = !panel.classList.contains('hidden');

    if (isOpen) {
        panel.classList.add('hidden');
        panel.classList.remove('visible');
        toggle.setAttribute('aria-expanded', 'false');
    } else {
        panel.classList.remove('hidden');
        // Trigger reflow for animation
        panel.offsetHeight;
        panel.classList.add('visible');
        toggle.setAttribute('aria-expanded', 'true');
        elements.promptInput?.focus();
    }
}

// Close on outside click
document.addEventListener('click', (e) => {
    if (elements.settingsPanel?.classList.contains('visible')) {
        if (!elements.settingsPanel.contains(e.target) &&
            !elements.settingsToggle.contains(e.target)) {
            toggleSettingsPanel();
        }
    }
});

// Keyboard shortcuts for quick access
document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !e.target.matches('input')) {
        e.preventDefault();
        if (!elements.settingsPanel.classList.contains('visible')) {
            toggleSettingsPanel();
        }
        elements.promptInput?.focus();
    }
});
```

## Out of Scope

- Additional settings (buffer size, output format, etc.)
- Preset configurations
- Settings import/export
- Undo/redo for setting changes
- Settings sync across sessions (beyond localStorage)

## Success Criteria

### Functional Acceptance

1. **Settings Panel Toggle:**
   - Gear icon opens/closes settings panel
   - Panel animates smoothly
   - Focus trapped in panel when open

2. **Status Bar Simplified:**
   - Only status info visible when panel closed
   - Clean, minimal appearance

3. **Quick Access:**
   - Keyboard shortcuts work for settings
   - Panel opens automatically when needed

4. **Responsive:**
   - Layout adapts to narrow windows
   - No horizontal scrolling required

### Non-Functional Acceptance

1. **Animation:** Panel open/close at 60fps
2. **Accessibility:** Keyboard navigable, screen reader compatible
3. **Persistence:** Panel state saved to localStorage

## Implementation Notes

**Estimated Effort:** Medium (3-4 hours)

**Testing Requirements:**
- Panel toggle functionality
- Keyboard shortcuts
- Focus management (accessibility)
- Responsive layout at various widths
- Settings persistence

**Dependencies:**
- None (refactors existing elements)

**Rollout Plan:**
1. Create settings panel HTML structure
2. Add CSS for panel positioning and animation
3. Implement toggle logic in JavaScript
4. Add keyboard shortcuts
5. Test accessibility (focus trap, ARIA)
6. Test responsive behavior
7. Document new shortcuts in help

**Risk Assessment:**
- Low risk: Pure UI refactor, no backend changes
- Medium complexity: Animation and focus management
- User impact: May require adjustment for existing users

**Fallback:**
If collapsible panel proves too complex, fall back to Option B (separate top bar) which is simpler to implement.
