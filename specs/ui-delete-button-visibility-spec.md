# Feature Specification: Delete Button Visibility

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

The delete functionality exists (Cmd/Ctrl+Delete removes current image from history) but has no corresponding UI button. Users must discover this feature through documentation or trial and error. This violates the principle of progressive disclosure—advanced features should be discoverable, even if not prominent.

Power users rely on keyboard shortcuts, but casual users or those new to the application may never discover they can remove unwanted images from their selection before accepting.

## Core Functionality

Add a delete button to the control section that removes the current image from history. The button should be visually distinct (warning-styled) but less prominent than the primary actions (Accept/Navigate/Abort).

## Functional Requirements

### FR1: Delete Button Appearance

**Requirement:** Add delete button to controls section

**Behavior:**
- Button positioned between Abort and Navigate buttons
- Smaller than primary action buttons
- Warning color scheme (red/orange tint)
- Icon: trash/delete symbol

**Visual Hierarchy:**
```
[Abort] [Delete] [Navigate] [Accept]
  ↓        ↓         ↓         ↓
danger  warning   neutral   success
```

### FR2: Button States

**Requirement:** Button has appropriate interactive states

**States:**
- **Default:** Subtle warning styling, muted icon
- **Hover:** Enhanced warning color, tooltip visible
- **Active:** Scale down effect (0.98)
- **Disabled:** Grayed out when no image to delete
- **Focus:** Visible focus ring for keyboard navigation

**Disabled Conditions:**
- No images in history
- Currently at loading placeholder
- Transition in progress

### FR3: Click Handler

**Requirement:** Clicking button triggers delete action

**Behavior:**
- Calls existing `deleteCurrentImage()` function
- Shows brief flash animation on button
- Updates position indicator
- Navigates to next image (or shows empty state)

**Confirmation:** No confirmation dialog (matches keyboard shortcut behavior). Users can navigate back if they made a mistake (deleted images are gone from acceptance, but rapid undo via history would require separate feature).

### FR4: Keyboard Shortcut Display

**Requirement:** Show keyboard shortcut on button

**Behavior:**
- Display shortcut below button label
- macOS: "Cmd+Del"
- Other platforms: "Ctrl+Del"
- Detect platform and show appropriate modifier

**Implementation:**
```javascript
const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
const shortcut = isMac ? 'Cmd+Del' : 'Ctrl+Del';
```

### FR5: Tooltip

**Requirement:** Show descriptive tooltip on hover

**Behavior:**
- Tooltip text: "Remove from selection (Cmd+Delete)"
- Appears after 500ms hover delay
- Positioned above button
- Disappears on mouse leave or click

## Critical Constraints

### Technical Constraints

1. **Existing Function Reuse:**
   - Must use existing `deleteCurrentImage()` function
   - No duplicate delete logic
   - Same behavior as keyboard shortcut

2. **Layout Stability:**
   - Button must not shift other buttons
   - Fixed width to prevent layout changes
   - Consistent gap spacing with other buttons

3. **Platform Detection:**
   - Reliable platform detection for shortcut display
   - Fallback to generic text if detection fails

### User Experience Constraints

1. **Discoverability vs. Prominence:**
   - Button should be findable but not distracting
   - Should not compete with Accept for attention
   - Warning styling indicates caution without alarm

2. **Consistency:**
   - Button styling consistent with other control buttons
   - Same padding, border-radius, transition effects
   - Same disabled state styling

3. **Accessibility:**
   - Full keyboard navigation support
   - Screen reader label describes action clearly
   - Focus visible and keyboard-activatable

## Integration Points

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<section class="controls">
    <button class="control-btn btn-abort" id="abort-btn" ...>
        ...
    </button>
    <button
        class="control-btn btn-delete"
        id="delete-btn"
        type="button"
        title="Remove current image from selection"
        aria-label="Delete current image"
    >
        <span class="btn-icon" aria-hidden="true">🗑</span>
        <span class="btn-label">Delete</span>
        <span class="btn-shortcut" id="delete-shortcut">Cmd+Del</span>
    </button>
    <button class="control-btn btn-skip" id="skip-btn" ...>
        ...
    </button>
    <button class="control-btn btn-accept" id="accept-btn" ...>
        ...
    </button>
</section>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.btn-delete {
    min-width: 80px; /* Slightly smaller than other buttons */
}

.btn-delete:hover {
    border-color: var(--accent-warning, #f59e0b);
    background: rgba(245, 158, 11, 0.1);
}

.btn-delete:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}
```

### CSS Variables (`src-tauri/ui/styles/variables.css`)

**Changes Required:**
```css
:root {
    --accent-warning: #f59e0b;
}

:root[data-theme="light"] {
    --accent-warning: #d97706;
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Add to elements cache
elements.deleteButton = document.getElementById('delete-btn');
elements.deleteShortcut = document.getElementById('delete-shortcut');

// Set platform-specific shortcut text
function setPlatformShortcuts() {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    if (elements.deleteShortcut) {
        elements.deleteShortcut.textContent = isMac ? 'Cmd+Del' : 'Ctrl+Del';
    }
}

// Add to setupButtonListeners
if (elements.deleteButton) {
    elements.deleteButton.addEventListener('click', deleteCurrentImage);
}

// Update delete button state
function updateDeleteButtonState() {
    if (!elements.deleteButton) return;

    const canDelete = state.imageHistory.length > 0 &&
                      !state.waitingForNext &&
                      !state.isTransitioning;

    elements.deleteButton.disabled = !canDelete;
}

// Call updateDeleteButtonState in:
// - handleImageReady
// - previous
// - skip
// - deleteCurrentImage
// - showLoadingPlaceholder
```

## Out of Scope

- Undo/restore deleted images
- Multi-select delete
- Confirmation dialog
- Bulk delete all
- Delete with animation (image flies to trash)
- Haptic feedback

## Success Criteria

### Functional Acceptance

1. **Button Visible:**
   - Delete button appears in controls section
   - Styled consistently with other buttons

2. **Click Action:**
   - Clicking button deletes current image
   - Same result as keyboard shortcut

3. **Disabled State:**
   - Button disabled when no images
   - Button disabled during transitions
   - Visual feedback for disabled state

4. **Platform Shortcut:**
   - Shows "Cmd+Del" on macOS
   - Shows "Ctrl+Del" on Linux

5. **Keyboard Navigation:**
   - Button focusable via Tab
   - Activatable via Enter/Space when focused

### Non-Functional Acceptance

1. **Layout:** No layout shifts when button added
2. **Styling:** Consistent with design system
3. **Accessibility:** Screen reader compatible

## Implementation Notes

**Estimated Effort:** Small (1 hour)

**Testing Requirements:**
- Click handler functionality
- Disabled state conditions
- Platform detection for shortcuts
- Keyboard navigation
- Screen reader testing

**Dependencies:**
- May want to add `--accent-warning` color variable
- Uses existing `deleteCurrentImage()` function

**Rollout Plan:**
1. Add warning color variable to variables.css
2. Add button HTML to index.html
3. Add button styles to main.css
4. Add click handler and state management to main.js
5. Test on macOS and Linux
6. Verify accessibility

**Alternative Approaches Considered:**
1. **Icon-only button:** More compact but less discoverable
2. **Context menu:** Right-click on image to delete—more hidden
3. **Swipe gesture:** Mobile-friendly but not applicable to desktop
4. **Inline delete on hover:** Shows X on image corner—more intrusive

Recommendation: Standard button is most consistent with existing UI pattern.
