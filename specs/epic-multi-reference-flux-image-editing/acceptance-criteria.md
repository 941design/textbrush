# Acceptance Criteria: Multi-Reference FLUX Image Editing

Generated: 2026-09-18
Source: spec.md

## Terminology

- **Editing-capable model** — a model that accepts at least one reference image: FLUX.1 Kontext [dev] (exactly one) or FLUX.2 [klein] 4B (one to four). FLUX.1 schnell is not editing-capable.
- **Reference** / **reference set** — the ordered list of one to four user-selected source images passed to an editing-capable model. References are equal and untyped: no roles, weights, priority, or masks.
- **Paused state** — the application state in which the backend is neither loading, generating, nor applying another configuration update, and is therefore permitted to accept a model or reference change. A pause *request* does not by itself establish this state: an already-running generation continues to completion, so the state is reached only once the generation loop has come to rest (see spec.md §5.4).
- **Acknowledged configuration** — a model and reference set that the backend has confirmed as applied. The frontend never presents a configuration as active before acknowledgement.
- **Acknowledged-and-incompatible** — an acknowledged configuration whose model and reference count cannot generate together (for example two references with a one-reference model). The configuration is held as selected and generation is refused at resume; this is distinct from a **rejected** update, which is one that could not be applied at all and leaves the previous configuration in force.
- **Default editing preset** — the single documented editing preset applied when an editing-capable model is active and no editing preset has been explicitly chosen. Identical across desktop, CLI, and headless.
- **Snapshot** — the immutable capture of prompt, model identity, ordered reference set, session-local source identity, output orientation and dimensions, seed, and existing generation settings taken when a generation request is created.
- **Editing preset** — one of the six output orientations/resolutions defined in spec.md §5.5 (landscape 4:3 and portrait 3:4, each in small/medium/large).
- **Normalization** — the EXIF-orientation, RGB-conversion, uniform-resize, and centered-padding steps defined in spec.md §6.2. Normalization never crops visible content and never performs facial analysis.

## Criteria

### AC-MODEL-1
- **Description**: Given no references and FLUX.1 schnell, Textbrush completes the existing text-to-image workflow without requiring an editing model or changing its established aspect-ratio options.
- **Verification**: Regression test over the existing text-to-image path asserting no editing model is loaded and the current aspect-ratio option set is unchanged.
- **Type**: unit

### AC-MODEL-2
- **Description**: Given exactly one valid reference and FLUX.1 Kontext [dev], Textbrush passes that reference and the user's prompt to the local Kontext pipeline and returns the generated result through the existing review or headless output flow.
- **Verification**: Mocked inference contract test asserting the exact reference and prompt reaching the Kontext pipeline, that the pipeline is invoked with its internal reference resizing disabled (or is handed a reference at dimensions it accepts unchanged), and that the result is delivered through the existing output flow.
- **Type**: integration

### AC-MODEL-3
- **Description**: Given any ordered set of one, two, three, or four valid references and FLUX.2 [klein] 4B, Textbrush passes every reference exactly once, in stable selection order, with the user's prompt to the local FLUX.2 pipeline.
- **Verification**: Parameterized mocked-pipeline contract test over reference counts 1-4 and multiple orderings, asserting exact-once delivery, preserved order, and that pipeline-internal reference resizing is disabled or unnecessary.
- **Type**: integration

### AC-MODEL-4
- **Description**: For every invalid model/reference cardinality, validation blocks inference and reports the selected model together with that model's exact cardinality rule, without silently dropping, duplicating, composing, or substituting references. A message that states only a range spanning every model does not satisfy this.
- **Verification**: Parameterized validation test over every invalid (model, reference-count) pair asserting inference never starts and that the error names both the selected model and that model's exact cardinality rule.
- **Type**: unit
- **Note**: The prohibition on "duplicating" here constrains the *application* — Textbrush must never pad a reference set to satisfy a cardinality rule. It does not constrain the *user*, who may deliberately select the same file more than once (see AC-INPUT-4).

### AC-MODEL-5a
- **Description**: Resolver honesty. The default-model resolution function is pure: no module-level state, no memoization, availability supplied by injection rather than read internally, and cardinality bounds read from the model registry rather than restated as literals. Re-invoking it with a changed reference count returns a correspondingly different answer, so it can never report a stale resolution as current. Default resolution prefers FLUX.2 [klein] 4B for reference editing when locally available; an explicit model selection is never silently replaced; and two-to-four-reference requests never fall back to FLUX.1.
- **Verification**: Purity assertions (no module state, no caching, availability injected), a permutation table over spec.md §7.3 covering 0 / 1 / 2-4 references against each availability combination with the exact expected resolution per cell, and a test that an explicitly requested unavailable model blocks rather than substituting an available alternative.
- **Type**: unit
- **Owner**: S2 (`model`). **Status: satisfied.**

### AC-MODEL-5b
- **Description**: Call-site cardinality. Default-model resolution is invoked exactly once per session, at launch, and is never re-run in response to a reference-set change. Adding or removing a reference during a desktop session never auto-switches the active model — the app names and pre-highlights the required model and awaits the user's action and backend acknowledgement — and an explicit user selection survives a reference-count change that would otherwise flip the resolved model.
- **Verification**: A live session driven across at least two reference-count changes that cross the cardinality boundary which would flip the resolver's answer, with a call counter asserting exactly one invocation at initialization and zero thereafter, and the resolved model id unchanged throughout. Plus a structural test asserting the resolution function has exactly the enumerated set of production call sites, failing if a new caller appears.
- **Type**: integration
- **Owner**: S8, S9, S10. **Status: open — blocking those stories.**
- **Note**: Split from AC-MODEL-5 by amendment 2026-09-18 on a Decider ruling. The original bundled two guarantees with different owners into one criterion, so a fully-satisfied S2 scored PARTIAL against it. `resolve_model_selection` cannot prevent its own re-invocation; only its callers can. Making it self-defending (a once-flag or cached state) would destroy the purity AC-MODEL-5a requires.


### AC-INPUT-1
- **Description**: The desktop interface accepts valid readable PNG and JPEG references through file selection, displays up to four previews and filenames, and supports individual removal and replacement.
- **Verification**: Desktop interaction tests driving the selection logic through its path-injection seam (a supplied path list, not the native dialog) for preview and filename rendering, individual removal, and individual replacement.
- **Type**: e2e

### AC-INPUT-2
- **Description**: CLI and headless invocations accept repeatable ordered `--reference` paths and enforce the same file and cardinality rules as the desktop workflow before model load. Reference, cardinality, and preset validation failures exit with the same status code the app already uses for an empty-prompt failure.
- **Verification**: CLI tests over valid and invalid combinations asserting order preservation and that validation precedes model load.
- **Type**: integration

### AC-INPUT-3
- **Description**: Unsupported extensions, missing files, unreadable files, corrupt files, and decode resource failures produce an actionable error and do not start generation. Supported extensions are matched case-insensitively, so an uppercase `.JPG` is accepted rather than reported as unsupported.
- **Verification**: Parameterized test over each failure class asserting an actionable per-file error and that inference never starts.
- **Type**: unit

### AC-INPUT-4
- **Description**: The same source file selected or passed more than once within a reference set is accepted and forwarded to the model in its selection order, once per occurrence, with no deduplication, reordering, warning, or app-side reinterpretation. Cardinality rules count occurrences, not distinct paths.
- **Verification**: Contract test passing a duplicated path in both desktop and CLI reference sets, asserting the pipeline receives the duplicate as a distinct ordered occurrence.
- **Type**: integration
- **Note**: Added by amendment 2026-09-18; resolves a gap in spec.md §5.2/§6.4/§7.2. Consistent with the spec's "no app-side roles, weights, or reconciliation" principle.

### AC-PROCESS-1
- **Description**: For reference images across supported orientations and dimensions, normalization applies EXIF orientation, RGB conversion, and uniform scaling while retaining all visible source content, preserving aspect ratio, and introducing no geometric distortion; no application-level crop or facial analysis occurs.
- **Verification**: Parameterized normalization tests over supported source dimensions and EXIF orientations asserting that the scale factor is exactly equal on both axes, that the visible content region retains its original aspect ratio (measured on the content region, not the padded canvas), and that all content is retained. A per-axis rounding that introduces even a few pixels of stretch fails this.
- **Type**: unit

### AC-PROCESS-2
- **Description**: When proportional resizing alone cannot satisfy a rectangular model input, the remainder is reached by deterministic centered padding with the documented neutral fill value, never by resizing an axis independently; sources with an alpha channel are composited onto that same fill. Normalization is deterministic for the same source bytes, selected model, and application version, and never varies with available resources. Resource failure produces an error rather than a crop, stretch, omitted reference, or silent down-selection.
- **Verification**: Tests asserting deterministic centered padding with the documented neutral fill, identical output across repeated runs of the same input, correct compositing of an alpha-channel source, and that an unnormalizable source raises an actionable error instead of degrading the image.
- **Type**: unit

### AC-PRESET-1
- **Description**: Editing mode offers the six specified 4:3 and 3:4 presets and generates an output with the selected requested dimensions subject only to existing model-alignment handling. Preset validation applies in both directions: an editing preset is rejected for a text-to-image model and a text-only aspect ratio is rejected for an editing-capable model. An editing model selected without an explicit preset uses the documented default editing preset — the same one in desktop, CLI, and headless — never the text-only default. A mode switch is applied as one atomic acknowledged update, so no observable state pairs a model with a preset from the other mode.
- **Verification**: Preset-mapping tests over all six presets asserting requested output dimensions, composed with the existing dimension-alignment behavior.
- **Type**: unit

### AC-STATE-1
- **Description**: Model and reference controls cannot apply changes outside the paused state, and are enabled only once the generation loop has actually come to rest — not merely once a pause was requested. After backend acknowledgement, generations started later use the new immutable configuration, delivered history retains its original configuration, and completed images still pending in the backend buffer follow the current buffer-clearing behavior. A generation that began before the acknowledged change is discarded on completion rather than enqueued, so no image produced under the previous model or reference set can appear as the first result after the change. A resume arriving while an update is being applied takes effect only after acknowledgement.
- **Verification**: IPC integration tests over pause/update/resume sequences asserting rejection outside the paused state, that controls become available only on the settled signal, that a result from a pre-change generation never reaches the buffer or the review history, and that a resume issued mid-update is honoured only after acknowledgement.
- **Type**: integration

### AC-STATE-2
- **Description**: Across sequences of pause, valid configuration update, resume, generation completion, navigation, and deletion, every displayed result's session record retains the prompt, model, seed, and dimensions from the single snapshot that generated it without persisting its source references; persisted outputs follow AC-META-1. Spans modules: desktop UI, IPC, backend state, worker, inference, metadata.
- **Verification**: IPC integration tests proving per-result provenance across configuration changes, combined with a metadata assertion that no reference identity is persisted.
- **Type**: integration

### AC-STATE-3
- **Description**: A rejected or failed configuration update leaves the last acknowledged model, references, and preset active in both backend and UI. Rejection is limited to updates that cannot be applied at all: an unreadable, unsupported, corrupt, or unnormalizable reference file; a model whose weights are missing, gated, incomplete, or fail to load; or a change attempted outside the paused state. An individually valid update that merely produces an incompatible model/reference combination is acknowledged rather than rejected, and is governed by AC-STATE-4.
- **Verification**: Rollback tests injecting backend rejection and failure asserting both backend state and UI return to the last acknowledged configuration.
- **Type**: integration

### AC-STORAGE-1
- **Description**: Source files remain byte-for-byte unchanged and are never copied into accepted output directories. Temporary normalized data follows existing cleanup behavior on accept, abort, fatal error, and normal shutdown.
- **Verification**: Byte-comparison of source files before and after a generation cycle, plus cleanup tests across accept, abort, fatal error, and shutdown.
- **Type**: integration

### AC-META-1
- **Description**: PNG output preserves the current embedded metadata fields and records the actual selected model; JPEG output preserves the current no-custom-metadata behavior. Neither format embeds reference paths, filenames, hashes, fingerprints, or source bytes.
- **Verification**: Metadata tests reading back written PNG and JPEG outputs asserting that the PNG text-chunk key set is exactly the current set and unchanged by this epic, that the recorded model is the one actually selected, and that JPEG carries no custom metadata. Asserting the exact key set is what makes the negative requirement testable — no reference-derived key can be present if the key set is closed.
- **Type**: unit

### AC-LOCAL-1
- **Description**: All reference decoding, normalization, inference, runtime request tracking, and output generation occurs locally. Network access is limited to the existing authorized model-download flow.
- **Verification**: With outbound connections refused and a populated local cache, engine load, reference normalization, and generation complete with zero network access. A model that discovery reports as available is loaded local-only, without a remote revalidation round trip.
- **Type**: integration

### AC-DISCOVERY-1
- **Description**: Model discovery and loading report the specific cause — absent, credentials missing, license access missing, incomplete, or unloadable — and prevent an invalid generation attempt. A cause may be reported as unknown only when it matches none of those. A checkpoint counts as available only once its top-level index and every declared component's configuration and weight files are present; a top-level marker alone is not sufficient.
- **Verification**: Discovery tests constructing each of the five enumerated states — including a cache whose index is present but whose component weights are missing — asserting the matching cause is reported and generation is blocked.
- **Type**: integration

### AC-RECOVERY-1
- **Description**: Any recoverable reference, compatibility, normalization, or configuration error preserves existing image history and allows correction while paused. Fatal failures follow the existing fatal-error contract without emitting an accepted path.
- **Verification**: Error-injection tests asserting history preservation and correct-while-paused recovery, a test that a model switch failing while the previous model reloads successfully stays recoverable and does not exit, and a fatal-path test asserting no accepted path is written to stdout when no model can be made active.
- **Type**: integration

### AC-ACCESS-1
- **Description**: All new desktop controls can be operated by keyboard, expose accessible labels, present errors as text, honor existing theme and font-size behavior, and remain usable with four previews at supported window sizes.
- **Verification**: Keyboard operability, accessible names, and text-form errors asserted against the real rendered interface in a headless browser with the desktop bridge stubbed; the four-preview layout asserted at supported window sizes such that no control loses keyboard or pointer reachability and no preview is clipped by overflow. Pattern-matching the source is a structural proxy for these properties and does not satisfy this criterion.
- **Type**: e2e

### AC-COMPAT-1
- **Description**: Existing configuration files, generated images, and text-only CLI invocations remain usable without supplying new fields or downloading a reference-editing model.
- **Verification**: Backward-compatibility tests loading existing configuration files and generated images, and running existing text-only CLI invocations unchanged.
- **Type**: integration

### AC-MODEL-6
- **Description**: Each supported model uses its own documented default sampling settings, and the values actually used are carried in the generation snapshot and reach the pipeline. One model's defaults are never silently reused for another.
- **Verification**: Contract test asserting the sampling settings reaching each pipeline are that model's documented defaults, and that the snapshot records them. A single global default applied to every model fails this.
- **Type**: integration
- **Note**: Added by amendment 2026-09-18. A shared default passes every mocked test while producing unusable output from a model with different sampling requirements; only this assertion and the release-gate smoke test can detect it.

### AC-STATE-4
- **Description**: An individually valid update that produces an incompatible model/reference combination is acknowledged, not rejected: the reference set is retained exactly as selected and the acknowledgement reports an explicit incompatibility with its reason and the required model. Compatibility is evaluated when generation is about to start, and resume is refused with that reason while the configuration remains incompatible, so no generation runs under a stale-but-valid configuration.
- **Verification**: IPC integration test adding a second reference while a one-reference model is active, asserting the update is acknowledged with both references retained, that the acknowledgement reports incompatibility and names the required model, and that a subsequent resume is refused rather than generating under the previously acknowledged configuration.
- **Type**: integration
- **Note**: Added by amendment 2026-09-18; resolves the contradiction between spec.md §5.1 and §7.2/AC-STATE-3 over whether an incompatible selection is acknowledged-and-blocked or rejected-and-rolled-back.

### AC-PROCESS-3
- **Description**: Each reference is decoded and normalized once, at acknowledgement, and the normalized data is held for the lifetime of that acknowledged configuration. A source file edited, moved, or deleted after acknowledgement does not change what the model receives, and file or decode failures surface as acknowledgement-time rejections rather than errors raised inside the generation loop. The held data is released when the configuration changes and on abort, fatal error, and shutdown.
- **Verification**: Test acknowledging a configuration, then modifying and deleting the source file, asserting subsequent generations receive the originally decoded reference unchanged; a test that a corrupt file is rejected at acknowledgement rather than per iteration; and cleanup tests asserting release on configuration change, abort, fatal error, and shutdown.
- **Type**: integration
- **Note**: Added by amendment 2026-09-18; closes an unspecified decode-timing question that would otherwise let the snapshot's immutability and normalization's determinism be violated in practice.

### AC-DOC-1
- **Description**: The desktop and CLI documentation states, for a reader who has not seen the specification: the capability difference among the three models (which accepts zero, exactly one, and one-to-four references); the supported reference file formats; the six editing output presets by their canonical identifiers; at least one worked one-reference Kontext example and one multi-reference FLUX.2 example; the local model storage, gated-license, credential and hardware/memory expectations; that prompt wording controls identity and reference use with no guaranteed identity fidelity; that processing is local-only and what the metadata privacy policy is; and the first-release limitations including the deferred face-aware-cropping direction. Release notes describe the feature as an additive editing workflow and state that FLUX.2 is required for two to four references.
- **Verification**: Documentation review against this list, plus a check that every command and configuration example given is executable as written against the shipped CLI surface and configuration schema. A heading without content does not satisfy an item.
- **Type**: manual-reviewable documentation check (no runtime behavior)
- **Note**: Added by amendment 2026-09-18. spec.md §16 states documentation and release-note requirements but carried no acceptance criterion and no owning story, so neither the story split nor the end-of-epic AC-closure gate would have caught its omission. Owned by S13.

## Manual Validation

_None._

Per spec.md §15, the one behavior in this domain that resists automated discrimination — visual similarity and identity preservation — is deliberately excluded from binary acceptance criteria rather than recorded as a manual-validation row. Verification instead asserts *input fidelity*: that Textbrush supplies the intended prompt, the complete ordered reference set, and the selected settings without app-side loss or reinterpretation. Every remaining behavioral requirement has a deterministic, mockable, or parameterizable observable.

The local smoke test for each editing model on supported hardware (spec.md §15) is a hardware-gated developer check, not a product acceptance criterion, and is explicitly not a prerequisite for the fast unit suite.

## Verification Plan

Per spec.md §15, implementation verification comprises:

1. Unit tests for model/reference cardinality, preset mapping, immutable snapshots, metadata behavior, and deterministic normalization decisions.
2. Parameterized tests over reference counts, file orderings, pause/update/resume sequences, and supported source dimensions.
3. Mocked inference contract tests proving the exact ordered references and prompt passed to each model pipeline.
4. IPC integration tests proving acknowledged state and per-result provenance across configuration changes.
5. CLI and headless tests for valid and invalid combinations, stdout, exit behavior, and unavailable models.
6. Desktop interaction tests for file selection, previews, removal, replacement, disabled states, rollback after rejection, keyboard access, and four-preview layout.
7. Cleanup tests across accept, abort, fatal error, and shutdown.
8. A local smoke test for each editing model on supported hardware when the gated weights are available, without making that hardware-dependent run a prerequisite for fast unit tests.
