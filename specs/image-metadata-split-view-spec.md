# Image Metadata Split View - Requirements Specification

## Problem Statement

Currently, the application displays only the generated image with minimal metadata (seed only) shown in the status bar. Users cannot see important generation parameters like the prompt and model name that were used to create each image. This makes it difficult to understand the context of generated images, especially when navigating through history or reviewing multiple generations.

## Core Functionality

Split the main viewer area into two panels:
- **Left panel**: Image display (existing functionality)
- **Right panel**: Metadata display showing generation parameters

The metadata panel should show the following fields:
- Prompt (the text used to generate the image)
- Model (the AI model name, e.g., "FLUX.1-schnell")
- Seed (the random seed value)

## Functional Requirements

### FR1: Split Layout
- The main `.viewer` section must be split into two side-by-side panels using flexbox layout
- Left panel displays the image (retains current image display behavior)
- Right panel displays metadata in a structured, readable format
- Right panel has a fixed width of approximately 300-400px
- Left panel takes remaining space (flexible)
- **Acceptance**: Visual inspection shows two distinct panels with image on left, metadata on right

### FR2: Metadata Display - Core Fields
- Display three core metadata fields:
  1. **Prompt**: Full text of the generation prompt
  2. **Model**: AI model name (e.g., "black-forest-labs/FLUX.1-schnell")
  3. **Seed**: Random seed value used for generation
- Metadata is displayed in read-only format (no editing)
- Use clear labels and formatting (e.g., "Prompt:", "Model:", "Seed:")
- Long prompts should wrap or scroll within the panel
- **Acceptance**: All three fields are visible and correctly display current image's metadata

### FR3: Metadata Visibility State
- Metadata panel is hidden when no image is loaded
- Metadata panel appears when an image is displayed
- Metadata updates when navigating through history (forward/back)
- Metadata updates when new images are generated
- **Acceptance**: Panel shows/hides correctly and displays accurate metadata for current image

### FR4: History Integration
- Image history must store metadata for each image (prompt, model, seed)
- When navigating to a previous image, display its associated metadata
- Metadata persists correctly throughout the session
- **Acceptance**: Navigating through history shows correct metadata for each image

## Critical Constraints

### Technical Constraints
1. **Metadata Pipeline Extension**: The `ImageReadyEvent` IPC message currently only includes `seed`. Must be extended to include `prompt` and `model_name`.
2. **Layout Compatibility**: Must maintain existing responsive behavior and not break current flexbox layout structure.
3. **State Management**: Metadata must be stored in `state.imageHistory` alongside existing `image_data`, `seed`, and `blobUrl` fields.
4. **No CSS Grid**: Project uses flexbox exclusively; continue this pattern.

### Design Constraints
1. **Design System Adherence**: Use existing CSS custom properties from `variables.css` for colors, spacing, and typography.
2. **Theme Support**: Metadata panel must work in both dark and light themes.
3. **No New Dependencies**: Use vanilla HTML/CSS/JS; no new libraries.

### Performance Constraints
1. **No Re-encoding**: Don't re-encode images when adding metadata to history; reuse existing blob URLs.
2. **Minimal Layout Shift**: Image display should not flicker or shift when metadata panel appears/disappears.

## Integration Points

### Backend (Python)
- **File**: `textbrush/ipc/protocol.py`
  - Extend `ImageReadyEvent` dataclass to include `prompt: str` and `model_name: str`
- **File**: `textbrush/ipc/handler.py`
  - Pass prompt and model_name from backend to `ImageReadyEvent` when sending images to UI
- **File**: `textbrush/backend.py`
  - Ensure prompt is accessible in backend state for inclusion in IPC messages
  - Access `model_name` from `GenerationResult` returned by inference engine

### Frontend (JavaScript)
- **File**: `src-tauri/ui/main.js`
  - Update `handleImageReady()` to extract and store `prompt` and `model_name` from payload
  - Update `state.imageHistory` structure to include new metadata fields
  - Update `displayImage()` to show/hide metadata panel and populate fields
- **File**: `src-tauri/ui/index.html`
  - Modify `.viewer` section to contain two panels instead of single image container
  - Add metadata panel HTML structure with labels and value elements
- **File**: `src-tauri/ui/styles/main.css`
  - Update `.viewer` to use flexbox row layout
  - Style metadata panel with fixed width, padding, and field layout
  - Add show/hide transitions for metadata panel

## User Preferences

- **Simple Implementation**: Fixed-width panel preferred over resizable divider
- **Read-Only Display**: No editing of metadata required
- **Minimal Fields**: Focus on essential metadata (prompt, model, seed) rather than exhaustive data
- **Hide When Empty**: Metadata panel should be hidden when no image is loaded rather than showing placeholders

## Codebase Context

See `.exploration/image-metadata-split-view-context.md` for detailed exploration findings including:
- Current UI structure and layout patterns
- Metadata handling pipeline
- Integration points and potential gaps

## Related Artifacts

- **Exploration Context**: `.exploration/image-metadata-split-view-context.md`

## Out of Scope

The following are explicitly NOT included in this feature:
- Embedding metadata in saved PNG files (EXIF data)
- Editing or modifying metadata values
- User-resizable panel divider
- Extended metadata fields (dimensions, generation time, steps, aspect ratio, timestamps)
- Metadata export or copy functionality
- Metadata persistence to disk
- Comparison view with multiple images

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined by the integration-architect during Phase 2.
