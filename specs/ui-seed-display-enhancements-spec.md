# Feature Specification: Seed Display Enhancements

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

The current seed display shows "Seed: —" when no image is displayed and "Seed: 12345" when an image is shown. While functional, there are opportunities for improvement:

1. **No interaction** - Users cannot copy the seed to clipboard
2. **Always visible** - Shows placeholder even when not meaningful
3. **No context** - Users may not understand why seed matters
4. **Wasted space** - Display takes space when empty

Seeds are important for reproducibility—users may want to regenerate the same image later or share the seed with others.

## Core Functionality

Enhance the seed display with copy-to-clipboard functionality and improved visual states. Make the seed actionable and more contextually meaningful.

## Functional Requirements

### FR1: Click-to-Copy Seed

**Requirement:** Clicking seed value copies it to clipboard

**Behavior:**
- Entire seed display is clickable when seed is available
- Click copies seed value (number only) to clipboard
- Visual feedback confirms copy action
- Not clickable when no seed (placeholder state)

**Feedback:**
- Brief "Copied!" tooltip or text replacement
- Subtle animation (flash or checkmark)
- Feedback disappears after 1.5 seconds

### FR2: Hover State

**Requirement:** Visual indication that seed is interactive

**Behavior:**
- Cursor changes to pointer when hoverable
- Subtle background highlight on hover
- Tooltip appears: "Click to copy seed"
- No hover effect when no seed available

### FR3: Visual States

**Requirement:** Different appearances for different states

**States:**
- **No seed:** "—" grayed out, not interactive
- **Has seed:** "12345" normal color, interactive
- **Copied:** "Copied!" or checkmark, brief green highlight
- **Generating:** Pulsing or animated state (optional)

### FR4: Keyboard Accessibility

**Requirement:** Seed copyable via keyboard

**Behavior:**
- Seed display is focusable (tabindex="0")
- Enter or Space triggers copy
- Focus ring visible
- Screen reader announces "Seed 12345, button, click to copy"

### FR5: Tooltip with Full Context

**Requirement:** Show helpful tooltip on hover

**Tooltip Content:**
- Normal state: "Click to copy seed for reproducibility"
- After copy: "Seed copied to clipboard!"
- No seed: No tooltip (not interactive)

## Critical Constraints

### Technical Constraints

1. **Clipboard API:**
   - Use `navigator.clipboard.writeText()` for modern browsers
   - Handle permission errors gracefully
   - No fallback to deprecated `execCommand` needed (Tauri webview supports Clipboard API)

2. **Focus Management:**
   - Must not interfere with main keyboard navigation
   - Tab order should be logical
   - Copying should not move focus

3. **State Synchronization:**
   - Copy action must use current seed value
   - Handle rapid clicking (debounce or ignore)
   - State must be accurate during navigation

### User Experience Constraints

1. **Discoverability:**
   - Click affordance should be clear but subtle
   - Don't make it look like a primary action
   - Maintain consistency with status bar styling

2. **Feedback Clarity:**
   - Copy confirmation must be noticeable
   - Feedback duration should be sufficient to see
   - No confusion about what was copied

3. **Non-Intrusive:**
   - Feature should not distract from main workflow
   - Optional/ignorable for users who don't need it
   - No accidental triggers

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<button
    class="seed-display"
    id="seed-display"
    type="button"
    title="Click to copy seed"
    aria-label="Seed, click to copy"
    disabled
>
    <span class="seed-label">Seed:</span>
    <span class="seed-value" id="seed-value">—</span>
</button>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.seed-display {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 11px;
    cursor: default;
    transition: all var(--transition-fast);
}

.seed-display:not(:disabled) {
    cursor: pointer;
}

.seed-display:not(:disabled):hover {
    background: var(--bg-secondary);
    border-color: var(--border-subtle);
    color: var(--text-secondary);
}

.seed-display:not(:disabled):active {
    transform: scale(0.98);
}

.seed-display:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}

.seed-display.copied {
    border-color: var(--accent-success);
    color: var(--accent-success);
}

.seed-display.copied .seed-value::after {
    content: ' ✓';
}

.seed-label {
    color: var(--text-muted);
}

.seed-value {
    color: inherit;
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Add to elements cache
elements.seedDisplay = document.getElementById('seed-display');
elements.seedValue = document.getElementById('seed-value');

// Update seed display
function updateSeedDisplay(seed) {
    if (!elements.seedDisplay || !elements.seedValue) return;

    if (seed !== undefined && seed !== null) {
        elements.seedValue.textContent = seed;
        elements.seedDisplay.disabled = false;
        elements.seedDisplay.setAttribute('aria-label', `Seed ${seed}, click to copy`);
        elements.seedDisplay.title = 'Click to copy seed';
    } else {
        elements.seedValue.textContent = '—';
        elements.seedDisplay.disabled = true;
        elements.seedDisplay.setAttribute('aria-label', 'No seed');
        elements.seedDisplay.title = '';
    }
}

// Copy seed to clipboard
async function copySeed() {
    if (!state.currentSeed) return;

    try {
        await navigator.clipboard.writeText(String(state.currentSeed));
        showCopiedFeedback();
    } catch (err) {
        console.error('Failed to copy seed:', err);
    }
}

// Show copied feedback
function showCopiedFeedback() {
    if (!elements.seedDisplay) return;

    elements.seedDisplay.classList.add('copied');
    elements.seedDisplay.setAttribute('aria-label', 'Seed copied to clipboard');

    setTimeout(() => {
        elements.seedDisplay.classList.remove('copied');
        updateSeedDisplay(state.currentSeed);
    }, 1500);
}

// Event listeners
function setupSeedListeners() {
    if (elements.seedDisplay) {
        elements.seedDisplay.addEventListener('click', () => {
            if (!elements.seedDisplay.disabled) {
                copySeed();
            }
        });

        elements.seedDisplay.addEventListener('keydown', (e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !elements.seedDisplay.disabled) {
                e.preventDefault();
                copySeed();
            }
        });
    }
}
```

## Out of Scope

- Seed editing (change seed for regeneration)
- Seed history (list of previously used seeds)
- Seed sharing (generate shareable link)
- Seed search (find image by seed)
- Seed format options (hex, etc.)

## Success Criteria

### Functional Acceptance

1. **Copy Action:**
   - Clicking seed copies value to clipboard
   - Keyboard activation works (Enter/Space)
   - Clipboard contains correct seed value

2. **Visual Feedback:**
   - Hover state shows clickability
   - Copy confirmation visible for 1.5s
   - Disabled state clearly different

3. **Accessibility:**
   - Screen reader announces seed and action
   - Focus ring visible
   - Keyboard fully functional

4. **State Management:**
   - Disabled when no seed
   - Updates correctly during navigation
   - No stale data copied

### Non-Functional Acceptance

1. **Performance:** Copy action is instant
2. **Reliability:** Clipboard API works consistently
3. **Styling:** Consistent with status bar design

## Implementation Notes

**Estimated Effort:** Small (1 hour)

**Testing Requirements:**
- Copy functionality verification
- Keyboard accessibility
- Screen reader testing
- Visual state transitions
- Clipboard API error handling

**Dependencies:**
- None (uses standard APIs)

**Rollout Plan:**
1. Convert seed display to button element
2. Add CSS for interactive states
3. Implement copy functionality
4. Add copied feedback animation
5. Test accessibility
6. Update aria-labels appropriately

**Future Enhancements (Not in Scope):**
- "Use this seed" feature for regeneration
- Seed input field for custom seeds
- Seed favorites/bookmarks
