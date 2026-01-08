# Feature Specification: Keyboard Shortcuts Help

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The application has several keyboard shortcuts:
- Space/→ : Navigate forward (skip)
- ← : Navigate backward
- Enter : Accept
- Esc : Abort
- Cmd/Ctrl+Delete : Delete current image

These shortcuts are shown in small text (10px) on the control buttons, but:
1. **Not comprehensive** - Not all shortcuts visible at a glance
2. **Hard to read** - Small font size
3. **No discoverability** - New users may not notice
4. **Platform-specific** - Cmd vs Ctrl not clearly indicated

Power users need quick reference; new users need discoverability.

## Core Functionality

Add a keyboard shortcuts help overlay accessible via the `?` key or a help icon. The overlay shows all available shortcuts in a clear, organized format.

## Functional Requirements

### FR1: Help Overlay Trigger

**Requirement:** Open help overlay via keyboard or button

**Triggers:**
- Press `?` key (Shift+/) when not in input field
- Click help icon button (if added to UI)
- Press `F1` key (common help shortcut)

**Close Triggers:**
- Press `Esc`
- Press `?` again (toggle)
- Click outside overlay
- Click close button

### FR2: Overlay Content

**Requirement:** Show all keyboard shortcuts in organized layout

**Content Structure:**
```
Keyboard Shortcuts
─────────────────

Navigation
  →  or  Space     Next image
  ←                Previous image

Actions
  Enter            Accept all images
  Esc              Abort and exit
  Cmd+Delete       Delete current image

View
  ?                Toggle this help
```

### FR3: Platform-Aware Display

**Requirement:** Show platform-appropriate modifier keys

**Behavior:**
- macOS: Show "Cmd" for Command key
- Linux: Show "Ctrl" for Control key
- Detect platform and adjust display
- Use standard key symbols where appropriate (⌘, ⌃, ⌫)

**macOS Symbols:**
- ⌘ Command
- ⌥ Option
- ⌃ Control
- ⇧ Shift
- ⌫ Delete

**Linux/Other:**
- Ctrl
- Alt
- Shift
- Delete

### FR4: Visual Design

**Requirement:** Overlay matches application design system

**Design:**
- Semi-transparent dark background overlay
- Centered content card
- Consistent typography with app
- Keyboard key styling (rounded boxes for keys)
- Subtle shadow for depth

**Animation:**
- Fade in (150ms)
- Fade out (100ms)
- No jarring appearance

### FR5: Accessibility

**Requirement:** Help overlay is fully accessible

**Requirements:**
- Focus trapped in overlay when open
- Screen reader announces overlay
- All shortcuts listed with descriptions
- Esc closes overlay
- Focus returns to previous element on close

**ARIA:**
```html
<div class="help-overlay" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <h2 id="help-title">Keyboard Shortcuts</h2>
    ...
</div>
```

### FR6: Help Icon Button (Optional)

**Requirement:** Visual trigger for help overlay

**Design:**
- Small `?` icon in status bar or corner
- Tooltip: "Keyboard shortcuts (?)"
- Minimal footprint

**Placement Options:**
1. Status bar, far right (after theme toggle)
2. Bottom-right corner, floating
3. Within controls section

## Critical Constraints

### Technical Constraints

1. **Keyboard Handling:**
   - `?` must not trigger in text inputs
   - Must not conflict with other shortcuts
   - Must work regardless of focus

2. **Focus Management:**
   - Focus trap in overlay
   - Return focus on close
   - No focus loss edge cases

3. **Platform Detection:**
   - Reliable platform detection
   - Fallback for unknown platforms
   - Consistent with other platform-aware features

### User Experience Constraints

1. **Non-Intrusive:**
   - Overlay should not interfere with workflow
   - Quick to dismiss
   - Remembers user preference (don't show again - optional)

2. **Discoverability:**
   - New users should find help easily
   - Not hidden or obscure
   - Natural trigger (`?` is common)

3. **Completeness:**
   - All shortcuts documented
   - No outdated information
   - Easy to update when shortcuts change

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<!-- Help overlay (hidden by default) -->
<div class="help-overlay hidden" id="help-overlay" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <div class="help-card">
        <button class="help-close" id="help-close" aria-label="Close help">&times;</button>
        <h2 id="help-title">Keyboard Shortcuts</h2>

        <div class="help-section">
            <h3>Navigation</h3>
            <div class="shortcut-row">
                <span class="shortcut-keys"><kbd>→</kbd> or <kbd>Space</kbd></span>
                <span class="shortcut-desc">Next image</span>
            </div>
            <div class="shortcut-row">
                <span class="shortcut-keys"><kbd>←</kbd></span>
                <span class="shortcut-desc">Previous image</span>
            </div>
        </div>

        <div class="help-section">
            <h3>Actions</h3>
            <div class="shortcut-row">
                <span class="shortcut-keys"><kbd>Enter</kbd></span>
                <span class="shortcut-desc">Accept all retained images</span>
            </div>
            <div class="shortcut-row">
                <span class="shortcut-keys"><kbd>Esc</kbd></span>
                <span class="shortcut-desc">Abort and exit</span>
            </div>
            <div class="shortcut-row">
                <span class="shortcut-keys"><kbd id="mod-key">Cmd</kbd>+<kbd>Delete</kbd></span>
                <span class="shortcut-desc">Remove current image</span>
            </div>
        </div>

        <div class="help-section">
            <h3>View</h3>
            <div class="shortcut-row">
                <span class="shortcut-keys"><kbd>?</kbd></span>
                <span class="shortcut-desc">Toggle this help</span>
            </div>
        </div>
    </div>
</div>

<!-- Optional: Help button in status bar -->
<button class="help-toggle" id="help-toggle" type="button" title="Keyboard shortcuts (?)" aria-label="Show keyboard shortcuts">
    <span aria-hidden="true">?</span>
</button>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
/* Help overlay backdrop */
.help-overlay {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.7);
    z-index: 1000;
    opacity: 0;
    pointer-events: none;
    transition: opacity 150ms ease;
}

.help-overlay.visible {
    opacity: 1;
    pointer-events: auto;
}

/* Help card */
.help-card {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: var(--spacing-xl);
    max-width: 400px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    position: relative;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.help-close {
    position: absolute;
    top: var(--spacing-md);
    right: var(--spacing-md);
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 24px;
    cursor: pointer;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all var(--transition-fast);
}

.help-close:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}

.help-card h2 {
    margin: 0 0 var(--spacing-lg);
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
}

.help-section {
    margin-bottom: var(--spacing-lg);
}

.help-section:last-child {
    margin-bottom: 0;
}

.help-section h3 {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    margin: 0 0 var(--spacing-sm);
}

.shortcut-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-xs) 0;
}

.shortcut-keys {
    display: flex;
    gap: 4px;
    align-items: center;
}

.shortcut-desc {
    color: var(--text-secondary);
    font-size: 13px;
}

/* Keyboard key styling */
kbd {
    display: inline-block;
    padding: 2px 6px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-primary);
    box-shadow: 0 1px 0 var(--border-subtle);
}

/* Help button */
.help-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: transparent;
    border: 1px solid var(--border-subtle);
    border-radius: 50%;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    transition: all var(--transition-fast);
}

.help-toggle:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
    border-color: var(--border-focus);
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Add to elements cache
elements.helpOverlay = document.getElementById('help-overlay');
elements.helpClose = document.getElementById('help-close');
elements.helpToggle = document.getElementById('help-toggle');
elements.modKey = document.getElementById('mod-key');

// Platform detection
function setupPlatformKeys() {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    if (elements.modKey) {
        elements.modKey.textContent = isMac ? '⌘' : 'Ctrl';
    }
}

// Toggle help overlay
function toggleHelp() {
    if (!elements.helpOverlay) return;

    const isVisible = elements.helpOverlay.classList.contains('visible');

    if (isVisible) {
        closeHelp();
    } else {
        openHelp();
    }
}

function openHelp() {
    if (!elements.helpOverlay) return;

    elements.helpOverlay.classList.remove('hidden');
    // Trigger reflow for animation
    elements.helpOverlay.offsetHeight;
    elements.helpOverlay.classList.add('visible');

    // Trap focus
    elements.helpClose?.focus();
}

function closeHelp() {
    if (!elements.helpOverlay) return;

    elements.helpOverlay.classList.remove('visible');
    setTimeout(() => {
        elements.helpOverlay.classList.add('hidden');
    }, 150);
}

// Event listeners
function setupHelpListeners() {
    // Keyboard trigger
    document.addEventListener('keydown', (e) => {
        // Don't trigger in input fields
        if (e.target.tagName === 'INPUT') return;

        if (e.key === '?' || e.key === 'F1') {
            e.preventDefault();
            toggleHelp();
        }

        // Close on Esc when help is open
        if (e.key === 'Escape' && elements.helpOverlay?.classList.contains('visible')) {
            e.preventDefault();
            e.stopPropagation();
            closeHelp();
        }
    });

    // Close button
    elements.helpClose?.addEventListener('click', closeHelp);

    // Help toggle button
    elements.helpToggle?.addEventListener('click', toggleHelp);

    // Close on backdrop click
    elements.helpOverlay?.addEventListener('click', (e) => {
        if (e.target === elements.helpOverlay) {
            closeHelp();
        }
    });
}

// Initialize
setupPlatformKeys();
setupHelpListeners();
```

## Out of Scope

- Customizable shortcuts
- Shortcut conflicts detection
- Searchable shortcuts
- Context-sensitive shortcuts (different shortcuts in different modes)
- Printing shortcut reference
- Video tutorials or extended help

## Success Criteria

### Functional Acceptance

1. **Trigger:**
   - `?` key opens overlay
   - `F1` opens overlay
   - Help button opens overlay

2. **Close:**
   - `Esc` closes overlay
   - `?` toggles (closes if open)
   - Click outside closes
   - Close button works

3. **Content:**
   - All shortcuts listed
   - Platform-appropriate modifier keys
   - Descriptions accurate

4. **Accessibility:**
   - Focus trapped in overlay
   - Screen reader announces content
   - Focus returns on close

### Non-Functional Acceptance

1. **Animation:** Smooth fade in/out
2. **Styling:** Consistent with design system
3. **Maintainability:** Easy to update shortcuts list

## Implementation Notes

**Estimated Effort:** Small (1-2 hours)

**Testing Requirements:**
- All triggers work
- All close methods work
- Focus management correct
- Platform detection correct
- Screen reader compatibility

**Dependencies:**
- None (pure HTML/CSS/JS)

**Rollout Plan:**
1. Add help overlay HTML
2. Add CSS styling
3. Implement JavaScript handlers
4. Add platform detection
5. Test accessibility
6. Add help button (optional)
