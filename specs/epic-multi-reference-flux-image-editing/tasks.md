# Implementation Tasks: Multi-Reference FLUX Image Editing

Audience: an AI coding agent working one task at a time, in order, with no memory of
earlier sessions. Everything you need to decide is written here; when this file and your
own judgement disagree, follow this file and note the disagreement in the task's status row.

Authority chain: `spec.md` > `acceptance-criteria.md` > `architecture.md` > this file.
Read `architecture.md` once before starting (module map, boundary rules, preset lexicon).

## 0. How to work this file

1. Find the first task in the status table (section 2) that is not `done`. Do only that task.
2. Read the task's **Files** and every file it names before editing anything.
3. Implement **Steps** in order. Write the **Tests** listed. Do not skip a test because it is
   hard; if it is impossible, write why in the status row and leave the task `blocked`.
4. Run the **Verify** commands. All must pass. Then run the global gate:
   ```bash
   uv run ruff check textbrush tests && uv run ruff format --check textbrush tests
   uv run pytest tests --ignore=tests/test_buffer_stress.py -m "not slow and not integration" -q
   ```
   Baseline expectation for the pytest line: the only failures allowed are the 61 pre-existing
   failures in `tests/test_config_controls.py` and `tests/test_config_controls_integration.py`
   (they need a compiled `config_controls.js`; see task T10 step 9, which fixes them). Any other
   failure is yours.
5. Update the status table row (`done` / `blocked` + one-line note). Commit with a message
   `feat(<module>): <task title>` on `master`. One commit per task.
6. Never revert, delete, or overwrite files you did not create in the current task. Never
   rewrite git history.

Rules that apply to every task (from `CLAUDE.md` and `architecture.md`):

- Package manager is `uv`. Run Python only as `uv run ...`.
- Production code is never adapted to make a test pass. Fix the test instead.
- Import direction is `ipc -> backend -> worker -> inference`; `buffer`, `config`, `paths`,
  `model`, `references`, `validation` are leaves and import nothing from `textbrush` except
  other leaves as already established (`validation` may import `model.registry`).
- Any wire-schema change is three edits made together: `textbrush/ipc/protocol.py`,
  the Rust `json!` builder in `src-tauri/src/`, and `src-tauri/ui/types.ts`.
- IPC validation failures are sent as `ErrorEvent(message, fatal=False)`, never raised.
- CLI exit codes: 0 success, 1 runtime or validation error, 2 argparse error. Reference,
  cardinality, and preset validation failures must exit 1, the same as an empty prompt.
- New public functions get the CONTRACT-style docstring used in `textbrush/inference/base.py`.
- Keep `ruff` line length 100. Run `uv run ruff format textbrush tests` before committing.
- Real model weights are gated. Tests stub `engine._pipeline = Mock()` as in
  `tests/test_flux_inference.py`; only `tests/conftest.py` loads real weights under `--run-slow`.
  Never run `--run-slow` or `make test-all` without the user's explicit confirmation.
- Do not create markdown files other than the ones a task names.

## 1. Ground truth (verified 2026-09-18 against commit 47f6151)

- Stories S1 (config), S2 (model registry), S3 (references) are complete and tested. Do not
  redesign them. Their public surfaces:
  - `textbrush/config.py`: `Config.model.selected_id: str | None`,
    `Config.editing.default_preset: str` (default `"landscape-medium"`).
  - `textbrush/model/registry.py`: `FLUX1_SCHNELL`, `FLUX1_KONTEXT_DEV`, `FLUX2_KLEIN_4B`,
    `get_model_spec(slug) -> ModelSpec` (fields `slug, repo_id, display_name, min_references,
    max_references, gated, ...`), `get_repo_id(slug)`, `iter_model_slugs()`,
    `DiscoveryCause`, `AvailabilityReport`, `ModelResolution`,
    `resolve_model_selection(*, selected_id, reference_count, availability) -> ModelResolution`
    where `availability: Callable[[str], AvailabilityReport]`.
  - `textbrush/model/weights.py`: `check_model_availability(model_id, *, custom_dirs) ->
    AvailabilityReport`, `is_model_available`, `ensure_model_available`,
    `download_model_weights`, `load_local_only(pipeline_factory, model_id, *, root, **kwargs)`.
  - `textbrush/references/`: `normalize(path, target_size: tuple[int,int] | None = None) ->
    NormalizedReference` (fields `pixel_data: PIL.Image.Image`, `width`, `height`,
    `content_aspect_ratio`, `fill_value`, `decoded_at`), exception base `ReferenceImageError`
    with six subclasses, `SUPPORTED_EXTENSIONS`, `NEUTRAL_FILL_VALUE = 128`.
    `pixel_data` is mutable and not copied: copy before handing it to any pipeline.
    `target_size=None` means EXIF/RGB/alpha only, no scaling, no padding.
- Commit 47f6151 added a thin, untested sketch of S4 through S9 plus README/CHANGELOG lines.
  It is the starting point for tasks T01 through T08, which repair and complete it. It contains
  these known defects (each is fixed by a named task):
  - 24 ruff errors and 7 unformatted files (T01).
  - `tests/test_backend_start_generation.py`: 10 failures because `create_mock_config()` yields
    a `Mock` for `config.model.selected_id` (T01).
  - `pyproject.toml` still pins `diffusers>=0.25.0`; the lock resolves 0.36.0, which exports
    `FluxKontextPipeline` but **not** `Flux2KleinPipeline` (T02).
  - Kontext is called with default `_auto_resize=True` and default `max_area=1024**2`, so the
    pipeline resizes the reference non-uniformly and recomputes the output size (T04).
  - `update_editing_config` does not forward preset dimensions to the worker, does not apply the
    default editing preset, and its engine swap has no reload-on-failure path (T06).
  - `handle_pause` emits `paused` before the worker is settled and carries no settled flag; the
    editing branch of `handle_update_config` refuses updates before generation started (T07).
  - CLI decodes references twice, never calls `resolve_model_selection`, and does not reject
    `--aspect-ratio` for editing models (T08).
  - `flux.py` records the short slug as `model_name`, changing PNG `Model` metadata for the
    existing schnell path (T06).
  - No `src-tauri` changes at all: no picker, no selector, no `config_ack` in TypeScript or Rust
    (T07, T09, T10, T11).
- Pre-existing, unrelated: 61 tests in `tests/test_config_controls*.py` fail because
  `src-tauri/ui/config_controls.js` is not compiled in a fresh checkout. `tsc` is not on PATH
  unless `npm install` has been run in `src-tauri/ui`. `cargo check` needs `glib-2.0` dev
  headers on Linux; on macOS it works as is.
- diffusers 0.36.0 `FluxKontextPipeline.__call__` facts (read from
  `pipelines/flux/pipeline_flux_kontext.py`):
  - Parameters `max_area: int = 1024**2` and `_auto_resize: bool = True`.
  - Output size is recomputed: `width = round((max_area * width/height) ** 0.5)` then floored
    to a multiple of `vae_scale_factor * 2` (= 16). Passing
    `max_area = width * height` with both already multiples of 16 makes this a no-op.
  - Reference handling: if `_auto_resize`, the image is bucketed to the nearest
    `PREFERRED_KONTEXT_RESOLUTIONS` entry; in all cases each axis is then floored to a multiple
    of 16 and the image is resized to that. Passing `_auto_resize=False` and an image whose
    width and height are already multiples of 16 makes the resize a no-op.
- diffusers 0.36.0 `Flux2Pipeline` (FLUX.2 dev, closest available relative of klein) resizes
  references to a target area of 1024*1024 and then to multiples of 16 with
  `resize_mode="crop"`. Expect `Flux2KleinPipeline` (diffusers >= 0.37) to behave the same;
  T02 verifies this against the real installed source and records the result.

## 2. Status

| Task | Title | Status | Note |
|---|---|---|---|
| T01 | Repair regressions and hygiene from 47f6151 | pending | |
| T02 | Raise the diffusers floor and record pipeline facts | pending | |
| T03 | Finish `validation.py` (S4) | pending | |
| T04 | Inference reference contract and engines (S5) | pending | |
| T05 | Worker quiescence, discard, buffer provenance (S6) | pending | |
| T06 | Backend config lifecycle, swap, decode-once, metadata (S7) | pending | |
| T07 | IPC pause gate, acknowledgement, launch resolution, wire mirror (S8) | pending | |
| T08 | CLI model and reference arguments (S9) | pending | |
| T09 | Desktop shell: file dialog command (S10a) | pending | |
| T10 | Desktop UI: picker, selector, presets, acknowledgement (S10b) | pending | |
| T11 | Headless-browser accessibility harness (S11) | pending | |
| T12 | Cross-cutting provenance integration tests (S12) | pending | |
| T13 | User documentation and release notes (S13) | pending | |
| T14 | Epic closure | pending | |

## 3. Tasks

---

### T01. Repair regressions and hygiene from 47f6151

**Goal.** Green baseline: lint and format clean, no test regressions relative to the spec
commit, README and CHANGELOG insertions in the right place.

**Files.** `textbrush/backend.py`, `textbrush/cli.py`, `textbrush/inference/factory.py`,
`textbrush/inference/flux.py`, `textbrush/ipc/handler.py`, `textbrush/ipc/protocol.py`,
`textbrush/validation.py`, `tests/test_backend_start_generation.py`, `README.md`,
`CHANGELOG.md`.

**Steps.**
1. Run `uv run ruff check textbrush tests --fix` then `uv run ruff format textbrush tests`.
   Fix the remaining errors by hand (unused imports such as `DEFAULT_EDITING_PRESET` in
   `backend.py`, long lines, import ordering). Do not change behavior in this task.
2. In `tests/test_backend_start_generation.py::create_mock_config`, add
   `mock_config.model.selected_id = None` (the `Mock(spec=ModelConfig)` otherwise returns a
   `Mock`, which `validate_selection` rejects as an unknown model). Also add
   `mock_config.editing = Mock(); mock_config.editing.default_preset = "landscape-medium"` so
   later tasks can read it.
3. `README.md`: move the "## Reference editing" section (currently lines 3 to 32) to sit after
   the existing "## Features" section, or after "## Usage" if one exists. The file must start
   with the title and the one-line tagline as before.
4. `CHANGELOG.md`: move "## Unreleased" (currently line 3) so it comes after the
   "The format is based on Keep a Changelog" preamble and before the first versioned section.
5. Run the global gate. Expected: 828 or more passed; failures only in the two
   `test_config_controls*` files.

**Tests.** None new.

**Verify.**
```bash
uv run ruff check textbrush tests && uv run ruff format --check textbrush tests
uv run pytest tests/test_backend_start_generation.py tests/test_worker.py -q
```

**Done when.** Lint and format pass; the ten backend tests pass; README begins with the title.

---

### T02. Raise the diffusers floor and record pipeline facts

**Goal.** The locked ML stack provides both editing pipelines, and the exact kwargs that stop
each pipeline from resizing references are known from source, not assumed.

**Files.** `pyproject.toml`, `uv.lock`, `docs/gpu-setup.md` (one paragraph), this file.

**Steps.**
1. In `pyproject.toml` `[project.optional-dependencies].model`, change the diffusers line to
   `"diffusers>=0.37.0,<1.0.0"`. If `uv lock` cannot find 0.37.0, use the lowest published
   version whose changelog adds `Flux2KleinPipeline`; check with
   `uv pip index versions diffusers` or the PyPI page.
2. Run `uv lock`. Do not run `uv sync --extra model` on a machine without a GPU unless the
   user has confirmed; the lock update alone is what this task needs. If the model extra is
   already installed, run `uv sync --extra model`.
3. Verify the export list without installing torch:
   ```bash
   uv run --no-project --with "diffusers==<locked version>" python -c \
     "import diffusers; print('FluxKontextPipeline' in dir(diffusers), 'Flux2KleinPipeline' in dir(diffusers))"
   ```
   Both must print `True`.
4. Locate the downloaded package (`python -c "import diffusers,os;print(os.path.dirname(diffusers.__file__))"`
   under the same `uv run --no-project --with` invocation) and read
   `pipelines/flux2/pipeline_flux2_klein.py` (or wherever `Flux2KleinPipeline` lives). Record
   in the **Note** column of T02 and in a docstring on `Flux2KleinInferenceEngine` (T04):
   - the name of the `image` parameter and whether it accepts a `list` of PIL images;
   - the exact preprocessing steps applied to each reference (target-area resize, multiple-of
     rounding, crop or pad, any `_auto_resize`-style flag);
   - the conditions under which preprocessing leaves an image's pixels unchanged (expected:
     width and height already multiples of 16 and area not exceeding the pipeline's target
     area). If there is a flag that disables the resize, record its name.
   - the default `num_inference_steps` and `guidance_scale` in the signature.
   Do the same for `FluxKontextPipeline` in the new version and confirm the facts listed in
   section 1 still hold (`max_area`, `_auto_resize`, multiple-of-16 flooring).
5. Confirm `FluxPipeline` (schnell) still accepts `prompt, width, height, num_inference_steps,
   guidance_scale, generator`; the existing `tests/test_flux_load.py` assertions must remain
   valid.
6. Add one paragraph to `docs/gpu-setup.md` stating the new minimum diffusers version and that
   the editing models need it.

**Tests.** None new (the assertions live in T04).

**Verify.** Step 3 prints `True True`; `uv run pytest tests/test_flux_load.py -q` passes or
skips exactly as before.

**Done when.** The lock resolves a diffusers version exporting both pipelines and the T02 note
records the klein preprocessing facts verbatim with file and line references.

---

### T03. Finish `validation.py` (S4)

**Goal.** One leaf module owns cardinality and preset rules, reads cardinality from
`ModelSpec`, validates presets in both directions, and produces messages that satisfy
AC-MODEL-4. Owned ACs: AC-MODEL-4, AC-PRESET-1, AC-INPUT-4.

**Files.** `textbrush/validation.py`, `tests/test_validation.py` (new), `textbrush/config.py`
(read only), `tests/test_config.py` (one assertion).

**Steps.**
1. Keep `EDITING_PRESETS`, `DEFAULT_EDITING_PRESET = "landscape-medium"`, `ValidationVerdict`,
   `editing_preset_dimensions`. Add module constant `TEXT_ASPECT_RATIOS = ("1:1", "16:9",
   "9:16", "3:1", "4:1", "4:5")` copied from `cli.py`'s `SUPPORTED_RATIOS` keys; do not move
   the CLI resolution table. Add `is_editing_model(model_id) -> bool` returning
   `get_model_spec(model_id).max_references > 0`.
2. Change the signature to
   `validate_selection(model_id, reference_count, preset=None, aspect_ratio=None) -> ValidationVerdict`.
   Rules, in this order, first failure wins:
   - unknown slug: `valid=False, reason=f"unknown model: {model_id}"`.
   - cardinality: derive the rule text from the spec:
     `min == max == 0` -> `"accepts no reference images"`;
     `min == max` -> `f"requires exactly {min} reference image"`;
     else `f"requires between {min} and {max} reference images"`.
     `reason = f"{spec.slug} ({spec.display_name}) {rule}; got {reference_count}"`.
     `required_model`: `FLUX2_KLEIN_4B` when `2 <= reference_count <= 4`; `FLUX2_KLEIN_4B` when
     `reference_count == 1` and the selected model is schnell (spec §5.1 prefers FLUX.2);
     `FLUX1_SCHNELL` when `reference_count == 0` and the model is editing-capable; `None` when
     `reference_count > 4` (append `"; no supported model accepts more than 4"` to the reason).
   - preset direction 1: `preset` given and in `EDITING_PRESETS` but model is not
     editing-capable -> `reason=f"editing preset {preset} requires an editing-capable model"`.
   - preset direction 2: `preset` given and not in `EDITING_PRESETS` -> `reason=f"unknown editing preset: {preset}"`.
   - aspect-ratio direction: `aspect_ratio` given (not `None`, not `"custom"`) and model is
     editing-capable -> `reason=f"text-only aspect ratio {aspect_ratio} is not valid for editing model {model_id}; choose one of {', '.join(EDITING_PRESETS)}"`.
   - editing model with `preset is None` is valid (the caller applies the default).
3. Add `resolve_preset(model_id, preset, default_preset) -> str | None`: returns `preset` if
   given, else `default_preset` for an editing-capable model, else `None`. Callers (backend,
   CLI) use it so the default lives in one place.
4. In `tests/test_config.py` add one test asserting
   `get_default_config().editing.default_preset == textbrush.validation.DEFAULT_EDITING_PRESET`
   (the two constants must not drift; `config` cannot import `validation` because `validation`
   imports `model`).

**Tests** (`tests/test_validation.py`).
- Parameterized table over every `(model, count)` for counts 0..5: assert `valid` matches
  `spec.min_references <= count <= spec.max_references`, and for invalid cells assert the reason
  contains the slug, the display name, and the exact rule text; assert `required_model` per the
  table in step 2.
- Bidirectional preset tests: each of the six presets with schnell is invalid; each text ratio
  with each editing model is invalid; each preset with each editing model is valid.
- Duplicate-path semantics: validation takes a count, so document with a test that
  `validate_selection(FLUX2_KLEIN_4B, 2)` is valid regardless of path identity, and that
  `validate_selection(FLUX1_KONTEXT_DEV, 2)` is invalid even if a caller passed the same path
  twice (AC-INPUT-4).
- `editing_preset_dimensions` for all six presets equals the table in `architecture.md`.
- Structural: `validation.py` contains no integer literals 0, 1, or 4 used as cardinality
  (grep the source in the test for `min_references`/`max_references` usage and assert no
  `reference_count > 4` style literal except the documented `> 4` no-model case, which must
  read `max(spec.max_references for spec in registry)` instead of a literal). Implement it that
  way: compute `_MAX_SUPPORTED = max(get_model_spec(s).max_references for s in iter_model_slugs())`.
- Leaf boundary: reuse the `_internal_imports` AST helper from `tests/test_config.py` to assert
  `validation.py` imports only `textbrush.model.registry`.

**Verify.** `uv run pytest tests/test_validation.py tests/test_config.py -q`

**Done when.** All rules above are tested and the three current callers (`backend.py`,
`cli.py`, `ipc/handler.py`) still pass their suites with the new keyword argument.

---

### T04. Inference reference contract and engines (S5)

**Goal.** The engine layer hands each pipeline the prompt, the ordered references, and that
model's own sampling settings, with pipeline-internal reference resizing provably disabled or
a no-op. Owned ACs: AC-MODEL-1, AC-MODEL-2, AC-MODEL-3, AC-MODEL-6. Blocking condition
S5-BC-1: the per-model reference-input size has exactly one derivation site, on the engine.

**Files.** `textbrush/inference/base.py`, `textbrush/inference/flux.py`,
`textbrush/inference/factory.py`, `tests/mocks.py`, `tests/test_flux_inference.py`,
`tests/test_inference_contract.py` (new).

**Design decisions (fixed).**
- Normalization shape for both editing pipelines is shape (ii) from S5-BC-1: uniform scale
  into a fixed canvas with centered padding, where the canvas is the generation canvas
  `(round16(output_width), round16(output_height))` with `round16(x) = ((x + 15) // 16) * 16`.
  Both axes are multiples of 16, and the largest preset canvas (1024x768 = 786,432 px) is below
  the FLUX.2 target area of 1,048,576 px, so neither pipeline resizes it.
- `GenerationOptions.references` holds `NormalizedReference` instances already at that canvas.
  The engine does not normalize; it copies `pixel_data` and passes it through.
- Sampling defaults per model, kept on the engine as `default_sampling_settings`:
  schnell `{"num_inference_steps": 4, "guidance_scale": 0.0}`;
  Kontext `{"num_inference_steps": 28, "guidance_scale": 2.5}`;
  FLUX.2 klein 4B `{"num_inference_steps": 4, "guidance_scale": 1.0}`. If T02 recorded
  different signature defaults for klein, use the documented model-card values and cite them
  in the docstring.

**Steps.**
1. `base.py`: type `references` as `tuple[NormalizedReference, ...]` (import under
   `TYPE_CHECKING` from `textbrush.references` to keep runtime imports minimal; both are leaves).
   Add to `InferenceEngine` two non-abstract methods with CONTRACT docstrings:
   `reference_input_size(self, output_width: int, output_height: int) -> tuple[int, int] | None`
   (default `None`) and `default_sampling_settings(self) -> dict[str, float | int]` (default
   `{}`). Update the `generate` docstring: "Aspect ratio respected" wording is stale; state that
   explicit width/height win and that `options.references` are forwarded in order.
2. `flux.py`:
   - `FluxInferenceEngine.reference_input_size` returns `None` for schnell and
     `(round16(w), round16(h))` for the two editing slugs. Put `round16` in one module-level
     helper and use it in `generate()` too (it currently inlines the formula twice).
   - `generate()`: build `settings = {**self.default_sampling_settings(), **options.sampling_settings}`;
     `steps = settings.pop("num_inference_steps")`; call the pipeline with
     `prompt, width=generated_width, height=generated_height, num_inference_steps=steps,
     generator=generator, **settings`.
   - Kontext branch: add `image=references[0].pixel_data.copy()`, `_auto_resize=False`,
     `max_area=generated_width * generated_height`. Before calling, assert each reference's
     `(width, height) == (generated_width, generated_height)`; raise `ValueError` naming the
     mismatch otherwise (this is the model-boundary guard; the backend must have normalized
     to `reference_input_size`).
   - FLUX.2 branch: `image=[r.pixel_data.copy() for r in references]` plus whatever kwargs T02
     recorded as disabling resizing (if any). Same size assertion.
   - Schnell branch: raise `ValueError` if `options.references` is non-empty.
   - `model_name=get_repo_id(self.model_id)` so PNG `Model` metadata keeps the repository id
     for schnell (AC-META-1, AC-COMPAT-1).
   - Keep `load()` selecting the pipeline class by slug; import `Flux2KleinPipeline` lazily.
   - Delete the `reference_input_size` property version from 47f6151 (it is now a method).
3. `factory.py`: keep `create_engine(backend, model_id)`. Add a test that each slug maps to the
   expected class and unknown slug raises `ValueError`.
4. `tests/mocks.py::MockInferenceEngine`: record `self.last_prompt`, `self.last_options`
   (the full `GenerationOptions`, including `references` and `sampling_settings`) on every
   `generate()`; add `reference_input_size` returning `None` and a constructor flag
   `reference_canvas: tuple[int,int] | None` so backend tests can drive the padded path.
   Returned image size must follow `options.width/height`.

**Tests** (`tests/test_inference_contract.py`; guard with `pytest.importorskip("torch")` only
for the classes that build a real engine; the mock-based ones need no torch).
- AC-MODEL-2: engine for Kontext with `engine._pipeline = Mock()`, one reference at the canvas
  size; assert `call_args.kwargs["image"]` is a PIL image of canvas size,
  `kwargs["_auto_resize"] is False`, `kwargs["max_area"] == gw * gh`,
  `kwargs["num_inference_steps"] == 28`, `kwargs["guidance_scale"] == 2.5`, and the
  `image` object is not the same object as `reference.pixel_data` (copied).
- AC-MODEL-3: parameterized over counts 1..4 and at least three distinct orderings (use
  images with distinct solid colours so identity is checkable by pixel); assert the `image`
  list length, order, and exact-once delivery; assert the same file appearing twice yields two
  list entries (AC-INPUT-4).
- Size guard: a reference not at canvas size raises `ValueError` before the pipeline is called.
- AC-MODEL-1: schnell engine called with no references passes no `image` kwarg and
  `guidance_scale == 0.0`; `FluxInferenceEngine.ASPECT_RATIOS` key set is unchanged (assert the
  literal set present today).
- AC-MODEL-6: for each slug, the kwargs reaching the pipeline equal that slug's documented
  defaults, and an `options.sampling_settings` override wins.
- `reference_input_size` table: schnell `None`; editing slugs `(round16(w), round16(h))` for
  all six presets.

**Verify.** `uv run pytest tests/test_inference_contract.py tests/test_flux_inference.py tests/test_flux_load.py -q`

**Done when.** Every assertion above passes with `_pipeline` mocked and the engine docstrings
cite the T02 source facts.

---

### T05. Worker quiescence, discard, buffer provenance (S6)

**Goal.** "Paused" is observable as quiescent, results from a superseded configuration never
enter the buffer, and every buffered image carries its snapshot's model identity and
session-local reference identity. Owned AC: AC-STATE-1 (worker half).

**Files.** `textbrush/worker.py`, `textbrush/buffer.py`, `tests/test_worker.py`,
`tests/test_buffer.py`.

**Steps.**
1. `buffer.py::BufferedImage`: add `model_id: str | None = None` and
   `reference_ids: tuple[str, ...] = ()` with docstring "session-local; never written to output
   files (AC-META-1)". Keep all existing fields and defaults so old call sites compile.
2. `worker.py`:
   - Keep `_settled_event`, `_generation_epoch`, `is_settled()` from 47f6151.
   - Add constructor parameter `on_settled: Callable[[], None] | None = None` and method
     `set_on_settled(callback)`. In `_run`, when the loop enters the pause-wait and sets
     `_settled_event` for the first time after a pause request, invoke the callback once
     (guard with a local flag reset when the worker resumes). Document that the callback runs
     on the worker thread.
   - Add `wait_settled(timeout: float | None) -> bool` wrapping `_settled_event.wait`.
   - In `update_config`, accept optional `model_id: str | None` and
     `reference_ids: tuple[str, ...]` keyword arguments stored on the worker and captured per
     iteration together with prompt/options/epoch; pass them into `BufferedImage`.
   - Keep the epoch bump on every `update_config` call (prompt-only updates also discard
     in-flight results; document this in the docstring as intended).
   - When the epoch check discards a result, log at info level with both epochs.
3. Remove the property `is_settled` from 47f6151 if it is a plain method already; it must stay a
   method named `is_settled()`.

**Tests.**
- `test_worker.py`:
  - Quiescence is distinct from request: engine `generate` blocks on a `threading.Event`;
    call `pause()`; assert `is_paused()` is `True` and `is_settled()` is `False`; release the
    event; assert `wait_settled(2.0)` returns `True` and the callback fired exactly once.
  - Discard race (VQ-S6-004): engine blocks mid-generate; call `update_config` (epoch bump)
    and `buffer.clear()`; release; assert the buffer stays empty and the next generation's
    result does arrive.
  - Resume then pause again re-arms the callback (fires once per settle).
  - Fix the flaky `test_immediate_stop_before_first_generation`: replace the `<= 3` timing
    assertion with an engine whose `generate` sleeps 50 ms and assert `<= 1`.
- `test_buffer.py`: `BufferedImage(model_id=..., reference_ids=...)` round-trips and defaults
  are `None`/`()`.

**Verify.** `uv run pytest tests/test_worker.py tests/test_buffer.py -q` (run twice to check
for flakiness).

**Done when.** The four scenarios above pass deterministically and `worker.py` imports nothing
from `backend` or `ipc`.

---

### T06. Backend config lifecycle, engine swap, decode-once, metadata (S7)

**Goal.** The backend holds the acknowledged configuration, decodes references exactly once
at acknowledgement to the engine's canvas, applies model + references + preset atomically,
swaps engines with reload-on-failure, releases decoded data on change/abort/shutdown, and
keeps the PNG key set closed. Owned ACs: AC-PROCESS-3, AC-STORAGE-1, AC-META-1, AC-RECOVERY-1.

**Files.** `textbrush/backend.py`, `tests/test_backend.py` (new),
`tests/test_backend_save_metadata.py` (extend), `tests/test_cleanup.py` (extend).

**Design decisions (fixed).**
- Backend state: `self.model_id: str`, `self.references: tuple[NormalizedReference, ...]`,
  `self.reference_paths: tuple[str, ...]` (for acknowledgement reporting only),
  `self.reference_ids: tuple[str, ...]` (session-local: `f"{uuid4().hex}:{position}"`
  generated at acknowledgement), `self.preset: str | None`, `self.sampling_settings: dict`.
- Snapshot: `GenerationOptions` is the immutable snapshot; the backend fills `references`,
  `model_id`, `sampling_settings` (from `engine.default_sampling_settings()`), `width/height`
  (from the preset when an editing model is active). `worker.update_config` receives
  `model_id` and `reference_ids` too.
- Engine swap order: (1) `check_model_availability(candidate)`; if not available raise
  `ModelUnavailableError(cause, detail)` (new exception class in `backend.py`) without touching
  the loaded engine. (2) `previous = self.engine; previous.unload()`. (3)
  `next_engine = create_engine(...); next_engine.load()`. (4) On exception: try
  `previous.load()`; if that succeeds raise `ModelSwitchError(recoverable=True, ...)` with the
  original cause; if it also fails raise `FatalModelError(...)`. Define the three exception
  classes at module level in `backend.py`; `ipc` and `cli` map them to messages.

**Steps.**
1. Replace `update_editing_config` with:
   ```python
   def apply_configuration(self, *, model_id=None, reference_paths=None, preset=None) -> ConfigurationAck
   ```
   returning a frozen dataclass `ConfigurationAck(model_id, reference_count, reference_paths,
   preset, compatible, incompatibility_reason, required_model)` defined in `backend.py`.
   Algorithm:
   a. Precondition: `self._worker is None or self._worker.is_settled()`; else raise
      `RuntimeError("configuration changes require a settled, paused worker")`.
   b. `candidate_model = model_id or self.model_id`;
      `candidate_preset = validation.resolve_preset(candidate_model, preset if preset is not None else self.preset, self.config.editing.default_preset)`
      but when switching between modes (editing-capable changes) and `preset is None`, drop
      the old-mode preset: text mode -> `None`, editing mode -> default. Record the last
      acknowledged preset per mode in `self._last_preset_by_mode` so that switching back
      restores it (spec §5.5).
   c. If the model changes: swap the engine per the design decision. Any exception here leaves
      `self.*` untouched and propagates.
   d. Decode: if `reference_paths is not None`, compute
      `canvas = self.engine.reference_input_size(width, height)` where `width, height` come
      from `editing_preset_dimensions(candidate_preset)` if a preset applies, else the current
      options; call `normalize(path, target_size=canvas)` for each path in order. Any
      `ReferenceImageError` propagates unchanged (the caller reports its message). On success
      the old `self.references` tuple is replaced (release) and new `reference_ids` are minted.
      If the model changed but `reference_paths is None`, re-normalize from
      `self.reference_paths` because the canvas may differ. If the preset changed for an
      editing model, re-normalize for the same reason.
   e. `verdict = validate_selection(candidate_model, len(refs), candidate_preset)`.
   f. Commit state; if a worker exists, build new `GenerationOptions` (seed `None`,
      `steps` from sampling settings, width/height from preset or current, references,
      model_id, sampling_settings) and call `worker.update_config(prompt, options,
      model_id=..., reference_ids=...)`, set `worker.engine = self.engine`, then
      `self.buffer.clear()`. Do this even when the verdict is incompatible: the worker holds the
      acknowledged state, and resume is refused elsewhere.
   g. Return the ack.
2. `start_generation`: accept `references` as already-normalized instances only from
   `apply_configuration`; simplify to read `self.model_id/self.references/self.preset`, apply
   `resolve_preset` for editing models, compute width/height from the preset, populate
   `sampling_settings` from the engine, and pass `model_id`/`reference_ids` to the worker. Keep
   the `validate_selection` guard and raise `ValueError(verdict.reason)` when incompatible.
3. `pause_generation(on_settled=None)`: forward the callback to the worker via
   `set_on_settled`. `is_settled()` on backend delegates to the worker (`True` when no worker).
4. `abort()`, `shutdown()`, and the fatal-error path: set `self.references = ()` and
   `self.reference_ids = ()` (release decoded data).
5. `_save_with_metadata`: no change to the key set. Add a comment that `model_id` and
   `reference_ids` on `BufferedImage` must never be written here.
6. `__init__`: `self.model_id = config.model.selected_id or FLUX1_SCHNELL` stays; composition
   roots set `config.model.selected_id` from the resolver before constructing the backend.

**Tests** (`tests/test_backend.py`, using `MockInferenceEngine` via
`patch("textbrush.backend.create_engine")` and the fixtures in `tests/fixtures/images/`).
- Decode-once (AC-PROCESS-3): acknowledge one reference; overwrite the file with a different
  image; delete it; run one generation; assert the engine's `last_options.references[0]`
  pixel data equals the originally decoded pixels.
- Corrupt file is rejected at acknowledgement: `apply_configuration` with
  `corrupt_truncated.jpg` raises `CorruptReferenceError`; state unchanged; worker untouched.
- Canvas: with an editing model and preset `portrait-large`, every reference has size
  `(768, 1024)`; changing the preset re-normalizes to the new canvas.
- Atomic mode switch: from schnell to Kontext with one reference and no preset, ack reports
  `preset == config.editing.default_preset`; back to schnell reports `preset is None`; back to
  Kontext restores the previously acknowledged editing preset.
- Acknowledged-and-incompatible: Kontext active, two references -> ack `compatible=False`,
  `required_model == FLUX2_KLEIN_4B`, both references retained.
- Swap recovery: patch `create_engine` so the new engine's `load()` raises; assert the previous
  engine's `unload()` then `load()` were called, the exception is `ModelSwitchError`, and
  `backend.model_id` is unchanged. Second test: previous `load()` also raises ->
  `FatalModelError`.
- Unavailable model: patch `check_model_availability` to report `DiscoveryCause.INCOMPLETE`;
  assert `ModelUnavailableError` and that no engine was unloaded.
- Release: after `abort()` and after `shutdown()`, `backend.references == ()`.
- Source preservation (AC-STORAGE-1): SHA-256 of each fixture before and after a full
  acknowledge + generate + accept cycle is identical, and the accepted output directory
  contains no file whose bytes equal a source file.
- Metadata (AC-META-1, extend `tests/test_backend_save_metadata.py`): PNG text keys of an
  accepted editing image are exactly
  `{"AspectRatio","Width","Height","Prompt","Model","Seed","GeneratedWidth","GeneratedHeight"}`
  (the last two only when present today); `Model` equals `get_repo_id(model_id)`; JPEG output
  has no text chunks and no EXIF.
- `tests/test_cleanup.py`: extend to assert `references == ()` after the existing accept,
  abort, fatal, and shutdown scenarios.

**Verify.** `uv run pytest tests/test_backend.py tests/test_backend_save_metadata.py tests/test_cleanup.py tests/test_backend_start_generation.py -q`

**Done when.** All listed tests pass and `backend.py` calls `normalize` in exactly one place.

---

### T07. IPC pause gate, acknowledgement, launch resolution, wire mirror (S8)

**Goal.** The desktop path acknowledges configuration through a `config_ack` event, reports
the settled state, refuses resume while incompatible, serializes resume behind an update, and
runs default-model resolution exactly once at init. The wire schema is mirrored in Rust and
TypeScript in this task. Owned ACs: AC-STATE-3, AC-STATE-4, AC-MODEL-5b (IPC half).

**Files.** `textbrush/ipc/protocol.py`, `textbrush/ipc/handler.py`,
`src-tauri/src/commands_update_config.rs`, `src-tauri/src/launch_args.rs` (read),
`src-tauri/ui/types.ts`, `tests/test_ipc_handler.py`, `tests/test_ipc_integration.py`,
`tests/test_model_resolution_callsites.py` (new).

**Steps.**
1. `protocol.py`:
   - `UpdateConfigCommand`: keep `model_id`, `references`, `preset` (all optional).
   - `InitCommand`: add `model_id: str | None = None`, `references: list[str] | None = None`,
     `preset: str | None = None`.
   - `ConfigAckEvent`: fields `model_id, reference_count, reference_paths: list[str], preset,
     compatible, incompatibility_reason, required_model, settled: bool`.
   - `StateChangedEvent`: add `settled: bool | None = None` (present only when
     `state == "paused"`).
   - `ErrorEvent`: add optional `cause: str | None = None` for discovery causes
     (`DiscoveryCause` value) and `required_model: str | None = None`.
2. `handler.py`:
   - `handle_init`: call `resolve_model_selection(selected_id=cmd.model_id or
     self.config.model.selected_id, reference_count=len(cmd.references or []),
     availability=lambda slug: check_model_availability(slug, custom_dirs=self.config.model.directories))`
     exactly once. If `resolution.blocked`, emit `state_changed(error, fatal=True)` with
     `resolution.reason`, `cause`, `required_model` and return. Otherwise set
     `self.config.model.selected_id = resolution.model_id` before constructing the backend.
     After the backend is initialized and the worker exists, if the init carried references or
     a preset, call `backend.apply_configuration(...)` before `start_generation` and emit the
     `config_ack`.
   - `handle_update_config`: when any editing field is present:
     a. If `not self._generation_started`: store the fields in `_pending_startup_config`
        (extend the existing dict) and return; `handle_init`'s replay applies them via
        `apply_configuration` and emits the ack.
     b. Else if `not backend.is_paused() or not backend.is_settled()`: emit
        `ErrorEvent("model and reference changes require paused, settled generation")`.
     c. Else call `apply_configuration`; on `ReferenceImageError`, `ModelUnavailableError`,
        `ModelSwitchError`: emit `ErrorEvent(str(exc), fatal=False, cause=..., required_model=...)`
        and then emit a `config_ack` describing the **unchanged** current configuration (so the
        UI can roll back from backend truth). On `FatalModelError`: emit
        `state_changed(error, fatal=True)`. On success emit `config_ack` with `settled=True`.
     d. Serialization: the handler runs commands on the server thread one at a time, so a resume
        that arrives during an update is processed after it. Add a comment stating this and a
        test proving it (step "Tests").
   - `handle_pause`: on pause request emit `state_changed(paused, settled=False)` and call
     `backend.pause_generation(on_settled=lambda: self._emit_state_changed(server, "paused", settled=True))`.
     Confirm `server.send` is safe to call from the worker thread (the delivery thread already
     does). On resume, keep the compatibility gate; include `required_model` in the error.
   - `_emit_state_changed`: add the `settled` parameter.
   - Remove the `from textbrush.validation import validate_selection` inline import; import at
     module top.
3. Rust `commands_update_config.rs`: add `model_id: Option<String>`,
   `references: Option<Vec<String>>`, `preset: Option<String>` to `update_generation_config`
   and to the `json!` payload (omit `null`s is fine; Python defaults handle absence). Update
   the doc comment and the existing proptest to include the new fields. Fix the stale
   "stub awaiting integration" comment at the top of the file.
4. `types.ts`: add `ConfigAckPayload` and `ConfigAckMessage { type: 'config_ack' }` to
   `SidecarMessage`; add `settled?: boolean` to `StateChangedPaused`; add `cause?` and
   `required_model?` to `ErrorPayload`. Also add `model_id?`, `references?`, `preset?` to the
   `LaunchArgs`-derived init call if `main.ts` builds one (read `main.ts` around the
   `init_generation` invoke).
5. Confirm `src-tauri/src/sidecar.rs` forwards any JSON line as `sidecar-message` without a
   type whitelist; if it filters, add `config_ack`.

**Tests.**
- `tests/test_ipc_handler.py`:
  - Off-paused rejection: worker running -> editing update yields `ErrorEvent`, no ack.
  - Pause request then settle: assert two `state_changed(paused)` events, first
    `settled=False`, second `settled=True`, the second only after the blocked generate returns.
  - Acknowledged-and-incompatible (AC-STATE-4): Kontext active, update with two references ->
    `config_ack` with `compatible=False`, `required_model == "flux2-klein-4b"`,
    `reference_count == 2`; then `handle_pause` (resume) -> `ErrorEvent` naming the reason and
    no `state_changed(generating)`.
  - Rejected update rollback (AC-STATE-3): corrupt reference -> `ErrorEvent` followed by
    `config_ack` equal to the previous configuration; backend state unchanged.
  - Model swap failure surfaces as non-fatal error with the previous model still active;
    double failure surfaces as fatal `state_changed(error)`.
  - Resume during update: drive `handle_update_config` on one thread with
    `apply_configuration` patched to block on an event, call `handle_pause` from the test
    thread, release, and assert the resume outcome was decided against the post-update state
    (use the real single-threaded `IPCServer` loop from `tests/test_ipc_integration.py` if it
    exists; otherwise document the server-thread argument in the test docstring and assert the
    order of emitted messages).
  - Pre-start queueing: editing update before `handle_init` completes is applied on replay and
    acknowledged once.
- `tests/test_model_resolution_callsites.py` (AC-MODEL-5b structural): walk `textbrush/` with
  `ast`, collect every `Call` whose func name is `resolve_model_selection`, and assert the set
  of (file, enclosing function) equals exactly
  `{("textbrush/ipc/handler.py", "handle_init"), ("textbrush/cli.py", "main")}` (adjust the CLI
  entry once T08 lands; T07 may assert only the handler site and mark the CLI site as expected
  by T08). Plus a live test: patch `resolve_model_selection` with a counting wrapper, run
  `handle_init`, then two editing updates crossing the 1 -> 2 reference boundary, and assert
  call count 1 and `backend.model_id` unchanged.
- Rust: `cd src-tauri && cargo test commands_update_config` passes with the new fields.
- TypeScript: `cd src-tauri/ui && npm install && npm run typecheck`.

**Verify.** `uv run pytest tests/test_ipc_handler.py tests/test_ipc_integration.py tests/test_model_resolution_callsites.py -q`

**Done when.** The three wire mirrors list identical fields, and the tests above pass.

---

### T08. CLI model and reference arguments (S9)

**Goal.** `--model`, repeatable `--reference`, and `--preset` are validated before any model
load, decoded once, resolved through the shared resolver once, and fail with exit code 1.
Owned ACs: AC-INPUT-2, AC-MODEL-5b (CLI half), AC-COMPAT-1 (CLI part).

**Files.** `textbrush/cli.py`, `tests/test_cli.py`, `tests/test_cli_headless.py`,
`tests/e2e/test_full_workflow.py`, `tests/test_model_resolution_callsites.py`.

**Steps.**
1. `validate_args`: keep the cardinality/preset check but pass
   `aspect_ratio=args.aspect_ratio` to `validate_selection` (T03 signature). Check only that
   each `--reference` path exists, is a file, and has a supported extension (case-insensitive,
   use `SUPPORTED_EXTENSIONS`); do **not** decode here. Raise `ValueError` with the file named.
2. `main`: after `merge_cli_args_with_config`, resolve the model exactly once:
   ```python
   resolution = resolve_model_selection(selected_id=args.model or config.model.selected_id,
       reference_count=len(args.reference),
       availability=lambda slug: check_model_availability(slug, custom_dirs=config.model.directories))
   ```
   If `resolution.blocked`: print `resolution.reason` and, when `resolution.required_model`,
   the `--download-model` hint naming that model, to stderr; `sys.exit(1)`. Set
   `config.model.selected_id = resolution.model_id`.
3. Decode references once, after resolution and after `backend.initialize()` (the canvas
   depends on the loaded engine): call `backend.apply_configuration(model_id=...,
   reference_paths=[str(p) for p in args.reference], preset=args.preset)` and check
   `ack.compatible`; if not, print the reason and exit 1 without starting generation. Do this
   in both the interactive path and `run_headless`; remove the `references=tuple(normalize(...))`
   line and the `references`/`preset`/`width`/`height` parameters that 47f6151 added to
   `start_generation` calls (the backend now owns them).
4. Order guarantee: validation (step 1) and resolution (step 2) happen before
   `backend.initialize()`; decoding (step 3) happens after `initialize()` but before
   `start_generation()`. Write this order in the `main` docstring.
5. Keep `--preset` choices from `validation.EDITING_PRESETS`; keep `--model` choices from
   `iter_model_slugs()`.
6. Update the `--help` text so `tests/e2e/test_full_workflow.py::test_help_shows_all_required_options`
   covers `--model`, `--reference`, `--preset`.

**Tests.**
- `tests/test_cli.py`: parameterized valid/invalid combinations of `--model` and `--reference`
  counts 0..5 (use fixture paths); for invalid, assert `SystemExit.code == 1`, stderr names the
  model and the rule, stdout is empty, and `TextbrushBackend` was never constructed
  (patch it). Assert `--prompt ""` also exits 1 (numeric equality between the two codes).
  Assert `--reference` order is preserved into `apply_configuration`'s `reference_paths`.
  Assert `--aspect-ratio 16:9 --model flux2-klein-4b --reference x` exits 1.
  Assert `IMG_1234.JPG` is accepted. Assert an explicitly requested unavailable model exits 1
  with the download hint and never substitutes (patch `check_model_availability`).
- `tests/test_cli_headless.py`: existing tests unchanged; add one with two references and
  `flux2-klein-4b` asserting `apply_configuration` was called once with both paths in order,
  and that `normalize` (patched) was called exactly once per path.
- `tests/test_model_resolution_callsites.py`: enable the CLI call-site assertion; add a test
  that `main` calls the resolver once per process (counting wrapper).
- `tests/e2e/test_full_workflow.py`: subprocess run of
  `uv run textbrush --prompt x --model flux1-kontext-dev` (no reference) exits 1 with the
  cardinality message and empty stdout.

**Verify.** `uv run pytest tests/test_cli.py tests/test_cli_headless.py tests/e2e/test_full_workflow.py tests/test_model_resolution_callsites.py -q`

**Done when.** `normalize` is not imported by `cli.py` (decode lives in backend), the resolver
has exactly two production call sites, and all listed tests pass.

---

### T09. Desktop shell: file dialog command (S10a)

**Goal.** A Tauri command that opens the native multi-file dialog and returns only a list of
paths. No validation in Rust.

**Files.** `src-tauri/Cargo.toml`, `src-tauri/src/commands_reference_dialog.rs` (new),
`src-tauri/src/main.rs`, `src-tauri/capabilities/default.json`, `src-tauri/tauri.conf.json`,
`src-tauri/ui/package.json`.

**Steps.**
1. Add `tauri-plugin-dialog = "2"` to `[dependencies]`; register `.plugin(tauri_plugin_dialog::init())`
   in `main.rs`.
2. `commands_reference_dialog.rs`: `#[tauri::command] pub fn pick_reference_files(app: tauri::AppHandle) -> Result<Vec<String>, String>`
   using `app.dialog().file().add_filter("Images", &["png","jpg","jpeg","PNG","JPG","JPEG"]).blocking_pick_files()`;
   map `None` (cancel) to `Ok(vec![])`; convert each path with `to_string_lossy`. Add a unit test
   for the path-conversion helper only (the dialog itself is untestable headlessly).
3. Register the command in `generate_handler!`.
4. Capabilities: add `"dialog:allow-open"` to `permissions`.
5. Previews: the UI will render `convertFileSrc(path)`. Set `app.security.assetProtocol.scope`
   in `tauri.conf.json` to include `"$HOME/**"`, `"$DESKTOP/**"`, `"$DOCUMENT/**"`,
   `"$PICTURE/**"`, `"$DOWNLOAD/**"` (keep any existing entries). Add
   `"core:path:default"` if `convertFileSrc` needs it in this Tauri version.
6. `cargo check` (macOS) or note in the status row if the Linux box lacks glib headers.

**Verify.** `cd src-tauri && cargo check && cargo test`

**Done when.** The command compiles, is registered, and the capability lists the dialog
permission.

---

### T10. Desktop UI: picker, selector, presets, acknowledgement (S10b)

**Goal.** The desktop offers a model selector, a reference picker with previews, removal and
replacement, the six editing presets, compatibility messaging, and enables editing controls
only on the settled signal; nothing is shown as active before `config_ack`. Owned ACs:
AC-INPUT-1, AC-INPUT-3 (desktop part), AC-MODEL-5b (UI half), AC-PRESET-1 (UI part).

**Files.** `src-tauri/ui/reference_picker.ts` (new), `src-tauri/ui/config_controls.ts`,
`src-tauri/ui/main.ts`, `src-tauri/ui/types.ts`, `src-tauri/ui/index.html`,
`src-tauri/ui/styles/*.css`, `src-tauri/ui/reference_picker.test.js` (new),
`src-tauri/ui/integration.test.js`, `src-tauri/ui/package.json`, `tests/test_html_structure.py`.

**Steps.**
1. `reference_picker.ts` (pure logic, no DOM, no Tauri import):
   - `export const MAX_REFERENCES = 4;`
     `export const SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg'];`
   - `export function applyPickedPaths(current: string[], picked: string[]): { references: string[]; errors: string[] }`
     appends in order, rejects unsupported extensions case-insensitively with a per-file
     message, rejects beyond four with a message naming the limit, keeps duplicates.
   - `export function removeReference(current: string[], index: number): string[]`
   - `export function replaceReference(current: string[], index: number, path: string): { references: string[]; errors: string[] }`
   - `export function previewLabel(path: string, position: number): string` returning
     `Reference ${position + 1} of N: ${basename}` (no content claims).
   - `export const EDITING_PRESETS = [...]` with the six identifiers and dimensions, spelled
     exactly as in `architecture.md`; a comment names `textbrush/validation.py` as the owner.
   - `export function isEditingModel(modelId): boolean` from a `MODELS` table with
     `{ id, displayName, minReferences, maxReferences }` for the three slugs; comment names
     `textbrush/model/registry.py` as owner.
   - `export function compatibilityMessage(modelId, referenceCount): string | null` mirroring
     the wording rule of T03 for pre-highlighting only; backend truth still arrives in the ack.
2. `types.ts`: extend `AppState` with `modelId: string | null`, `references: string[]`
   (acknowledged), `pendingReferences: string[] | null`, `preset: string | null`,
   `settled: boolean`, `compatibility: { compatible: boolean; reason: string | null; requiredModel: string | null } | null`,
   `configUpdateInFlight: boolean`. Extend `Elements` with the new controls.
3. `index.html`: inside `.config-controls` add:
   - a `<fieldset id="model-selector">` with three radios `name="model"` and visible labels
     (display names plus a capability hint "text to image", "1 reference", "1 to 4 references");
   - a `<div id="reference-picker">` with `<button id="reference-add" type="button">Add reference images</button>`,
     `<ul id="reference-list" aria-live="polite">`, and `<div id="reference-error" role="alert">`;
   - a `<fieldset id="editing-presets">` with six radios `name="editing-preset"`, hidden via
     class when a text model is active (text-mode aspect-ratio group hidden when an editing
     model is active).
   Each list item renders `<img alt="<previewLabel>">`, the filename as text, and two buttons
   `aria-label="Remove reference N: <file>"` and `aria-label="Replace reference N: <file>"`.
4. `main.ts`:
   - Cache the new elements; wire `reference-add` to `invoke('pick_reference_files')` then
     `applyPickedPaths`; wire remove/replace; render previews with `convertFileSrc`.
   - Send editing changes through `invoke('update_generation_config', { prompt, aspect_ratio,
     width, height, model_id, references, preset })` only when `state.settled` is true and
     `configUpdateInFlight` is false; set `configUpdateInFlight = true` and disable the pause
     button, model radios, picker buttons, and preset radios until `config_ack` or `error`.
   - Handle `config_ack`: set `modelId`, `references`, `preset`, `compatibility`; clear
     `pendingReferences`; re-enable controls; render the incompatibility reason as text in
     `#reference-error` and pre-highlight `required_model`'s radio label with a
     "recommended" badge (text, not colour only). Never auto-select it.
   - Handle `state_changed(paused, settled)`: `state.settled = settled === true`; enable
     editing controls only when settled. On `generating`/`loading`: `settled=false`, disable.
   - Handle `error` during an in-flight update: re-enable controls and restore the last
     acknowledged values into the DOM (rollback from `state`, not from the DOM).
   - Do not call any model resolution in the frontend; the selector reflects `config_ack`.
5. `config_controls.ts`: when an editing model is active, `getCurrentConfig` returns
   `aspect_ratio: 'custom'` and the preset's width/height so legacy prompt updates stay valid
   through the handler's text-mode validation.
6. Styles: previews at most 96 px tall, list wraps, container has `overflow: visible` or
   scrolls without clipping; respect existing theme variables and font-size classes.
7. `package.json`: add `"build:modules": "tsc"` already exists; ensure `reference_picker.ts`
   is included by `tsconfig.json` (`*.ts` already matches).
8. Tests (`node --test`):
   - `reference_picker.test.js`: pure-function tests for add (order, duplicates, case-insensitive
     `.JPG`, fifth file rejected with message, `.bmp` rejected), remove, replace, previewLabel,
     compatibility messages for each (model, count) cell.
   - `integration.test.js` with jsdom: render `index.html`, stub `window.__TAURI__` invoke and
     `convertFileSrc`, drive `applyPickedPaths` through the UI helper with a supplied path
     list (never the dialog), and assert four previews with filenames, removal of the second,
     replacement of the third; assert controls are disabled until a `state_changed(paused,
     settled=true)` is dispatched; assert that after an editing change the UI still shows the
     previous model until `config_ack` arrives (VQ-S10-005); assert an `error` rolls the DOM
     back; assert adding a second reference under Kontext never changes the selected radio
     (AC-MODEL-5b UI half).
9. Fix the pre-existing 61 failures: `tests/test_config_controls*.py` read compiled
   `config_controls.js`. Either add `src-tauri/ui/config_controls.js` to the tracked compiled
   outputs by running `npm run build:modules` and committing it (the repository already tracks
   `list-manager.js`, `font-size-manager.js`, `png-metadata.js`), or make those tests skip
   with a clear reason when the file is absent. Prefer committing the compiled file for
   consistency with the existing tracked modules, and also commit `reference_picker.js`.
10. `tests/test_html_structure.py`: add assertions for the new element ids and ARIA attributes.

**Verify.**
```bash
cd src-tauri/ui && npm install && npm run check && npm run test && npm run build
uv run pytest tests/test_html_structure.py tests/test_config_controls.py tests/test_config_controls_integration.py -q
```

**Done when.** All UI tests pass, `bundle.js` is rebuilt and committed, and no test drives the
native dialog.

---

### T11. Headless-browser accessibility harness (S11)

**Goal.** Keyboard reachability, accessible names, text-form errors, and the four-preview
layout are asserted against the rendered interface in a real browser with the Tauri bridge
stubbed. Owned AC: AC-ACCESS-1.

**Files.** `src-tauri/ui/a11y/` (new: `playwright.config.ts`, `tauri-stub.ts`,
`reference-controls.spec.ts`, `serve.mjs`), `src-tauri/ui/package.json`, `Makefile`
(`test-ui-a11y` target), `docs/` (one paragraph in the developer section of README or
`docs/troubleshooting.md` on installing browsers).

**Steps.**
1. Add dev dependencies `@playwright/test` and `esbuild` is already present. Add scripts
   `"build:a11y": "esbuild main.ts --bundle --outfile=a11y/bundle.a11y.js --format=esm --target=es2022 --alias:@tauri-apps/api/core=./a11y/tauri-stub.ts --alias:@tauri-apps/api/event=./a11y/tauri-stub.ts"`
   and `"test:a11y": "npm run build:a11y && playwright test -c a11y/playwright.config.ts"`.
2. `tauri-stub.ts` exports `invoke`, `listen`, `convertFileSrc`: `invoke` records calls and
   returns canned results (`pick_reference_files` returns the path list the test injected via
   `window.__a11yPaths`); `listen` stores handlers on `window.__a11yEmit(type, payload)` so
   tests can dispatch `state_changed` and `config_ack`; `convertFileSrc` returns a data URL of
   a 1x1 PNG.
3. `serve.mjs`: static server for `src-tauri/ui` on a free port, serving an `a11y/index.html`
   copy of `index.html` whose script tag points at `bundle.a11y.js`.
4. Spec assertions (Playwright, Chromium):
   - Tab from the prompt input reaches, in order: model radios, add button, each preview's
     remove and replace buttons, preset radios; use real `keyboard.press('Tab')` and
     `document.activeElement` checks. Activate remove with `Enter` and `Space`.
   - `getByRole('button', { name: /Remove reference 2 of 4/ })` and the img `alt` values
     exist for four injected paths; alt text contains the filename and position and no other
     words.
   - Emit a `config_ack` with `compatible=false`; assert the reason is visible text inside
     `[role=alert]` and `getComputedStyle` colour is not the only difference (check text
     content non-empty).
   - Layout at the supported window size `1024x768` (from `tauri.conf.json`) and at the
     smallest size the app allows if resizable (it is not; test 1024x768 and 1280x800): with
     four previews, every control's `boundingBox` lies inside the viewport and inside its
     scroll container, and `scrollWidth <= clientWidth` on `.config-controls`.
   - Theme and font-size: toggle the theme button and each font-size radio; assert the new
     controls' computed `color` and `font-size` change accordingly (values differ between
     settings).
   - Disabled state: before any `state_changed(paused, settled=true)`, the add button and
     model radios report `disabled === true` and clicking them does not call `invoke`.
5. `Makefile`: `test-ui-a11y: cd src-tauri/ui && npx playwright install chromium && npm run test:a11y`.
   Do not add it to `make test` (browser download is heavy); document it.

**Verify.** `cd src-tauri/ui && npx playwright install chromium && npm run test:a11y`

**Done when.** The spec passes headless with no Python backend running.

---

### T12. Cross-cutting provenance integration tests (S12)

**Goal.** Against the real handler, backend, worker, and mock engine (only the pipeline is a
double), prove per-result provenance across pause/update/resume/generate/navigate/delete
sequences and the six adversarial interleavings. Owned AC: AC-STATE-2.

**Files.** `tests/test_state_provenance_integration.py` (new),
`tests/e2e/test_config_change_flow.py` (new). Fix any production gap in the owning module's
file, not in these tests.

**Steps.**
1. Build a helper that constructs `MessageHandler(config)` with `create_engine` patched to
   return a `MockInferenceEngine` whose `generate` can be gated by a `threading.Event`, and
   a fake server that records every message in order. Drive `handle_init` with
   `start_paused` semantics as the app does today.
2. Scenarios (each its own test, named after the guarantee):
   - `test_stale_result_never_visible`: start generation A, pause, wait settled, switch to
     Kontext with one reference, resume; assert no `image_ready` whose record carries model A
     appears after the `config_ack`.
   - `test_control_enablement_window_is_empty`: the first `state_changed(paused, settled=true)`
     is emitted only after the gated `generate` returned.
   - `test_snapshot_attribution_across_two_changes`: three configurations in one session;
     for each delivered image, read the preview PNG metadata (`Prompt`, `Model`, `Seed`,
     `Width`, `Height`) and the handler's index map record; assert they match the
     configuration active when that image's generation started, through navigation and a
     `handle_delete` of the middle image.
   - `test_no_partial_reference_set`: switch from two references to three while a generation
     is gated; assert the engine never received a set that is neither the old nor the new
     tuple.
   - `test_decode_lifetime`: acknowledge, delete the source file, generate twice; both use the
     held data; after `handle_abort`, `backend.references == ()`.
   - `test_resume_during_update`: as in T07 but through the full stack.
   - `test_no_reference_identity_persisted`: for every preview and accepted file, the PNG key
     set is the closed set from T06 and no chunk value contains any reference path, basename,
     or the `reference_ids` strings.
3. `tests/e2e/test_config_change_flow.py`: subprocess-level headless run with
   `--model flux2-klein-4b` and two fixture references against the mock engine (patch via an
   env var only if one already exists; otherwise mark `@pytest.mark.slow` and gate on
   `--run-slow`). Do not run `--run-slow` yourself.

**Verify.** `uv run pytest tests/test_state_provenance_integration.py -q` (twice).

**Done when.** All seven scenarios pass deterministically and any production fix made here is
committed under the owning module's task label.

---

### T13. User documentation and release notes (S13)

**Goal.** A reader who has not seen the spec can use reference editing from desktop and CLI.
Owned AC: AC-DOC-1.

**Files.** `README.md`, `docs/reference-editing.md` (new), `docs/configuration.md`
(cross-link only), `CHANGELOG.md`.

**Steps.**
1. `docs/reference-editing.md` sections, each with real content:
   - Models and capabilities (table: slug, display name, mode, reference count).
   - Supported reference formats and the four-file limit; duplicates allowed.
   - Output presets: the six identifiers with dimensions; default `landscape-medium`; text-mode
     aspect ratios unchanged for schnell.
   - CLI examples: one Kontext example, one FLUX.2 example with three references, one showing
     the validation error for two references on Kontext. Every command must run as written
     against `uv run textbrush --help` (check flags exist).
   - Desktop walkthrough: pause, wait for the settled indicator, pick files, choose model,
     choose preset, resume; what the compatibility message means; why the model is never
     switched automatically.
   - Model storage, gated licence, credentials (`TEXTBRUSH_HF_TOKEN` or whatever
     `docs/configuration.md` documents), `--download-model <slug>`, hardware and memory
     expectations (state that editing models need substantially more VRAM than schnell and
     that two models are never held in memory at once).
   - Prompt guidance: prompt wording controls identity and reference use; no guaranteed
     identity fidelity; references are equal and untyped.
   - Privacy: local-only processing; PNG metadata key list; JPEG has none; no reference paths,
     hashes, or bytes are written.
   - Limitations and roadmap: no face-aware cropping, masks, roles, weights, iterative editing;
     face-aware selection is a later direction.
2. `README.md`: shorten the section moved in T01 to a short paragraph plus a link to
   `docs/reference-editing.md`; keep two copy-pasteable examples.
3. `CHANGELOG.md` "Unreleased": "Added" entry describing the additive editing workflow, naming
   FLUX.2 [klein] 4B as required for two to four references, and a "Changed" entry for the
   diffusers minimum version.
4. Verify each documented command parses: run each with `--help`-style dry checks or with a
   patched backend in a throwaway script; delete the script afterwards.

**Verify.** Manual review against the AC-DOC-1 list; `uv run textbrush --help` shows every
flag used in the examples.

**Done when.** Every bullet in AC-DOC-1 maps to a paragraph with content.

---

### T14. Epic closure

**Goal.** The epic's own records reflect what shipped.

**Files.** `specs/epic-multi-reference-flux-image-editing/reconciliation.json`,
`epic-state.json`, `S3-reference-normalization/result.json`, this file.

**Steps.**
1. Run the full fast suite, `make check-all`, `cd src-tauri/ui && npm run check && npm test`,
   and `cd src-tauri && cargo test`. Record results in the status table.
2. Update `reconciliation.json`: one verdict per AC with the test file and test name that
   proves it. Any AC still `unverifiable` must say why.
3. Update `epic-state.json`: `completed_stories` S1 through S13, `status: "complete"` only if
   every AC holds. Set `S3-reference-normalization/result.json` `status` to `done`.
4. Remove any temporary files created during the tasks (scratch scripts, backups). Do not
   remove `textbrush-missed-acceptance-criteria.md` or `implementation-state.json`; they
   predate this epic.
5. Ask the user before running the hardware-gated smoke test described in `spec.md` §15; it
   is the release gate and needs real weights.

**Done when.** The status table is all `done` or has an explicit `blocked` reason per row.
