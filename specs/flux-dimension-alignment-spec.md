# Flux Dimension Alignment and Metadata Enhancement - Requirements Specification

## Problem Statement

The FLUX.1 Schnell model requires image dimensions to be divisible by 16 for proper generation. When users specify dimensions that don't meet this requirement, the model may produce errors or suboptimal results. Currently, the system does not enforce this constraint, and users are unaware of the actual dimensions used for generation versus the final output dimensions.

## Core Functionality

This feature ensures that all image generation through the Flux model uses dimensions divisible by 16 by:
1. Automatically rounding up any non-compliant width or height to the next multiple of 16
2. Generating the image at the rounded dimensions
3. Cropping the generated image back to the user's intended dimensions using center cropping
4. Storing both the generated dimensions (used by the model) and final dimensions (after cropping) in image metadata
5. Displaying both sets of dimensions in the UI for user transparency

## Functional Requirements

### FR1: Dimension Rounding Logic
- **Requirement**: Before generating an image, if either width or height is not divisible by 16, round UP to the next number divisible by 16
- **Acceptance Criteria**:
  - Dimensions already divisible by 16 remain unchanged (e.g., 1024×1024 → 1024×1024)
  - Dimensions not divisible by 16 are rounded up (e.g., 1000×750 → 1008×752)
  - Rounding applies to both custom dimensions and dimensions resolved from aspect ratios
  - Algorithm: `rounded = ((dim + 15) // 16) * 16`

### FR2: Image Cropping After Generation
- **Requirement**: After generation, if dimensions were rounded up, crop the image back to the intended size using center cropping
- **Acceptance Criteria**:
  - If no rounding occurred, no cropping is performed
  - Cropping is evenly distributed on all sides (center crop)
  - For example, if width was rounded from 1000 to 1008 (+8 pixels), crop 4 pixels from left and 4 from right
  - If extra pixels are odd, bias toward cropping more from right/bottom (e.g., +7 pixels → crop 3 left, 4 right)
  - Final image dimensions exactly match the user's intended dimensions

### FR3: Enhanced Metadata Storage
- **Requirement**: Store both generated dimensions and final dimensions in image metadata
- **Acceptance Criteria**:
  - Add new PNG tEXt metadata fields: `GeneratedWidth` and `GeneratedHeight`
  - Existing `Width` and `Height` fields contain final (post-crop) dimensions
  - All dimension fields are stored as strings in the PNG tEXt chunks
  - Metadata is saved alongside existing fields (AspectRatio, Prompt, Model, Seed)
  - For images where no rounding occurred, GeneratedWidth==Width and GeneratedHeight==Height

### FR4: UI Metadata Panel Enhancement
- **Requirement**: Display both generated dimensions and final dimensions in the UI metadata panel
- **Acceptance Criteria**:
  - Add two new metadata rows in the "Image Details" panel:
    - "Generated Size: 1008×752" (dimensions used by model, divisible by 16)
    - "Final Size: 1000×750" (dimensions of saved image after cropping)
  - Format as `<width>×<height>` (using × character, not 'x')
  - When dimensions are identical, both rows still appear (shows no rounding was needed)
  - New fields appear below existing Seed field and above Path field
  - Fields follow existing styling patterns (2-column grid layout)

### FR5: BufferedImage Metadata Extension
- **Requirement**: Extend BufferedImage dataclass to carry generated dimensions through the pipeline
- **Acceptance Criteria**:
  - Add `generated_width: int` and `generated_height: int` fields to BufferedImage
  - These fields are populated by the inference engine after rounding but before generation
  - Fields flow through: InferenceEngine → Worker → Buffer → Backend → IPC → UI
  - Existing metadata (seed, prompt, model_name, aspect_ratio) remains unchanged

## Critical Constraints

### C1: Dimension Rounding Location
- Rounding logic MUST be implemented in `FluxInferenceEngine.generate()` method
- This ensures all generation paths (CLI, UI, API) are covered consistently
- Rounding occurs after dimension resolution but before pipeline invocation

### C2: Deterministic Rounding
- Rounding algorithm must be deterministic and consistent
- Same input dimensions must always produce same rounded dimensions
- Formula: `rounded = ((dim + 15) // 16) * 16`

### C3: Center Crop Algorithm
- Cropping MUST be evenly distributed from all sides
- Left crop = `(generated_width - final_width) // 2`
- Top crop = `(generated_height - final_height) // 2`
- Right/bottom crops handle any remainder from integer division

### C4: Backward Compatibility
- Existing images without GeneratedWidth/GeneratedHeight metadata are handled gracefully
- UI shows "—" (em dash) for missing generated dimension fields
- Existing functionality (dimension resolution, aspect ratios, metadata storage) remains unchanged

### C5: Thread Safety
- Dimension rounding and cropping logic must be thread-safe
- Must respect existing `_generate_lock` in FluxInferenceEngine
- No race conditions when multiple generations occur concurrently

## Integration Points

### IP1: FluxInferenceEngine
- Location: `textbrush/inference/flux.py`, `generate()` method (lines 130-208)
- Changes: Add dimension rounding before pipeline call, add cropping before returning GenerationResult
- Existing behavior: Dimension resolution, seed handling, generator initialization

### IP2: BufferedImage Dataclass
- Location: `textbrush/buffer.py`, lines 17-35
- Changes: Add `generated_width` and `generated_height` fields
- Existing behavior: Stores image, seed, prompt, model_name, aspect_ratio

### IP3: Backend Metadata Storage
- Location: `textbrush/backend.py`, `_save_with_metadata()` method (lines 216-257)
- Changes: Add GeneratedWidth and GeneratedHeight to PNG tEXt chunks
- Existing behavior: Saves PNG with AspectRatio, Width, Height, Prompt, Model, Seed

### IP4: UI Metadata Display
- Location: `src-tauri/ui/main.ts`, `updateMetadataPanel()` function (lines 474-505)
- Changes: Populate two new dimension fields from payload
- Existing behavior: Displays prompt, model, seed, path

### IP5: UI HTML Structure
- Location: `src-tauri/ui/index.html`, metadata panel (lines 121-136)
- Changes: Add two new `<dt>`/`<dd>` pairs for generated and final dimensions
- Existing behavior: 2-column grid layout with 4 existing metadata fields

### IP6: TypeScript Types
- Location: `src-tauri/ui/types.ts`
- Changes: Add `generated_width?: number` and `generated_height?: number` to ImagePayload/DisplayPayload
- Existing behavior: Defines interfaces for image data flow

### IP7: IPC Protocol
- Location: `textbrush/ipc/handler.py` and `textbrush/ipc/protocol.py`
- Changes: Include generated dimensions in ImageReadyEvent if needed
- Existing behavior: Transmits image_data, seed, prompt, model_name to UI

## User Preferences

### UP1: Transparency Over Abstraction
- User prefers full visibility into what's happening (both dimension sets displayed)
- Users should understand why generated dimensions differ from requested dimensions
- Metadata should tell the complete story of how the image was produced

### UP2: Center Cropping
- User prefers center cropping to preserve subject matter in the center
- This is more aesthetically pleasing than edge cropping

### UP3: Centralized Logic
- User prefers dimension rounding in the inference engine (single source of truth)
- Avoids duplication and ensures consistency across all code paths

## Codebase Context

See `.exploration/flux-dimension-alignment-context.md` for detailed exploration findings including:
- Current dimension resolution patterns
- Metadata flow through BufferedImage
- PNG tEXt chunk usage
- UI metadata panel structure
- Key integration points and files

## Related Artifacts

- **Exploration Context**: `.exploration/flux-dimension-alignment-context.md`
- **Main Specification**: `specs/spec.md` (should be updated after implementation)
- **User Stories**: `user-stories.md` (should be updated after implementation)

## Out of Scope

### What This Feature Does NOT Include:

1. **JPEG EXIF Support**: This feature only adds metadata to PNG files using tEXt chunks. JPEG EXIF support remains a TODO (requires piexif library)

2. **Dimension Validation**: No validation that dimensions are reasonable (e.g., not too large for memory). Existing behavior is preserved.

3. **Smart Content-Aware Cropping**: Cropping uses simple center crop algorithm. No AI-based or content-aware cropping.

4. **Dimension Rounding for Other Models**: This feature is specific to FLUX.1 Schnell. Other inference engines (if added) must implement their own constraints.

5. **UI Configuration for Cropping Method**: Cropping method is fixed (center crop). No user configuration for alternative cropping strategies.

6. **Aspect Ratio Preservation Warnings**: No warnings if the final dimensions create a different aspect ratio than requested. This is implicit in the rounding behavior.

7. **Metadata Export/Import**: No functionality to export metadata to separate files or import metadata from external sources.

8. **Dimension History**: No tracking of dimension changes across multiple generations or sessions.

---

**Note**: This is a requirements specification, not an architecture design.
Edge cases, error handling details, and implementation approach will be
determined by the integration-architect during architecture design phase.
