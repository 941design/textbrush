# Feature Specification: Dynamic Image Container Sizing

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The image container is hardcoded to 512x512px in `main.css`, regardless of the selected aspect ratio (1:1, 16:9, 9:16). When users select 16:9 or 9:16, the generated image is constrained to fit within a square container, resulting in significant wasted space and a smaller visible image than necessary.

The current implementation limits the user's ability to preview images at their intended proportions, reducing the effectiveness of the review workflow.

## Core Functionality

Dynamically resize the image container based on the selected aspect ratio while maintaining maximum utilization of available viewport space. The container should adapt when the aspect ratio changes, providing optimal image display for each format.

## Functional Requirements

### FR1: Aspect Ratio Container Mapping

**Requirement:** Map aspect ratio selection to container dimensions

**Behavior:**
- 1:1 aspect ratio: Container maintains square proportions
- 16:9 aspect ratio: Container width exceeds height (wider than tall)
- 9:16 aspect ratio: Container height exceeds width (taller than wide)

**Container Sizing Rules:**
```
1:1   → max(512px, min(viewerWidth - 48px, viewerHeight - 48px)) square
16:9  → width: min(viewerWidth - 48px, (viewerHeight - 48px) * 16/9)
        height: width * 9/16
9:16  → height: min(viewerHeight - 48px, (viewerWidth - 48px) * 16/9)
        width: height * 9/16
```

Note: 48px accounts for padding (24px on each side).

### FR2: Container Transition Animation

**Requirement:** Animate container size changes smoothly

**Behavior:**
- Container resizes with CSS transition when aspect ratio changes
- Transition duration: 200ms ease-out
- Image fades out before resize, fades in after resize
- No jarring layout shifts during transition

**Animation Sequence:**
1. User selects new aspect ratio
2. Current image fades to 50% opacity (100ms)
3. Container animates to new dimensions (200ms)
4. Image source updates (if different aspect produces different image)
5. Image fades to 100% opacity (100ms)

### FR3: Viewport-Aware Sizing

**Requirement:** Container respects available viewport space

**Behavior:**
- Container never exceeds viewer section bounds
- Maintains aspect ratio even when viewport is constrained
- Minimum container size: 256px on smallest dimension
- Maximum container size: viewport bounds minus padding

**Responsive Rules:**
- Calculate available space: `viewer.clientWidth - 48`, `viewer.clientHeight - 48`
- Scale container to fit within available space while maintaining aspect ratio
- Center container within viewer section

### FR4: CSS Variable-Based Dimensions

**Requirement:** Use CSS custom properties for container dimensions

**Behavior:**
- Define `--container-width` and `--container-height` variables
- JavaScript updates these variables when aspect ratio changes
- CSS uses variables for `.image-container` dimensions
- Enables future theming and configuration

**Implementation:**
```css
.image-container {
    width: var(--container-width, 512px);
    height: var(--container-height, 512px);
    transition: width 200ms ease-out, height 200ms ease-out;
}
```

### FR5: Integration with Config Controls

**Requirement:** Container updates when aspect ratio control changes

**Behavior:**
- Listen to aspect ratio radio button changes
- Calculate new container dimensions
- Update CSS custom properties
- Trigger transition animation

**Event Flow:**
1. User clicks aspect ratio radio button
2. `config_controls.js` dispatches change event
3. Container sizing logic receives event
4. New dimensions calculated and applied
5. Backend notified of aspect ratio change (for new generations)

## Critical Constraints

### Technical Constraints

1. **No Layout Shifts:**
   - Container must not cause page reflow during transitions
   - Use `transform` and `opacity` for animations where possible
   - Avoid triggering expensive layout recalculations

2. **Image Object-Fit:**
   - Image must continue using `object-fit: contain`
   - Image should fill container without distortion
   - Letterboxing acceptable if aspect ratios don't match exactly

3. **Browser Compatibility:**
   - CSS custom properties required (supported in all modern browsers)
   - CSS transitions required
   - No JavaScript animation libraries

### User Experience Constraints

1. **Smooth Transitions:**
   - Users should not experience jarring size changes
   - Aspect ratio change should feel intentional and polished

2. **Immediate Feedback:**
   - Container should begin resizing immediately on selection
   - No delay between click and visual response

3. **Consistent Centering:**
   - Image container always centered in viewer
   - Centering maintained during and after transitions

## Integration Points

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.image-container {
    position: relative;
    width: var(--container-width, 512px);
    height: var(--container-height, 512px);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    transition: width 200ms ease-out, height 200ms ease-out;
}
```

### JavaScript (`src-tauri/ui/main.js` or new module)

**Changes Required:**
```javascript
function updateContainerSize(aspectRatio) {
    const viewer = document.querySelector('.viewer');
    const container = document.querySelector('.image-container');

    const availableWidth = viewer.clientWidth - 48;
    const availableHeight = viewer.clientHeight - 48;

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

    document.documentElement.style.setProperty('--container-width', `${width}px`);
    document.documentElement.style.setProperty('--container-height', `${height}px`);
}
```

### Config Controls (`src-tauri/ui/config_controls.js`)

**Changes Required:**
- Call `updateContainerSize()` when aspect ratio changes
- Pass current aspect ratio to the sizing function
- Ensure sizing runs on initial load

## Out of Scope

- Custom aspect ratios beyond 1:1, 16:9, 9:16
- User-configurable container sizes
- Pinch-to-zoom or image panning
- Full-screen image viewing mode
- Animation customization (duration, easing)

## Success Criteria

### Functional Acceptance

1. **1:1 Aspect Ratio:**
   - Container displays as square
   - Image fills container without distortion

2. **16:9 Aspect Ratio:**
   - Container displays as landscape rectangle
   - Image fills wider container appropriately

3. **9:16 Aspect Ratio:**
   - Container displays as portrait rectangle
   - Image fills taller container appropriately

4. **Transition Animation:**
   - Changing aspect ratio animates smoothly
   - No layout jumps or flashes

5. **Viewport Constraints:**
   - Container never exceeds viewer bounds
   - Container scales down on smaller windows

### Non-Functional Acceptance

1. **Performance:** No frame drops during transitions (60fps)
2. **Responsiveness:** Container adjusts within 16ms of selection
3. **Accessibility:** No motion issues (respects prefers-reduced-motion)

## Implementation Notes

**Estimated Effort:** Medium (2-3 hours)

**Testing Requirements:**
- Manual testing with all three aspect ratios
- Window resize behavior verification
- Animation smoothness on various hardware
- Prefers-reduced-motion media query testing

**Dependencies:**
- None (pure CSS/JS enhancement)

**Rollout Plan:**
1. Add CSS custom properties to variables.css
2. Update .image-container styles in main.css
3. Create container sizing module or add to main.js
4. Integrate with config_controls.js
5. Test all aspect ratio combinations
6. Verify no regressions in existing functionality
