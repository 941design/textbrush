# UI Enhancements - Requirements Specification

## Problem Statement

The current UI has several limitations that reduce usability and visual appeal:
1. **Theming**: The dark theme is hardcoded with no option for light mode, and styling could be more polished
2. **Navigation**: Images can only be reviewed forward (skip discards permanently); users cannot revisit previous images
3. **Exit behavior**: Only a single file path is returned on accept; users cannot collect multiple images in a session
4. **Visual feedback**: Keyboard navigation provides no visual feedback on which action was triggered
5. **Image scaling**: Image display behavior within the window is not optimized for varying aspect ratios

This feature addresses these limitations to create a more polished, flexible image review experience.

## Core Functionality

### Theme System
- Adopt Hero UI design system for consistent, modern styling
- Provide toggle between light and dark themes
- Persist theme preference

### Image Navigation
- Navigate backward and forward through all generated images in the session
- Images are retained until explicitly deleted
- Delete current image with Cmd+Delete (macOS) / Ctrl+Delete (Linux)
- Clear visual indication of position in image history

### Multi-Image Output
- On exit, return paths to all retained (non-deleted) images
- Maintain the accept/abort semantic distinction

### Visual Feedback
- Flash/highlight buttons when their corresponding keyboard shortcuts are pressed
- Provide tactile visual response to cursor key navigation

### Image Scaling
- Scale images to fit within the viewer area
- Maintain aspect ratio (contain behavior)
- Either horizontal or vertical extent may limit the displayed size

---

## Functional Requirements

### FR-1: Hero UI Theme Integration

- **Design system**: Adopt Hero UI color palette, typography, and component styles
- **Implementation**: Update CSS variables in `variables.css` to Hero UI design tokens
- **Styling improvements**:
  - More refined button styles with better hover/active states
  - Improved typography hierarchy
  - Polished status bar and controls layout
  - Better visual separation between UI sections
- **Acceptance Criteria**:
  - UI uses Hero UI color palette and design conventions
  - Visual appearance is noticeably more polished than current implementation
  - All existing functionality continues to work

### FR-2: Light/Dark Theme Toggle

- **Location**: Controls section or status bar (implementation discretion)
- **Type**: Toggle switch or button
- **Behavior**:
  - Switch between light and dark color schemes
  - Apply theme change immediately without page reload
  - Persist preference to localStorage
  - Respect system preference on first launch (`prefers-color-scheme`)
- **Acceptance Criteria**:
  - Toggle is visible and accessible
  - Clicking toggle switches theme instantly
  - Theme persists across app restarts
  - Initial theme respects OS setting if no saved preference

### FR-3: Bidirectional Image Navigation

- **Controls**:
  - **Previous**: Left arrow key (`←`) or dedicated button
  - **Next**: Right arrow key (`→`) or Space
- **Behavior**:
  - Maintain ordered history of all generated images in the session
  - Navigation moves through history without discarding images
  - At end of history with pending buffer images, advance fetches next from buffer
  - At beginning of history, previous navigation is disabled/no-op
  - Current position indicator shows `[current]/[total]` in history
- **Image retention**: Images remain in history until explicitly deleted
- **Acceptance Criteria**:
  - User can navigate backward to previously viewed images
  - User can navigate forward through history and to new images
  - Position indicator accurately reflects current position
  - Navigation at boundaries behaves gracefully (no errors, clear indication)

### FR-4: Image Deletion

- **Shortcut**: Cmd+Delete (macOS) / Ctrl+Delete (Linux)
- **Behavior**:
  - Delete currently displayed image from history
  - Advance to next image in history (or previous if at end)
  - Update position indicator
  - If all images deleted, show empty/waiting state
  - Deleted images are removed from disk (temp files)
- **Confirmation**: No confirmation dialog (immediate deletion)
- **Acceptance Criteria**:
  - Cmd/Ctrl+Delete removes current image
  - Navigation automatically advances after deletion
  - Deleted images do not appear in final output
  - History count updates correctly

### FR-5: Multi-Path Exit Contract

- **Accept action** (`Enter` key):
  - Save all retained images to output directory (if not already saved)
  - Print all retained image paths to stdout, one per line
  - Exit with code 0
- **Abort action** (`Esc` key):
  - Discard all images
  - Print nothing to stdout
  - Exit with code 1
- **Edge case**: If all images have been deleted, Accept behaves like Abort (exit 1, no output)
- **Acceptance Criteria**:
  - Accept prints multiple paths (newline-separated) when multiple images retained
  - Accept prints single path when one image retained (backward compatible)
  - Accept with zero images exits with code 1
  - Abort always exits with code 1 and no stdout

### FR-6: Button Flash on Keyboard Navigation

- **Trigger**: When user presses a keyboard shortcut for an action
- **Visual effect**: Corresponding button briefly shows active/pressed state
- **Buttons affected**:
  - Left arrow → Previous button (if visible)
  - Right arrow / Space → Next/Skip button
  - Enter → Accept button
  - Esc → Abort button
  - Cmd/Ctrl+Delete → Delete indicator or current image flash
- **Animation**: Brief highlight (~150ms) that mimics physical button press
- **Acceptance Criteria**:
  - Button visually responds when its shortcut is pressed
  - Flash is noticeable but not distracting
  - Flash does not interfere with action execution

### FR-7: Fit-to-Window Image Scaling

- **Behavior**: Scale image to fit within viewer area while maintaining aspect ratio
- **Constraint**: Image should not exceed viewer bounds in either dimension
- **CSS approach**: `object-fit: contain` on image element
- **Centering**: Image centered horizontally and vertically in viewer
- **Edge cases**:
  - Very wide images: limited by width, vertical space unused
  - Very tall images: limited by height, horizontal space unused
  - Square images: fit to smaller dimension
- **Acceptance Criteria**:
  - Images never overflow the viewer area
  - Aspect ratio is always preserved
  - Images are centered in the viewer
  - Works correctly for all supported aspect ratios (1:1, 16:9, 9:16)

---

## Critical Constraints

### C-1: Backward Compatibility

- Single-image workflows must continue to work
- CLI arguments and configuration unchanged
- Editors expecting single-path output should handle multi-path gracefully (first line is primary)

### C-2: Memory Management

- Image history stored in memory must be bounded or managed
- Consider maximum history size to prevent excessive memory usage
- Blob URLs must be properly revoked when images are deleted

### C-3: Theme Persistence

- Theme preference stored in localStorage
- Must not conflict with other application state
- Handle missing or corrupt localStorage gracefully

### C-4: Performance

- Theme switch must be instantaneous (CSS variable swap)
- Image navigation must feel responsive (<100ms)
- Button flash animation must not block action execution

### C-5: Accessibility

- Theme toggle must be keyboard accessible
- Maintain existing keyboard navigation support
- Ensure sufficient contrast in both light and dark themes (WCAG AA)
- Respect `prefers-reduced-motion` for button flash animation

---

## Integration Points

### IP-1: CSS Theme System

- Root-level CSS variables for all colors
- `data-theme="light"` or `data-theme="dark"` attribute on `<html>` or `<body>`
- Hero UI design tokens mapped to CSS custom properties

### IP-2: Image History State

- Frontend `state` object extended with:
  - `imageHistory: Array<{blob: Blob, seed: number, path?: string}>`
  - `historyIndex: number`
- Backend may need to track saved image paths

### IP-3: Exit Handler Modification

- Rust `print_and_exit` command updated to accept array of paths
- Or: new command `print_paths_and_exit(paths: Vec<String>)`
- Print paths newline-separated to stdout

### IP-4: IPC Protocol

- Possible new message type for deletion confirmation
- Or: deletion handled purely in frontend with path tracking

### IP-5: Button Component Enhancement

- Add method to trigger flash animation: `flashButton(buttonId)`
- Called from keyboard event handlers

---

## User Preferences

### UP-1: Theme Toggle Location

- Theme toggle should be unobtrusive but discoverable
- Suggested location: corner of status bar or near controls
- Icon-based toggle preferred (sun/moon icons)

### UP-2: Navigation Button Visibility

- Previous/Next buttons may be added to controls section
- Or rely purely on keyboard navigation with on-screen hints
- Current approach: keyboard-first with optional visible buttons

### UP-3: Deletion Feedback

- Brief visual confirmation when image is deleted
- Position indicator update provides implicit feedback

---

## Out of Scope

- Custom theme creation or color customization
- Image editing, cropping, or post-processing
- Undo for deleted images (deletion is permanent)
- Drag-and-drop reordering of image history
- Export to formats other than configured output format
- Thumbnail gallery view of history
- Batch operations on multiple images
- Image comparison side-by-side view
- Zoom or pan within images

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined during the architecture phase.
