# Feature Specification: Empty State Placeholder

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

When the application launches, the image viewer area shows nothing until the first image arrives. This creates an awkward "blank" period where users may wonder if the application is working correctly. The current loading overlay with spinner appears, but the overall empty state could be more informative and visually polished.

Similarly, when all images are deleted from history, users see an undefined empty state.

## Core Functionality

Provide clear, informative placeholder states for:
1. **Initial launch** - Before first image is generated
2. **Empty history** - After all images are deleted
3. **Loading** - While waiting for generation (existing, but enhanced)

Each state should communicate what's happening and what the user can do.

## Functional Requirements

### FR1: Initial Launch State

**Requirement:** Show informative placeholder before first image

**Behavior:**
- Display centered message in viewer area
- Show prompt that will be used for generation
- Indicate that generation is starting
- No jarring transition when first image arrives

**Content:**
```
[Spinner]
Generating your first image...

Prompt: "A watercolor cat"
```

### FR2: Empty History State

**Requirement:** Clear message when all images have been deleted

**Behavior:**
- Displayed when `imageHistory.length === 0` and not waiting for generation
- Inform user that all images were removed
- Suggest next action (wait for new image or abort)

**Content:**
```
No images in selection

New images will appear as they're generated.
Press Esc to abort.
```

### FR3: Waiting for Next Image State

**Requirement:** Clear indication when at end of history, waiting for buffer

**Behavior:**
- Shown when user navigates past last image in history
- Buffer is empty, generation in progress
- Different from initial state (user has seen images before)

**Content:**
```
[Spinner]
Generating next image...

Press ← to go back
```

### FR4: Error State

**Requirement:** Clear error display when generation fails

**Behavior:**
- Shown when backend reports fatal error
- Clear error message
- Suggested action (retry or abort)

**Content:**
```
[Error Icon]
Generation failed

{error message}

Press Esc to exit.
```

### FR5: Visual Design

**Requirement:** Placeholder states are visually consistent

**Design Elements:**
- Centered in viewer area
- Muted colors (not distracting)
- Consistent typography with rest of UI
- Subtle background to differentiate from loaded image state
- Icon or illustration for visual interest (optional)

**Typography:**
- Primary message: 16px, text-primary
- Secondary message: 13px, text-secondary
- Prompt preview: 12px, font-mono, text-muted

## Critical Constraints

### Technical Constraints

1. **State Detection:**
   - Must accurately detect which state to show
   - No race conditions between states
   - Transitions should be smooth

2. **DOM Structure:**
   - Placeholder can reuse existing loading-overlay
   - Or be a separate element that shows/hides
   - Must not conflict with image display

3. **Performance:**
   - Placeholder rendering must be instant
   - No delay in transitioning to/from states
   - Minimal DOM manipulation

### User Experience Constraints

1. **Clarity:**
   - Each state must be immediately understandable
   - Users should know what to do in each state
   - No ambiguity about what's happening

2. **Non-Intrusive:**
   - Placeholders should be subtle, not alarming
   - Smooth transitions between states
   - No jarring visual changes

3. **Actionable:**
   - Each state includes guidance on next steps
   - Keyboard shortcuts mentioned where relevant

## State Machine

```
                    ┌─────────────┐
                    │   Initial   │
                    │   Launch    │
                    └──────┬──────┘
                           │ first image received
                           ▼
                    ┌─────────────┐
     ◄──────────────│  Viewing    │──────────────►
     navigate back  │   Image     │  navigate forward
                    └──────┬──────┘
                           │ delete all
                           ▼
                    ┌─────────────┐
                    │   Empty     │
                    │   History   │
                    └──────┬──────┘
                           │ new image received
                           ▼
                    ┌─────────────┐
                    │  Viewing    │
                    │   Image     │
                    └─────────────┘
```

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<section class="viewer">
    <div class="image-container">
        <img class="current-image" id="current-image" ... />

        <!-- Existing loading overlay enhanced -->
        <div class="loading-overlay" id="loading-overlay" aria-live="polite">
            <div class="spinner" aria-hidden="true"></div>
            <div class="loading-message" id="loading-message">
                <div class="loading-title">Generating your first image...</div>
                <div class="loading-subtitle" id="loading-subtitle"></div>
            </div>
            <div class="loading-hint" id="loading-hint"></div>
        </div>

        <!-- Empty state (separate element) -->
        <div class="empty-state hidden" id="empty-state" aria-live="polite">
            <div class="empty-icon">○</div>
            <div class="empty-title">No images in selection</div>
            <div class="empty-subtitle">New images will appear as they're generated.</div>
            <div class="empty-hint">Press Esc to abort.</div>
        </div>

        <!-- Error state -->
        <div class="error-state hidden" id="error-state" aria-live="assertive">
            <div class="error-icon">⚠</div>
            <div class="error-title">Generation failed</div>
            <div class="error-message" id="error-message"></div>
            <div class="error-hint">Press Esc to exit.</div>
        </div>
    </div>
</section>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
/* Shared placeholder styles */
.loading-overlay,
.empty-state,
.error-state {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: var(--bg-secondary);
    border-radius: 4px;
    text-align: center;
    padding: var(--spacing-xl);
}

.loading-title,
.empty-title,
.error-title {
    font-size: 16px;
    color: var(--text-primary);
    margin-bottom: var(--spacing-sm);
}

.loading-subtitle,
.empty-subtitle,
.error-message {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: var(--spacing-md);
}

.loading-hint,
.empty-hint,
.error-hint {
    font-size: 11px;
    color: var(--text-muted);
}

.empty-icon,
.error-icon {
    font-size: 48px;
    margin-bottom: var(--spacing-lg);
    color: var(--text-muted);
}

.error-state {
    background: rgba(239, 68, 68, 0.05);
}

.error-icon {
    color: var(--accent-danger);
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Add to elements cache
elements.emptyState = document.getElementById('empty-state');
elements.errorState = document.getElementById('error-state');
elements.loadingMessage = document.getElementById('loading-message');
elements.loadingTitle = document.querySelector('.loading-title');
elements.loadingSubtitle = document.getElementById('loading-subtitle');
elements.loadingHint = document.getElementById('loading-hint');

// State display management
function showState(stateName) {
    const states = ['loading-overlay', 'empty-state', 'error-state'];
    const stateElements = [elements.loadingOverlay, elements.emptyState, elements.errorState];

    stateElements.forEach((el, i) => {
        if (el) {
            el.classList.toggle('hidden', states[i] !== stateName);
        }
    });

    // Hide image when showing any placeholder
    if (stateName && elements.currentImage) {
        elements.currentImage.classList.add('hidden');
    }
}

// Initial loading state
function showInitialLoading(prompt) {
    if (elements.loadingTitle) {
        elements.loadingTitle.textContent = 'Generating your first image...';
    }
    if (elements.loadingSubtitle) {
        elements.loadingSubtitle.textContent = `Prompt: "${prompt}"`;
    }
    if (elements.loadingHint) {
        elements.loadingHint.textContent = '';
    }
    showState('loading-overlay');
}

// Waiting for next image
function showWaitingLoading() {
    if (elements.loadingTitle) {
        elements.loadingTitle.textContent = 'Generating next image...';
    }
    if (elements.loadingSubtitle) {
        elements.loadingSubtitle.textContent = '';
    }
    if (elements.loadingHint) {
        elements.loadingHint.textContent = 'Press ← to go back';
    }
    showState('loading-overlay');
}

// Empty history state
function showEmptyState() {
    showState('empty-state');
}

// Error state
function showErrorState(message) {
    if (elements.errorMessage) {
        elements.errorMessage.textContent = message;
    }
    showState('error-state');
}

// Hide all placeholders
function showImage() {
    showState(null);
    if (elements.currentImage) {
        elements.currentImage.classList.remove('hidden');
    }
}
```

## Out of Scope

- Animated illustrations in placeholders
- Retry button for errors (keyboard only)
- Progress indication in placeholders
- Customizable placeholder messages
- Branding/logo in initial state

## Success Criteria

### Functional Acceptance

1. **Initial Launch:**
   - Shows "Generating your first image..." with prompt
   - Transitions smoothly to first image

2. **Empty History:**
   - Shows when all images deleted
   - Updates when new image arrives

3. **Waiting State:**
   - Shows when at end of history, buffer empty
   - Includes hint to navigate back

4. **Error State:**
   - Shows on fatal backend error
   - Displays error message clearly

### Non-Functional Acceptance

1. **Transitions:** Smooth fade between states
2. **Accessibility:** All states announced to screen readers
3. **Consistency:** Styling matches rest of UI

## Implementation Notes

**Estimated Effort:** Small (1-2 hours)

**Testing Requirements:**
- All state transitions
- Error state with various messages
- Screen reader announcements
- Visual testing in both themes

**Dependencies:**
- None (uses existing state information)

**Rollout Plan:**
1. Add HTML structure for new states
2. Add CSS styling
3. Implement state management functions
4. Integrate with existing handlers
5. Test all state transitions
6. Verify accessibility
