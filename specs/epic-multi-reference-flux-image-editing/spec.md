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

Defaults are resolved by mode at launch only. With no references, Textbrush retains FLUX.1 schnell as the text-to-image default. The default-model resolution in §7.3 applies to launch-time invocation — CLI arguments and startup configuration — and never runs again mid-session: the desktop never auto-switches the selected model in response to a reference change. Where this specification says Textbrush *prefers* FLUX.2 [klein] 4B for reference editing, that preference is expressed by naming and pre-highlighting FLUX.2 as the recommended target in the compatibility message and the model selector; performing the switch requires the user's action and backend acknowledgement. One reference may use FLUX.1 Kontext or FLUX.2; every request with two to four references requires FLUX.2. Textbrush must never silently change an explicitly requested model, discard references, or reduce the number of references to make a request compatible.

The model and the reference set are acknowledged **independently**. An update that is individually valid — a readable, decodable reference; a model whose weights load — is acknowledged even when the resulting *combination* is incompatible. This is what lets the app keep the user's references exactly as selected while still reflecting only backend-held state in the UI.

Model/reference cardinality compatibility is evaluated when generation is about to start — at resume, and at launch before a model is loaded — not when an individual update is applied. The acknowledgement payload carries an explicit compatibility flag and, when incompatible, the reason and the required model. While the configuration is incompatible, resume is refused with that reason and no generation starts; the app explains the compatibility requirement and provides the existing local model discovery/download path. Generation remains blocked until the user selects or installs a compatible model or changes the reference set. Loading a model that is incompatible with the current reference count may be deferred until the configuration becomes compatible.

An update is *rejected* — as distinct from acknowledged-and-incompatible — only when it cannot be applied at all: an unreadable, unsupported, corrupt, or unnormalizable reference file; a model whose weights are missing, gated, incomplete, or fail to load; or an attempt to change the model or reference set outside the paused state. A rejected update leaves the last acknowledged configuration active, per §5.4.

### 5.2 Desktop reference selection

The desktop configuration area shall provide a native file-selection control for reference images. It shall:

- accept `.png`, `.jpg`, and `.jpeg` files, matching the extension case-insensitively so that the common camera form `IMG_1234.JPG` is accepted;
- accept no more than four references;
- display each selected reference as a preview with its filename;
- allow an individual reference to be removed or replaced;
- preserve selection order internally for deterministic request construction, without exposing role or priority semantics;
- reject unsupported, unreadable, corrupt, or resource-constrained decode failures with a clear per-file error;
- make the active reference count and selected model compatibility visible;
- avoid copying or modifying the user’s source files.

The upload control is available for editing-capable models. FLUX.1 schnell cannot generate while references are active; the user must clear the reference selection or choose an editing-capable model.

The native file dialog shall be separable from the selection logic behind it: the dialog's only responsibility is to yield a list of paths, and everything downstream — cardinality checks, per-file validation, preview construction, removal, and replacement — shall operate on a supplied path list. This keeps the selection behavior verifiable without driving a native dialog, which no available test harness can automate.

### 5.3 Prompt behavior

A non-empty prompt remains required for every generation mode. In reference-editing mode, the prompt is the sole user-facing mechanism for stating how identities, characters, objects, styles, backgrounds, and compositions from the references should affect the result.

Textbrush shall not infer or assign reference roles, prepend hidden role instructions, promise identity fidelity, or resolve contradictory references. The selected model determines how it interprets the prompt and reference set.

### 5.4 Paused configuration changes

Model changes and reference additions, removals, or replacements are allowed only while generation is paused. Controls that would change either are disabled while the backend is loading, generating, or applying another configuration update. Prompt and output-preset changes retain the app’s existing update behavior.

**Paused means quiescent.** A pause request that arrives mid-generation does not stop the generation already running. Textbrush shall therefore report the paused state as ready to accept a model or reference change only once the generation loop has actually come to rest — either by carrying a distinct settled indication in the paused state, or by withholding the paused report until the worker has blocked. Model and reference controls are enabled on that signal, never on the mere request to pause. Without this, the frontend would offer controls the backend must then refuse, producing the very not-paused error §11 lists.

After a valid paused-state update is acknowledged by the backend:

- images already delivered to the review history remain unchanged;
- completed images still waiting in the backend buffer follow the app’s existing configuration-update clearing behavior;
- generations started after acknowledgement use the new model or reference set;
- an in-flight generation finishes under its original immutable configuration; it must never receive a partially changed reference set. Because that result would otherwise arrive *after* the buffer was cleared and appear as the first image produced "under" the new configuration, a result whose generation began before an acknowledged model or reference change shall be discarded on completion rather than enqueued. This extends the existing configuration-update buffer-clearing behavior to results still in flight at the moment of the clear, and requires no per-generation cancellation mechanism.

Commands are serialized against an update in progress. A resume that arrives while a configuration update is being applied takes effect after acknowledgement: on success generation proceeds under the new configuration; on failure the app remains paused and surfaces the error. The frontend shall disable the pause/resume control while an update is being applied.

The frontend shall wait for backend acknowledgement and shall not present a model or reference set as active optimistically.

### 5.5 Output presets

Reference-editing mode shall replace the current aspect-ratio list with two named output orientations, each with three selectable resolution tiers:

| Orientation | Small | Medium | Large |
|---|---:|---:|---:|
| Landscape (4:3) | 512×384 | 768×576 | 1024×768 |
| Portrait (3:4) | 384×512 | 576×768 | 768×1024 |

The six presets above shall be available through the app’s existing preset-selection interaction. These dimensions describe the generated output and are independent of reference-image dimensions.

One of the six editing presets shall be documented as the default editing preset, and it shall be the same default in the desktop, CLI, and headless paths. When an editing-capable model is active and no editing preset has been explicitly selected, that default applies; the text-only aspect-ratio default must never be used as the fallback for an editing model. The acknowledgement reports the resulting active preset.

Text-only FLUX.1 schnell mode retains its current aspect-ratio and resolution options. Switching modes restores the most recently acknowledged preset for that mode during the current session.

Presets are validated in both directions: an editing preset is invalid for a text-to-image model, and a text-only aspect ratio is invalid for an editing-capable model. A mode switch is applied as a single atomic acknowledged update carrying the model, the reference set, and the preset together, so no intermediate state exists in which the active model and the active preset belong to different modes.

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
3. resize it uniformly when required by the selected model, using a scale factor that is exactly equal on both axes;
4. when a fixed rectangular tensor is required, reach the model's required dimensions by deterministic centered padding with a documented neutral fill value, never by resizing an axis independently — any remainder after the uniform scale is padding;
5. retain the original aspect ratio of the visible content region through normalization.

Normalization must retain every source pixel’s visible contribution, introduce no geometric distortion, and produce model-compatible dimensions. It must be deterministic for the same source bytes, selected model, and application version — the scale factor must not depend on available local resources, since a resource-dependent factor would make the same input produce different output on different runs. It must not run facial recognition or choose a subject-dependent crop.

"Aspect ratio preserved" refers to the visible content region, not to the padded canvas: the padded canvas necessarily has the model's required ratio. Sources carrying an alpha channel are composited onto the same documented neutral fill before conversion, so that transparency never becomes an undefined colour.

**The guarantee must hold at the model boundary, not merely at the application boundary.** Model pipelines commonly apply their own reference-image resizing — bucketing to a preferred resolution, or per-axis rounding to a required multiple — which would silently undo the no-crop, no-distortion guarantee this section makes. Textbrush shall therefore hand each pipeline references that it accepts unchanged, and shall disable or bypass any pipeline-internal reference resizing. A normalization that is correct in isolation but is re-scaled downstream does not satisfy this section.

If a source image cannot be normalized within the available resources, Textbrush shall reject the generation with an actionable error rather than silently crop, stretch, omit, or substitute the image.

### 6.3 Decode timing and lifetime

Each reference is decoded and normalized **once, when the configuration is acknowledged**, not per generation. The normalized data is held for the lifetime of that acknowledged configuration and released when the configuration changes, or on abort, fatal error, and shutdown, per §9.

Two consequences follow. First, unreadable, corrupt, unsupported, and unnormalizable files are detected at acknowledgement time and make the update a rejection on the §5.4 rollback path — not an error raised repeatedly inside the generation loop. Second, a source file that is edited, moved, or deleted after acknowledgement has no effect on the session: the reference in force is the one that was decoded, which is what makes the §9 snapshot immutable and §6.2 normalization deterministic in practice rather than only in principle.

### 6.4 Reference ordering and equality

References are passed to FLUX.2 in their stable selection order because model interfaces consume an ordered list. Textbrush provides no semantic claim that earlier items have greater weight. Reordering is not a first-release user control; removing and reselecting files is sufficient to construct a different list. Selecting the same file more than once is permitted: each occurrence is passed to the model as a distinct entry in selection order, and cardinality limits count occurrences rather than distinct paths. Textbrush does not deduplicate, reorder, or warn about repeated references, consistent with its refusal to reinterpret the reference set.

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
- references must be readable local files with supported extensions, matched case-insensitively;
- editing presets are valid only for editing-capable models, and text-only aspect-ratio options are invalid for editing-capable models — validation applies in both directions;
- current text-only aspect-ratio options remain valid for FLUX.1 schnell;
- a prompt must be non-empty;
- an explicitly requested unavailable model must not be replaced automatically.

Validation failures shall identify the invalid argument or file, write no accepted output path to stdout, avoid starting inference, and return the app’s existing error exit behavior. Because these are scriptable contracts, reference, cardinality, and preset validation failures shall exit with the same status code the app already uses for an empty-prompt failure, rather than introducing a third convention alongside the existing argument-parsing and runtime-error codes.

### 7.3 Default model resolution

When `--model` is omitted:

1. With two to four references, select locally available FLUX.2 [klein] 4B; if unavailable, block and direct the user to its download flow.
2. With exactly one reference, prefer locally available FLUX.2 [klein] 4B, then locally available FLUX.1 Kontext [dev]. If neither is available, block and direct the user to install a compatible model.
3. With no references, preserve the existing FLUX.1 schnell text-to-image default. FLUX.1 schnell is the only text-to-image model in this release; there is no other text-to-image-capable selection to fall through to, and neither editing model may be used with zero references.

Headless operation follows the same model selection, validation, inference, metadata, output, and cleanup rules as interactive operation. It must not require a graphical file chooser or UI acknowledgement.

## 8. Local Model Management

Textbrush shall discover FLUX.1 Kontext [dev] and FLUX.2 [klein] 4B through the same local Hugging Face cache and configured model-directory mechanisms used for FLUX.1 schnell.

For each supported model, the app shall extend current discovery and download behavior to distinguish an available model from a model that cannot be used. So that "when that cause is known" cannot collapse into reporting every cause as unknown, the following causes are enumerated and each shall be reported as such:

- **absent** — no local marker for the checkpoint is present;
- **credentials missing** — no access token is configured;
- **license access missing** — the repository is gated, or access is refused as unauthorized or forbidden;
- **incomplete** — the marker is present but one or more declared components lack their configuration or weight files;
- **unloadable** — discovery succeeds but loading raises on the current system.

A cause may be reported as unknown only when it matches none of the above.

When a required model is absent, Textbrush shall use its existing download behavior: offer or perform a download only when credentials and model-license access permit it, and otherwise block generation with instructions that identify the required model and missing prerequisite. Generation and reference handling remain local.

The model selector shall not describe a checkpoint as available until discovery has validated its required local files. **Required local files** means the checkpoint's top-level index plus, for each component the index declares, that component's configuration and weight files — a single top-level marker file is not sufficient evidence of availability.

A model that discovery reports as locally available shall be loaded from local files only, without contacting a remote host to revalidate. Network access belongs to the download flow alone.

A failed switch shall leave the last acknowledged model configuration active, where **active** means loaded and ready — not merely selected. Because loading two checkpoints simultaneously may exceed available memory, the backend may unload the current model before loading the next; if the new model then fails to load, it shall attempt to reload the previous one. The switch is recoverable, and §11's recovery path applies, when the previous model is still loaded or reloads successfully. Only if that reload also fails is the failure fatal.

## 9. State and Inference Semantics

A generation request shall capture an immutable snapshot containing at least:

- prompt;
- selected model identifier and model version/checkpoint identity;
- ordered reference set;
- session-local source identity sufficient to bind the selected files to the request;
- output orientation and dimensions;
- seed and other existing generation settings;
- the sampling settings in force for the selected model.

Sampling settings are per-model, not global. The step count and guidance appropriate to a few-step distilled text-to-image model are not appropriate to a guidance-distilled editing model, and reusing one model's defaults for another produces unusable output that every mocked test would still pass. Each supported model therefore carries its own documented default sampling settings, and the values actually used are part of the snapshot.

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

Operational errors must not corrupt existing history or discard the last acknowledged configuration. Where recovery is possible, the user can pause, correct the model or reference selection, and resume. A model switch that fails while the previously acknowledged model is still loaded, or that fails but whose predecessor reloads successfully, is recoverable in this sense and must not exit. Fatal model-load or resource failures — including a failed switch whose predecessor also fails to reload, leaving no model active — use the current fatal-error presentation and exit behavior.

## 12. Accessibility and Interaction Requirements

Reference controls shall be keyboard accessible and expose programmatic labels for selecting, previewing, replacing, and removing files. Compatibility and validation errors must be available as text and must not rely on color alone. Preview images require accessible names derived from their filenames and positions, without claiming inferred image content.

All new controls shall follow the existing focus, theme, font-size, disabled-state, and backend-acknowledgement conventions. The layout must remain usable within the app’s supported desktop window sizes when four previews are selected, where usable means that no control loses keyboard or pointer reachability and no preview is clipped by overflow.

These are rendering and focus properties, and static source inspection cannot establish them. They shall be verified against the real rendered interface in a headless browser, with the desktop bridge stubbed so no backend or native dialog is required. Asserting them by pattern-matching the source would be a structural proxy for a behavioral requirement, and does not satisfy this section.

## 13. Compatibility and Migration

- Existing CLI text-to-image commands remain valid and retain their current defaults.
- Existing configuration files remain readable without new required fields.
- New model and editing defaults are additive and receive safe defaults when absent.
- Existing generated images remain readable and display their current metadata without requiring new fields.
- Existing FLUX.1 schnell installations continue to work without downloading an editing model until editing is requested.
- The app must not report multi-reference support for FLUX.1 Kontext or text-only FLUX.1 schnell.
- The minimum supported version of the diffusers stack rises to one that provides both reference-editing pipelines; the currently pinned version predates them. "No FLUX.1 schnell regression" is a contract-level guarantee — the existing text-to-image path keeps its behavior, options, metadata, and exit semantics across that uplift — and is not a claim of pixel-identical output, which a library uplift cannot promise.

## 14. Acceptance Criteria

The acceptance criteria for this epic live in `acceptance-criteria.md` alongside this specification, together with the terminology they rely on and the verification plan. That file is the authoritative list; amendments to individual criteria are recorded there and in §17 below.

## 15. Verification Expectations

Implementation verification shall include:

- unit tests for model/reference cardinality, preset mapping, immutable snapshots, metadata behavior, and deterministic normalization decisions;
- parameterized tests over reference counts, file orderings, pause/update/resume sequences, and supported source dimensions;
- mocked inference contract tests proving the exact ordered references and prompt passed to each model pipeline, and proving that each pipeline is invoked with its internal reference resizing disabled or is handed references it accepts unchanged;
- IPC integration tests proving acknowledged state and per-result provenance across configuration changes;
- CLI and headless tests for valid and invalid combinations, stdout, exit behavior, and unavailable models;
- desktop interaction tests for file selection, previews, removal, replacement, disabled states, and rollback after rejection, driven through the path-injection seam of §5.2 rather than through the native dialog;
- rendered-interface tests in a headless browser, with the desktop bridge stubbed, for keyboard reachability and the four-preview layout at supported window sizes;
- a locality test establishing that engine load, reference normalization, and generation complete with no network access when the local cache is present and outbound connections are refused;
- cleanup tests across accept, abort, fatal error, and shutdown;
- a local smoke test for each editing model on supported hardware when the gated weights are available, without making that hardware-dependent run a prerequisite for fast unit tests. The smoke test shall include one reference whose aspect ratio does not match any resolution the pipeline prefers, and shall confirm the dimensions the model actually consumed. This test is a release gate: it is the only check that can observe a model receiving distorted input or unusable sampling settings, both of which every mocked test passes.

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

## 17. Amendments

- **2026-09-18 — Acceptance criteria extracted.** The acceptance criteria previously inlined in
  §14 were moved verbatim into `acceptance-criteria.md`, matching the convention used by every
  other feature epic in `specs/` and the layout `base:spec-template` defines. §14 now points to
  that file. No criterion's wording changed in the move.
- **2026-09-18 — Duplicate references resolved as permitted (AC-INPUT-4).** The specification did
  not state whether the same source file could appear more than once in a reference set. Resolved
  in favour of pass-through: duplicates are accepted and forwarded once per occurrence, with no
  deduplication or warning. Recorded in §6.3 and as AC-INPUT-4. This does not weaken AC-MODEL-4,
  which forbids *Textbrush* from duplicating references to satisfy a cardinality rule; it governs
  only references the *user* deliberately repeats.
- **2026-09-18 — Adversarial spec review applied (18 findings).** An adversarial review pass, distinct from
  the completeness validation, found three load-bearing problems and fifteen smaller ones. All were resolved
  against the specification's own stated principles; none required a change of intent. The three substantive
  ones:
  - **Reference fidelity had to be moved to the model boundary.** §6.2 guaranteed no crop and no distortion,
    but model pipelines apply their own reference resizing internally, which would silently undo a correct
    normalization with no test able to observe it. §6.2 now requires that pipeline-internal resizing be
    disabled or unnecessary, and AC-MODEL-2/AC-MODEL-3 assert it.
  - **"Paused" did not mean quiescent.** A pause request does not stop an already-running generation, so the
    result of that generation would arrive after the buffer was cleared and appear as the first image produced
    under the new configuration. §5.4 now requires the paused state to be reported only once the generation
    loop has come to rest, and requires results from pre-change generations to be discarded rather than
    enqueued. The clause relying on a per-generation cancellation mechanism was struck, as no such mechanism
    exists.
  - **Incompatible selections were specified two ways.** §5.1 described them as acknowledged-and-blocked while
    §7.2 and AC-STATE-3 described them as rejected-and-rolled-back; the two yield materially different desktop
    behavior. Resolved in favour of §5.1: the model and reference set are acknowledged independently,
    compatibility is evaluated at generation start, and resume is refused while incompatible. AC-STATE-3 is now
    bounded to genuine application failures, and the new AC-STATE-4 covers the acknowledged-and-incompatible
    path.
  The remaining findings tightened determinism (§6.2 no longer scales by available resources), decode timing
  (new §6.3 — decode once at acknowledgement; ordering moved to §6.4), per-model sampling defaults (§9, new
  AC-MODEL-6), model-switch recoverability (§8/§11), discovery cause reporting and the meaning of "required
  local files" (§8, AC-DISCOVERY-1), locality as a falsifiable property (AC-LOCAL-1), accessibility verified
  against a rendered interface rather than by source inspection (§12, AC-ACCESS-1), case-insensitive extension
  matching, the validation exit code, both-direction preset validation with an atomic mode switch, the removal
  of a clause referring to a text-to-image model this release does not define, and the ML dependency floor
  (§13). AC-STATE-2's prohibition was narrowed from "exposing or persisting" to "persisting", which is all the
  specification actually requires.
- **2026-09-18 — New acceptance criteria.** AC-MODEL-6 (per-model sampling defaults), AC-STATE-4
  (acknowledged-and-incompatible configurations), and AC-PROCESS-3 (decode-once timing and reference lifetime)
  were added to cover behavior the review found unspecified.
- **2026-09-18 — Documentation given an owner (AC-DOC-1, story S13).** §16 stated documentation and
  release-note requirements but carried no acceptance criterion, and the story split left it unowned.
  Because §16 had no AC, the end-of-epic AC-closure gate would not have caught the omission either —
  the epic could have shipped complete-by-its-own-gates with none of its required documentation written.
  Surfaced when a code review noticed `docs/configuration.md` had gone stale against S1's schema change.
  AC-DOC-1 now states the documentation contract and story S13 owns it. The narrower
  `docs/configuration.md` correction stays in S1, where the change that invalidated it originated.

