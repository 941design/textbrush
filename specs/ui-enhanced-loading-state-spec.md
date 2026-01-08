# Feature Specification: Enhanced Loading State

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

The current loading overlay shows only a spinner and the generation prompt. Users have no indication of:

- How long generation will take
- Whether progress is being made
- If the system is stuck or working normally

For FLUX.1 schnell with 4 inference steps, generation typically takes 3-15 seconds depending on hardware. Without progress feedback, users may think the application has frozen or may interrupt generation prematurely.

## Core Functionality

Enhance the loading state with progress information including step count, optional ETA, and clearer visual feedback. The backend already knows the step count; this feature surfaces that information to the user.

## Functional Requirements

### FR1: Step Progress Display

**Requirement:** Show current step and total steps during generation

**Behavior:**
- Display format: "Step 2 of 4" or "2/4"
- Updates in real-time as inference progresses
- Shown below the spinner, above the prompt

**Backend Integration:**
- Requires new IPC message type: `generation_progress`
- Payload: `{ current_step: number, total_steps: number }`
- Sent after each inference step completes

### FR2: Progress Bar (Optional)

**Requirement:** Visual progress indicator

**Behavior:**
- Horizontal bar below spinner
- Width proportional to completion percentage
- Smooth transition between steps
- Subtle styling (not distracting)

**Implementation:**
```
[============        ] Step 3/4
```

### FR3: Elapsed Time Display

**Requirement:** Show time elapsed since generation started

**Behavior:**
- Format: "0:05" (minutes:seconds)
- Updates every second
- Helps users gauge performance
- Resets when new generation starts

**Display Logic:**
- Only show after 2 seconds (avoid flicker for fast generations)
- Stop updating when generation completes

### FR4: Status Text States

**Requirement:** Contextual status messages

**States:**
- **Initializing:** "Preparing model..." (before first step)
- **Generating:** "Step 2 of 4" (during inference)
- **Processing:** "Finalizing image..." (after last step, before display)
- **Queued:** "Waiting in queue..." (if buffer requests are queued)

### FR5: Cancel Hint

**Requirement:** Show how to cancel generation

**Behavior:**
- Small text below status: "Press Esc to abort"
- Only shown during active generation
- Muted styling to avoid prominence

## Critical Constraints

### Technical Constraints

1. **Backend Changes Required:**
   - Python backend must emit progress events
   - IPC protocol extended with `generation_progress` message
   - May require changes to inference engine interface

2. **Performance:**
   - Progress updates must not slow down inference
   - Use requestAnimationFrame for timer updates
   - Batch DOM updates to avoid reflows

3. **Accuracy:**
   - Step count must match actual inference steps
   - No false progress (don't fake it)
   - Handle edge cases (single-step inference, errors)

### User Experience Constraints

1. **Non-Intrusive:**
   - Progress info should inform, not distract
   - Spinner remains primary visual element
   - Text updates should not cause layout shifts

2. **Honesty:**
   - Don't show fake progress or inflated estimates
   - If ETA is unknown, don't show one
   - Clearly indicate when something is wrong

3. **Consistency:**
   - Progress format consistent across sessions
   - Timer format matches common conventions
   - Styling matches existing loading overlay

## Integration Points

### IPC Protocol (`textbrush/ipc/protocol.py`)

**Changes Required:**
```python
class MessageType(Enum):
    # ... existing types
    GENERATION_PROGRESS = "generation_progress"

# New message format:
# {"type": "generation_progress", "payload": {"current_step": 2, "total_steps": 4}}
```

### Inference Engine (`textbrush/inference/flux.py`)

**Changes Required:**
```python
def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
    for step in range(self.num_steps):
        # ... inference code
        self._emit_progress(step + 1, self.num_steps)
    # ... finalize
```

### HTML (`src-tauri/ui/index.html`)

**Changes Required:**
```html
<div class="loading-overlay hidden" id="loading-overlay" aria-live="polite">
    <div class="spinner" aria-hidden="true"></div>
    <div class="loading-progress" id="loading-progress">
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
        <div class="progress-text" id="progress-text">Preparing...</div>
    </div>
    <div class="loading-caption" id="loading-caption">
        <span class="loading-label">generating:</span>
        <span class="loading-prompt" id="loading-prompt"></span>
    </div>
    <div class="loading-hint">Press Esc to abort</div>
</div>
```

### CSS (`src-tauri/ui/styles/main.css`)

**Changes Required:**
```css
.loading-progress {
    margin-top: var(--spacing-md);
    text-align: center;
}

.progress-bar {
    width: 120px;
    height: 4px;
    background: var(--border-subtle);
    border-radius: 2px;
    overflow: hidden;
    margin: 0 auto var(--spacing-sm);
}

.progress-fill {
    height: 100%;
    background: var(--accent-primary);
    width: 0%;
    transition: width 200ms ease-out;
}

.progress-text {
    color: var(--text-secondary);
    font-size: 12px;
    font-family: var(--font-mono);
}

.loading-hint {
    margin-top: var(--spacing-lg);
    color: var(--text-muted);
    font-size: 11px;
}
```

### JavaScript (`src-tauri/ui/main.js`)

**Changes Required:**
```javascript
// Add to elements cache
elements.progressFill = document.getElementById('progress-fill');
elements.progressText = document.getElementById('progress-text');

// Handle progress messages
function handleGenerationProgress(payload) {
    const { current_step, total_steps } = payload;
    const percentage = (current_step / total_steps) * 100;

    if (elements.progressFill) {
        elements.progressFill.style.width = `${percentage}%`;
    }

    if (elements.progressText) {
        elements.progressText.textContent = `Step ${current_step} of ${total_steps}`;
    }
}

// Reset progress on new generation
function resetProgress() {
    if (elements.progressFill) {
        elements.progressFill.style.width = '0%';
    }
    if (elements.progressText) {
        elements.progressText.textContent = 'Preparing...';
    }
}

// Add to message handler switch
case 'generation_progress':
    handleGenerationProgress(msg.payload || {});
    break;
```

## Out of Scope

- Detailed performance metrics (GPU utilization, memory)
- Time remaining estimation (too unreliable)
- Generation queue visualization
- Historical generation time statistics
- Pause/resume generation
- Priority queue management

## Success Criteria

### Functional Acceptance

1. **Step Progress:**
   - Shows "Step N of M" during generation
   - Updates in real-time as steps complete
   - Resets on new generation

2. **Progress Bar:**
   - Fills proportionally to completion
   - Smooth transitions between steps
   - Visible but not distracting

3. **Status Messages:**
   - Appropriate message for each state
   - Clear indication of what's happening
   - No misleading information

4. **Cancel Hint:**
   - Shows "Press Esc to abort"
   - Visible during generation only

### Non-Functional Acceptance

1. **Performance:** No slowdown in inference
2. **Accuracy:** Progress matches actual inference state
3. **Styling:** Consistent with existing UI

## Implementation Notes

**Estimated Effort:** Medium (3-4 hours)

**Testing Requirements:**
- Unit tests for progress calculation
- Integration tests for IPC message handling
- Visual testing for progress bar animation
- Edge cases: rapid steps, single step, errors

**Dependencies:**
- Backend changes required (IPC protocol, inference engine)
- Must coordinate frontend and backend development

**Rollout Plan:**
1. Extend IPC protocol with progress message
2. Add progress emission to inference engine
3. Add Tauri event forwarding for progress
4. Implement frontend progress display
5. Style and test animations
6. Test end-to-end with real inference

**Phased Implementation:**
- Phase 1: Step count display only (no progress bar)
- Phase 2: Add progress bar
- Phase 3: Add elapsed time (if desired)

This allows incremental delivery with value at each phase.
