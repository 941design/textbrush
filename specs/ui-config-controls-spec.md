# UI Configuration Controls - Requirements Specification

## Problem Statement

Currently, all image generation parameters (prompt, aspect ratio, seed) are provided via CLI arguments at application launch and cannot be changed during runtime. Users must close and restart the application with new arguments to change generation parameters. This creates friction in the workflow and prevents iterative exploration of different prompts or aspect ratios.

This feature enables in-UI configuration of generation parameters to support a more fluid, iterative creative workflow.

## Core Functionality

Add editable controls to the UI allowing users to modify:
1. **Prompt** - the text description for image generation
2. **Aspect ratio** - the image dimensions ratio (1:1, 16:9, or 9:16)

When any parameter changes (on blur or Enter keypress), the system should:
1. Stop current generation and purge the image buffer queue
2. Restart generation with the new configuration
3. Keep the currently displayed image visible until the first new image is ready

## Functional Requirements

### FR-1: Prompt Input Control
- **Location**: Status bar, replacing the current read-only prompt display
- **Type**: Text input field
- **Behavior**:
  - Initially populated with the CLI-provided prompt
  - Editable by clicking/focusing the field
  - Accepts any non-empty text string
  - Commits changes on blur or Enter keypress
  - **Acceptance Criteria**:
    - User can click the prompt area to edit it
    - Typing and editing works as expected (standard text input behavior)
    - Pressing Enter or clicking outside the field triggers configuration update
    - Empty prompts are rejected (validation message or prevent commit)

### FR-2: Aspect Ratio Radio Button Group
- **Location**: Status bar, new section for aspect ratio control
- **Type**: Radio button group with three options
- **Options**:
  - "1:1" (1024×1024 pixels)
  - "16:9" (1344×768 pixels)
  - "9:16" (768×1344 pixels)
- **Behavior**:
  - Initially set to CLI-provided aspect ratio (default: "1:1")
  - Clicking a different radio button commits the change immediately on blur/Enter
  - **Acceptance Criteria**:
    - Three radio buttons labeled "1:1", "16:9", "9:16" are visible
    - Only one option can be selected at a time
    - Current selection is visually indicated (radio button checked state)
    - Selecting a different option and confirming (blur/Enter) triggers configuration update
    - Dimensions are derived from fixed mapping (no custom dimension inputs)

### FR-3: Configuration Update and Generation Restart
- **Trigger**: Field blur or Enter keypress on prompt input, or aspect ratio selection change
- **Behavior**:
  - Detect configuration change
  - Stop current generation worker
  - Purge image buffer queue (discard all pending images)
  - Create new GenerationWorker with updated prompt and/or aspect ratio
  - Start new generation
  - **Acceptance Criteria**:
    - Generation restarts with new configuration within 1 second of commit
    - Buffer indicator resets to 0 (empty queue)
    - New images generated use the updated parameters
    - No stale images from previous configuration are delivered

### FR-4: Visual State During Restart
- **Behavior**:
  - Currently displayed image remains visible during restart
  - Loading overlay does NOT appear during restart (only if buffer becomes empty)
  - Buffer indicator shows 0/8 immediately after restart
  - Status bar updates to show new prompt text
  - First new image replaces the old image when ready
  - **Acceptance Criteria**:
    - User sees smooth transition without jarring blank states
    - Old image stays visible until new image is generated and ready
    - Buffer count accurately reflects the purged and refilling state
    - Seed display updates when first new image is delivered

### FR-5: Seed Display Behavior
- **Current behavior**: Seed is displayed in the status bar (read-only)
- **New behavior**: Seed remains read-only, displays the seed of the currently shown image
- **Behavior**:
  - Seed is NOT configurable through UI (remains auto-generated or from CLI)
  - Seed display updates when each new image is shown
  - **Acceptance Criteria**:
    - Seed display remains read-only
    - Shows "—" or "pending" when no image is displayed
    - Updates to show the correct seed for each displayed image

## Critical Constraints

### C-1: Parameter Validation
- Prompt must not be empty (minimum 1 character)
- Aspect ratio must be one of: "1:1", "16:9", "9:16"
- Invalid configurations should show inline error messages and prevent commit

### C-2: Thread Safety
- Configuration updates must properly stop the GenerationWorker thread
- Buffer must be cleared atomically (existing buffer.clear() method)
- No race conditions between worker stopping and new worker starting

### C-3: State Consistency
- Frontend state must stay in sync with backend generation state
- Buffer status events must accurately reflect queue state after purge
- Current image reference must be valid until replaced

### C-4: Performance
- Configuration change should feel responsive (<100ms to initiate restart)
- UI should not freeze or become unresponsive during restart
- Model remains loaded (no need to reload FLUX.1 model between config changes)

### C-5: Existing Workflow Compatibility
- CLI arguments should still work to set initial configuration
- Skip, Accept, Abort buttons continue to function as before
- Keyboard shortcuts (Space, Enter, Esc) remain unchanged

## Integration Points

### IP-1: IPC Protocol Extension
- New message type: `UPDATE_CONFIG` or similar
- Payload: `{prompt: string, aspect_ratio: string}`
- Python backend handler processes message and restarts generation

### IP-2: Rust Tauri Command
- New invoke command: `update_generation_config(prompt, aspect_ratio)`
- Command stops sidecar generation, sends UPDATE_CONFIG message
- Or: reuses existing abort + init pattern

### IP-3: Backend Lifecycle
- MessageHandler needs new handler method: `handle_update_config()`
- Logic: call `backend.abort()`, then `backend.start_generation()` with new params
- Ensures clean shutdown of worker and buffer purge

### IP-4: Frontend State Management
- `state` object tracks current config values
- Input fields bound to state, sync on change events
- On config update: invoke Rust command, update local state

### IP-5: UI Layout
- Status bar section modified to include:
  - Editable prompt text input (replaces read-only prompt display)
  - Radio button group for aspect ratio
- CSS styling for form controls consistent with existing dark theme

## User Preferences

### UP-1: Apply on Blur/Enter
- Configuration changes commit when:
  - Prompt input loses focus (blur event)
  - User presses Enter in prompt input
  - Aspect ratio radio button selection changes (on blur/Enter)
- This provides a balance between immediate feedback and controlled updates

### UP-2: Radio Button UI
- Use radio buttons (not dropdown) for aspect ratio selection
- Clear visual indication of current selection
- Aligned horizontally or vertically as appropriate for status bar space

### UP-3: Smooth Transitions
- Keep old image visible during restart (avoid jarring blank screen)
- Fade in first new image when ready
- Use existing image transition animations

## Codebase Context

See `.exploration/ui-config-controls-context.md` for exploration findings including:
- Existing UI components and layout patterns
- IPC message flow and command structure
- Backend initialization and generation start logic
- Buffer management and queue purging implementation

## Related Artifacts

- **Exploration Context**: `.exploration/ui-config-controls-context.md`

## Out of Scope

- Custom dimension inputs (only predefined aspect ratios supported)
- Seed configuration via UI (remains auto-generated or CLI-provided)
- Saving/loading configuration presets
- History of previous prompts or configurations
- Real-time preview of aspect ratio change before committing
- Configuration validation during typing (only on commit)
- Advanced settings (steps, guidance scale, etc.)
- Multi-prompt batching or scheduling

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined by the integration-architect during Phase 2.
