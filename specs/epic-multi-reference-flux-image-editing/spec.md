---
epic: multi-reference-flux-image-editing
created: 2026-09-18T00:00:00+02:00
status: proposed
---

# Multi-Reference FLUX Image Editing — Feature Request Specification

## 1. Summary

Textbrush shall add a local image-editing workflow in which a user supplies a prompt and one to four reference images, then generates variations through a compatible FLUX model. The workflow shall be available in the desktop interface, the command-line interface, and headless operation while preserving the current buffered generation, review, acceptance, deletion, metadata, output, and cleanup behavior.

The first release shall support three distinct local model capabilities:

| Model | Mode | Reference-image count |
|---|---|---:|
| FLUX.1 schnell | Existing text-to-image generation | 0 |
| FLUX.1 Kontext [dev] | Prompt-directed reference editing | Exactly 1 |
| FLUX.2 [klein] 4B | Prompt-directed multi-reference editing | 1–4 |

FLUX.1 schnell text-to-image generation remains supported. Reference editing is an additional mode and requires at least one reference image.

## 2. Problem and Motivation

Textbrush currently generates images from text with FLUX.1 schnell. Users cannot supply visual source material when they need a generated image to retain or reinterpret a person, character, object, style, palette, setting, or composition.

The requested workflow lets users select up to four images as equal, untyped references and describe the desired result in natural language. Textbrush passes the references and prompt to the selected model without assigning semantic roles or resolving conflicts itself. This preserves the app’s fast local review workflow while adding prompt-directed visual editing and composition.

## 3. Goals

The first release shall:

1. Support local prompt-directed editing with one reference through FLUX.1 Kontext [dev].
2. Support local prompt-directed editing with one to four references through FLUX.2 [klein] 4B.
3. Retain existing FLUX.1 schnell text-to-image generation without requiring a reference.
4. Expose compatible model selection and reference-image selection in the desktop, CLI, and headless interfaces.
5. Treat all selected references equally: no reference roles, weights, masks, or app-authored interpretation.
6. Let the prompt direct identity preservation and describe how references should influence the result.
7. Apply acknowledged model and reference changes only to generations started after the change.
8. Keep inference local and preserve existing storage, review, acceptance, output, metadata, privacy, and cleanup conventions unless this specification explicitly extends them.

## 4. Non-Goals

The first release does not include:

- facial detection, facial recognition, subject detection, or content-aware cropping;
- automatic framing or cropping around a detected person or face;
- per-reference roles such as identity, style, pose, background, or composition;
- per-reference weights, priority, strength, or ordering controls;
- masks, inpainting, regional prompting, or manual crop tools;
- automatic prompt rewriting or app-side reconciliation of conflicting references;
- iterative editing in which a generated result automatically becomes a new reference or base image;
- cloud-hosted inference, remote generation APIs, or reference-image uploads to a service;
- changes to the current retained-image review, deletion, acceptance, or exit-code semantics;
- support for more than four references, even if a model can accept more;
- removal or behavioral regression of FLUX.1 schnell text-to-image generation.

A later release may add face-aware selection and cropping. The first release must not introduce hidden face analysis as preprocessing.

## 5. User Experience

### 5.1 Modes and model selection

The user shall be able to select among locally supported FLUX model variants in the desktop interface and with a CLI option. The selection shall make the model’s capability clear:

- **FLUX.1 schnell:** text to image; references are not accepted.
- **FLUX.1 Kontext [dev]:** image editing; exactly one reference is required.
- **FLUX.2 [klein] 4B:** image editing; one to four references are required.

Defaults are resolved by mode. With no references, Textbrush retains FLUX.1 schnell as the text-to-image default. With references, Textbrush prefers FLUX.2 [klein] 4B when it is locally available. One reference may use FLUX.1 Kontext or FLUX.2; every request with two to four references requires FLUX.2. Textbrush must never silently change an explicitly requested model, discard references, or reduce the number of references to make a request compatible.

If the current selection becomes incompatible—for example, a second reference is added while FLUX.1 Kontext is selected—the app shall keep the user’s references and require FLUX.2 [klein] 4B. It shall explain the compatibility requirement and provide the existing local model discovery/download path. Generation remains blocked until the user selects or installs a compatible model or changes the reference set.

### 5.2 Desktop reference selection

The desktop configuration area shall provide a native file-selection control for reference images. It shall:

- accept `.png`, `.jpg`, and `.jpeg` files;
- accept no more than four references;
- display each selected reference as a preview with its filename;
- allow an individual reference to be removed or replaced;
- preserve selection order internally for deterministic request construction, without exposing role or priority semantics;
- reject unsupported, unreadable, corrupt, or resource-constrained decode failures with a clear per-file error;
- make the active reference count and selected model compatibility visible;
- avoid copying or modifying the user’s source files.

The upload control is available for editing-capable models. FLUX.1 schnell cannot generate while references are active; the user must clear the reference selection or choose an editing-capable model.

### 5.3 Prompt behavior

A non-empty prompt remains required for every generation mode. In reference-editing mode, the prompt is the sole user-facing mechanism for stating how identities, characters, objects, styles, backgrounds, and compositions from the references should affect the result.

Textbrush shall not infer or assign reference roles, prepend hidden role instructions, promise identity fidelity, or resolve contradictory references. The selected model determines how it interprets the prompt and reference set.

### 5.4 Paused configuration changes

Model changes and reference additions, removals, or replacements are allowed only while generation is paused. Controls that would change either are disabled while the backend is loading, generating, or applying another configuration update. Prompt and output-preset changes retain the app’s existing update behavior.

After a valid paused-state update is acknowledged by the backend:

- images already delivered to the review history remain unchanged;
- completed images still waiting in the backend buffer follow the app’s existing configuration-update clearing behavior;
- generations started after acknowledgement use the new model or reference set;
- an in-flight generation finishes under its original immutable configuration or is cancelled through existing cancellation behavior; it must never receive a partially changed reference set.

The frontend shall wait for backend acknowledgement and shall not present a model or reference set as active optimistically.

### 5.5 Output presets

Reference-editing mode shall replace the current aspect-ratio list with two named output orientations, each with three selectable resolution tiers:

| Orientation | Small | Medium | Large |
|---|---:|---:|---:|
| Landscape (4:3) | 512×384 | 768×576 | 1024×768 |
| Portrait (3:4) | 384×512 | 576×768 | 768×1024 |

The six presets above shall be available through the app’s existing preset-selection interaction. These dimensions describe the generated output and are independent of reference-image dimensions. This feature does not prescribe which of the six editing presets is initially selected.

Text-only FLUX.1 schnell mode retains its current aspect-ratio and resolution options. Switching modes restores the most recently acknowledged preset for that mode during the current session.

### 5.6 Review and acceptance

Generated edits enter the existing buffer and image-history workflow. Navigation, pause/resume, skip, delete, accept, abort, retained-image ordering, output paths, stdout, and exit codes continue to behave as they do for text-to-image generations.

Changing the active configuration does not remove or relabel earlier results. While a result remains in the session’s review history, its session record remains associated with the configuration that generated it. Persisted file metadata remains format-specific as defined in Section 10.

## 6. Reference Image Processing

### 6.1 Source preservation

Textbrush shall open references read-only. It shall not overwrite, rename, relocate, or persistently copy source images. Any normalized working data follows the app’s current temporary-storage lifecycle and is removed through its existing best-effort cleanup behavior.

### 6.2 First-release normalization

The first release shall preserve the complete visible content of each reference and shall not crop it. Before inference, Textbrush may perform only the normalization required to provide a valid model input:

1. apply the file’s EXIF orientation;
2. decode the image and convert it to the model pipeline’s supported RGB representation;
3. resize it uniformly when required by the selected model or available local resources, using the same scale factor on both axes;
4. when a fixed rectangular tensor is required, use deterministic centered padding with a documented neutral fill rather than crop visible content;
5. retain the original aspect ratio through normalization.

Normalization must retain every source pixel’s visible contribution, introduce no geometric distortion, and produce model-compatible dimensions. It must be deterministic for the same source bytes, selected model, and application version. It must not run facial recognition or choose a subject-dependent crop.

If a source image cannot be normalized within the available resources, Textbrush shall reject the generation with an actionable error rather than silently crop, stretch, omit, or substitute the image.

### 6.3 Reference ordering and equality

References are passed to FLUX.2 in their stable selection order because model interfaces consume an ordered list. Textbrush provides no semantic claim that earlier items have greater weight. Reordering is not a first-release user control; removing and reselecting files is sufficient to construct a different list.

## 7. CLI and Headless Contracts

### 7.1 Arguments

The CLI shall add:

- `--model <model>` to select `flux1-schnell`, `flux1-kontext-dev`, or `flux2-klein-4b`;
- repeatable `--reference <path>` arguments, preserving command-line order;
- editing preset selection that can express all six specified landscape and portrait dimensions through an extension of the current dimension controls.

The existing prompt, output, seed, format, verbose, headless, auto-accept, and auto-abort behavior remains available. Existing text-only invocations that do not specify `--model` or `--reference` remain valid.

### 7.2 Validation

Validation shall occur before loading a model or starting generation:

- `flux1-schnell` requires zero references;
- `flux1-kontext-dev` requires exactly one reference;
- `flux2-klein-4b` requires one to four references;
- references must be readable local files with supported extensions;
- editing presets are valid only for editing-capable models;
- current text-only aspect-ratio options remain valid for FLUX.1 schnell;
- a prompt must be non-empty;
- an explicitly requested unavailable model must not be replaced automatically.

Validation failures shall identify the invalid argument or file, write no accepted output path to stdout, avoid starting inference, and return the app’s existing error exit behavior.

### 7.3 Default model resolution

When `--model` is omitted:

1. With two to four references, select locally available FLUX.2 [klein] 4B; if unavailable, block and direct the user to its download flow.
2. With exactly one reference, prefer locally available FLUX.2 [klein] 4B, then locally available FLUX.1 Kontext [dev]. If neither is available, block and direct the user to install a compatible model.
3. With no references, preserve the existing FLUX.1 schnell text-to-image default unless the user explicitly selects another valid text-to-image-capable model mode.

Headless operation follows the same model selection, validation, inference, metadata, output, and cleanup rules as interactive operation. It must not require a graphical file chooser or UI acknowledgement.

## 8. Local Model Management

Textbrush shall discover FLUX.1 Kontext [dev] and FLUX.2 [klein] 4B through the same local Hugging Face cache and configured model-directory mechanisms used for FLUX.1 schnell.

For each supported model, the app shall extend current discovery and download behavior to distinguish an available model from a model that cannot be used. Errors shall identify whether the model is absent, inaccessible because credentials or license access are missing, incomplete, or unable to load on the current system when that cause is known.

When a required model is absent, Textbrush shall use its existing download behavior: offer or perform a download only when credentials and model-license access permit it, and otherwise block generation with instructions that identify the required model and missing prerequisite. Generation and reference handling remain local.

The model selector shall not describe a checkpoint as available until discovery has validated its required local files. A failed switch shall leave the last acknowledged model configuration active.

## 9. State and Inference Semantics

A generation request shall capture an immutable snapshot containing at least:

- prompt;
- selected model identifier and model version/checkpoint identity;
- ordered reference set;
- session-local source identity sufficient to bind the selected files to the request;
- output orientation and dimensions;
- seed and other existing generation settings.

The backend remains the source of truth. The reference set associated with an enqueued or executing request cannot change in place. Configuration acknowledgement must report enough state for the frontend to render the active model, active reference count, and active preset accurately.

The existing buffer may contain outputs produced with different acknowledged configurations. Each output is independently attributable to its own snapshot. Pause, abort, shutdown, deletion, and cleanup must release decoded reference data and model-specific resources without deleting source files.

## 10. Metadata, Storage, and Privacy

Accepted images, preview images, source references, and temporary files shall retain the app’s current storage and cleanup behavior. Source references remain external files and are not copied into accepted output directories.

Generated outputs retain the current format-specific metadata behavior. Existing metadata continues to record the prompt, actual selected model, seed, aspect ratio, and dimensions for PNG output. JPEG output remains without embedded custom metadata. This first release does not persist reference paths, filenames, hashes, fingerprints, or source bytes in generated files. Any reference identity needed to keep runtime history correct remains session-local.

Inference and reference handling remain local. This feature does not introduce telemetry, remote reference storage, or a remote inference API.

## 11. Errors and Recovery

The app shall provide actionable errors for at least:

- no reference supplied to an editing model;
- a reference supplied to FLUX.1 schnell;
- more than one reference supplied to FLUX.1 Kontext;
- more than four references supplied to FLUX.2;
- multiple references supplied when FLUX.2 is unavailable;
- missing, unreadable, corrupt, unsupported, or resource-constrained image files;
- normalization failure;
- missing, incomplete, gated, or unloadable model weights;
- insufficient memory or unsupported local hardware;
- a model/reference change attempted while generation is not paused;
- backend rejection or failure while applying a paused-state update.

Operational errors must not corrupt existing history or discard the last acknowledged configuration. Where recovery is possible, the user can pause, correct the model or reference selection, and resume. Fatal model-load or resource failures use the current fatal-error presentation and exit behavior.

## 12. Accessibility and Interaction Requirements

Reference controls shall be keyboard accessible and expose programmatic labels for selecting, previewing, replacing, and removing files. Compatibility and validation errors must be available as text and must not rely on color alone. Preview images require accessible names derived from their filenames and positions, without claiming inferred image content.

All new controls shall follow the existing focus, theme, font-size, disabled-state, and backend-acknowledgement conventions. The layout must remain usable within the app’s supported desktop window sizes when four previews are selected.

## 13. Compatibility and Migration

- Existing CLI text-to-image commands remain valid and retain their current defaults.
- Existing configuration files remain readable without new required fields.
- New model and editing defaults are additive and receive safe defaults when absent.
- Existing generated images remain readable and display their current metadata without requiring new fields.
- Existing FLUX.1 schnell installations continue to work without downloading an editing model until editing is requested.
- The app must not report multi-reference support for FLUX.1 Kontext or text-only FLUX.1 schnell.

## 14. Acceptance Criteria

**AC-MODEL-1** — Given no references and FLUX.1 schnell, Textbrush completes the existing text-to-image workflow without requiring an editing model or changing its established aspect-ratio options.

**AC-MODEL-2** — Given exactly one valid reference and FLUX.1 Kontext [dev], Textbrush passes that reference and the user’s prompt to the local Kontext pipeline and returns the generated result through the existing review or headless output flow.

**AC-MODEL-3** — Given any ordered set of one, two, three, or four valid references and FLUX.2 [klein] 4B, Textbrush passes every reference exactly once, in stable selection order, with the user’s prompt to the local FLUX.2 pipeline.

**AC-MODEL-4** — For every invalid model/reference cardinality, validation blocks inference and reports the required count without silently dropping, duplicating, composing, or substituting references.

**AC-MODEL-5** — When FLUX.2 [klein] 4B is locally available it is preferred for reference editing; an explicit model selection is never silently replaced, and two-to-four-reference requests never fall back to FLUX.1.

**AC-INPUT-1** — The desktop interface accepts valid readable PNG and JPEG references through file selection, displays up to four previews and filenames, and supports individual removal and replacement.

**AC-INPUT-2** — CLI and headless invocations accept repeatable ordered `--reference` paths and enforce the same file and cardinality rules as the desktop workflow before model load.

**AC-INPUT-3** — Unsupported extensions, missing files, unreadable files, corrupt files, and decode resource failures produce an actionable error and do not start generation.

**AC-PROCESS-1** — For reference images across supported orientations and dimensions, normalization applies EXIF orientation, RGB conversion, and uniform scaling while retaining all visible source content, preserving aspect ratio, and introducing no geometric distortion; no application-level crop or facial analysis occurs.

**AC-PROCESS-2** — When proportional resizing alone cannot satisfy a rectangular model input, padding preserves all source content. Resource failure produces an error rather than a crop, stretch, omitted reference, or silent down-selection.

**AC-PRESET-1** — Editing mode offers the six specified 4:3 and 3:4 presets and generates an output with the selected requested dimensions subject only to existing model-alignment handling.

**AC-STATE-1** — Model and reference controls cannot apply changes outside the paused state. After backend acknowledgement, generations started later use the new immutable configuration, delivered history retains its original configuration, and completed images still pending in the backend buffer follow the current buffer-clearing behavior.

**AC-STATE-2** — Across sequences of pause, valid configuration update, resume, generation completion, navigation, and deletion, every displayed result’s session record retains the prompt, model, seed, and dimensions from the single snapshot that generated it without exposing or persisting its source references; persisted outputs follow AC-META-1. Spans modules: desktop UI, IPC, backend state, worker, inference, metadata.

**AC-STATE-3** — A rejected or failed configuration update leaves the last acknowledged model, references, and preset active in both backend and UI.

**AC-STORAGE-1** — Source files remain byte-for-byte unchanged and are never copied into accepted output directories. Temporary normalized data follows existing cleanup behavior on accept, abort, fatal error, and normal shutdown.

**AC-META-1** — PNG output preserves the current embedded metadata fields and records the actual selected model; JPEG output preserves the current no-custom-metadata behavior. Neither format embeds reference paths, filenames, hashes, fingerprints, or source bytes.

**AC-LOCAL-1** — All reference decoding, normalization, inference, runtime request tracking, and output generation occurs locally. Network access is limited to the existing authorized model-download flow.

**AC-DISCOVERY-1** — Model discovery and loading provide an actionable unavailable or load-failure message, including missing credentials or license access when known, and prevent an invalid generation attempt.

**AC-RECOVERY-1** — Any recoverable reference, compatibility, normalization, or configuration error preserves existing image history and allows correction while paused. Fatal failures follow the existing fatal-error contract without emitting an accepted path.

**AC-ACCESS-1** — All new desktop controls can be operated by keyboard, expose accessible labels, present errors as text, honor existing theme and font-size behavior, and remain usable with four previews at supported window sizes.

**AC-COMPAT-1** — Existing configuration files, generated images, and text-only CLI invocations remain usable without supplying new fields or downloading a reference-editing model.

## 15. Verification Expectations

Implementation verification shall include:

- unit tests for model/reference cardinality, preset mapping, immutable snapshots, metadata behavior, and deterministic normalization decisions;
- parameterized tests over reference counts, file orderings, pause/update/resume sequences, and supported source dimensions;
- mocked inference contract tests proving the exact ordered references and prompt passed to each model pipeline;
- IPC integration tests proving acknowledged state and per-result provenance across configuration changes;
- CLI and headless tests for valid and invalid combinations, stdout, exit behavior, and unavailable models;
- desktop interaction tests for file selection, previews, removal, replacement, disabled states, rollback after rejection, keyboard access, and four-preview layout;
- cleanup tests across accept, abort, fatal error, and shutdown;
- a local smoke test for each editing model on supported hardware when the gated weights are available, without making that hardware-dependent run a prerequisite for fast unit tests.

Visual similarity and identity preservation are model-dependent and are not binary product acceptance criteria. Verification must establish that Textbrush supplies the intended prompt, complete reference set, and settings without app-side loss or reinterpretation.

## 16. Release and Documentation Requirements

The feature shall be documented for both desktop and CLI users, including:

- the differences among schnell, Kontext, and FLUX.2 editing capabilities;
- supported reference counts and formats;
- the six editing output presets;
- examples for one-reference Kontext and multi-reference FLUX.2 usage;
- local model storage, gated-license, credential, hardware, and memory expectations;
- the fact that prompt wording controls identity and reference use, with no guaranteed identity fidelity;
- local-only processing and the metadata privacy policy;
- first-release limitations and the later face-aware-cropping direction.

Release notes shall describe this as an additive editing workflow and call out FLUX.2 as required for two to four references.
