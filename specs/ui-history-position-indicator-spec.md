# Feature Specification: History Position Indicator

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The spec (section 4.4) states: "Position indicator: Shows current position in history (e.g., '[2/5]')". However, this indicator is not currently implemented in the UI. Users navigating through image history with arrow keys have no visual feedback about:

- How many images they have viewed
- Where they are in the history
- Whether there are more images ahead or behind

This creates confusion during the review workflow, especially when users have viewed many images and want to return to a specific one.

## Core Functionality

Display a persistent position indicator showing the current image index and total history count. The indicator updates in real-time as users navigate through their image history.

## Functional Requirements

### FR1: Position Display Format

**Requirement:** Show current position in "[current/total]" format

**Behavior:**
- Display format: `[N/M]` where N = current position, M = total images
- Position is 1-indexed (first image is 1, not 0)
- Updates immediately on navigation
- Shows `[—]` when no images are available

**Examples:**
- First image of five: `[1/5]`
- Third image of five: `[3/5]`
- At loading placeholder (waiting for next): `[5/5+]` or `[—]`
- No images yet: `[—]`

### FR2: Indicator Placement

**Requirement:** Position indicator in status bar, left side

**Behavior:**
- Display between buffer indicator and seed display
- Monospace font for alignment consistency
- Subtle styling (muted text color)
- Fixed width to prevent layout shifts as numbers change

**Location in DOM:**
```html
<div class="status-right">
    <div class="position-indicator" id="position-indicator">[—]</div>
    <div class="buffer-indicator">...</div>
    <div class="seed-display">...</div>
</div>
```

### FR3: Real-Time Updates

**Requirement:** Indicator updates on all navigation events

**Update Triggers:**
- New image received from backend (total increases)
- User navigates forward (ArrowRight/Space)
- User navigates backward (ArrowLeft)
- User deletes current image (total decreases, position may change)
- User reaches loading placeholder

**State Transitions:**
```
Initial state:      [—]
First image:        [1/1]
Second image:       [1/2] (if viewing first) or [2/2] (if advanced)
Navigate back:      [N-1/M]
Navigate forward:   [N+1/M]
Delete image:       [N/M-1] or [N-1/M-1] (if deleted was last)
```

### FR4: Waiting State Indication

**Requirement:** Indicate when user is waiting for next image

**Behavior:**
- When at end of history and waiting for generation: `[N/N+]`
- The `+` suffix indicates "waiting for more"
- Returns to normal format when new image arrives

**Alternative:** Show `[N/N]` with pulsing animation on the indicator

### FR5: Accessibility

**Requirement:** Position indicator is accessible to screen readers

**Behavior:**
- Use `role="status"` for live updates
- Include `aria-live="polite"` for non-intrusive announcements
- Provide `aria-label` with full description

**Implementation:**
```html
<div
    class="position-indicator"
    id="position-indicator"
    role="status"
    aria-live="polite"
    aria-label="Image 2 of 5"
>[2/5]</div>
```

## Critical Constraints

### Technical Constraints

1. **State Synchronization:**
   - Must accurately reflect `state.historyIndex` and `state.imageHistory.length`
   - Update atomically with navigation actions
   - No stale state after rapid navigation

2. **Performance:**
   - DOM updates should be minimal (only text content)
   - No layout thrashing from width changes
   - Use fixed-width font to prevent reflow

3. **Integration with HistoryManager:**
   - Indicator updates should be triggered by HistoryManager
   - Single source of truth for position data
   - No duplicate state tracking

### User Experience Constraints

1. **Visibility:**
   - Indicator must be visible but not prominent
   - Should not distract from primary image review task
   - Consistent with existing status bar styling

2. **Accuracy:**
   - Position must always be accurate
   - No off-by-one errors
   - Total must match actual history length

3. **Responsiveness:**
   - Update within same frame as navigation
   - No perceived delay between action and indicator change

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<div class="status-right">
    <div class="position-indicator" id="position-indicator"
         role="status" aria-live="polite" aria-label="No images">
        [—]
    </div>
    <div class="buffer-indicator" id="buffer-indicator">
        <!-- existing content -->
    </div>
    <div class="seed-display" id="seed-display">
        seed: —
    </div>
</div>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.position-indicator {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 11px;
    min-width: 4em;
    text-align: center;
}

.position-indicator.waiting::after {
    content: '';
    animation: pulse 1s ease infinite;
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Add to elements cache
elements.positionIndicator = document.getElementById('position-indicator');

// Add update function
function updatePositionIndicator() {
    if (!elements.positionIndicator) return;

    const { imageHistory, historyIndex, waitingForNext } = state;
    const total = imageHistory.length;
    const current = historyIndex + 1; // 1-indexed

    let text, label;

    if (total === 0) {
        text = '[—]';
        label = 'No images';
    } else if (waitingForNext) {
        text = `[${total}/${total}+]`;
        label = `Viewing image ${total} of ${total}, waiting for next`;
    } else {
        text = `[${current}/${total}]`;
        label = `Image ${current} of ${total}`;
    }

    elements.positionIndicator.textContent = text;
    elements.positionIndicator.setAttribute('aria-label', label);
    elements.positionIndicator.classList.toggle('waiting', waitingForNext);
}

// Call in: handleImageReady, previous, skip, deleteCurrentImage
```

### HistoryManager (`src-tauri/ui/history-manager.js`)

**Changes Required:**
- Export position data or provide getter
- Call position update after navigation functions
- Alternatively, emit events that main.js listens to

## Out of Scope

- Clickable position indicator for direct navigation
- Thumbnail strip or filmstrip view
- Image numbering/naming in indicator
- Persistent position across sessions
- Jump-to-position dialog

## Success Criteria

### Functional Acceptance

1. **Initial State:**
   - Indicator shows `[—]` before first image

2. **First Image:**
   - Indicator updates to `[1/1]` when first image arrives

3. **Navigation Forward:**
   - Pressing → or Space increments position correctly
   - New images increment total

4. **Navigation Backward:**
   - Pressing ← decrements position correctly
   - Total remains unchanged

5. **Deletion:**
   - Total decreases by 1
   - Position adjusts appropriately

6. **Waiting State:**
   - Shows `+` suffix when waiting for generation

### Non-Functional Acceptance

1. **Performance:** No measurable impact on navigation speed
2. **Accessibility:** Screen reader announces position changes
3. **Styling:** Consistent with existing status bar elements

## Implementation Notes

**Estimated Effort:** Small (1-2 hours)

**Testing Requirements:**
- Unit tests for position calculation logic
- Integration tests for all navigation scenarios
- Accessibility testing with screen reader
- Edge cases: empty history, single image, rapid navigation

**Dependencies:**
- None (uses existing state)

**Rollout Plan:**
1. Add HTML element to index.html
2. Add CSS styles to main.css
3. Add updatePositionIndicator function to main.js
4. Integrate calls into navigation and message handlers
5. Test all navigation scenarios
6. Verify accessibility with VoiceOver/NVDA
