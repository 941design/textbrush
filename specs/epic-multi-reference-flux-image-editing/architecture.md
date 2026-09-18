# Epic Architecture: Multi-Reference FLUX Image Editing

Derived from `exploration.json` and `spec.md`. This is the operational document every
agent on this epic reads. It records the paradigm in force, the modules this epic touches
or creates, the boundary rules, and the seams between stories.

## Paradigm

The codebase follows a **layered pipeline with a strategy-pattern inference layer**, in a
single process, with **two independent composition roots** over the same core.

- Layers, outer to inner: `ipc` → `backend` → `worker` → `inference`, with `buffer`,
  `config`, `paths` and `model` as leaves that import nothing internal.
- The inference layer is a strategy behind the `InferenceEngine` ABC, selected by a
  string-keyed factory.
- Generation is a **producer/consumer pipeline**: the worker fills `ImageBuffer`, a
  delivery thread in the IPC handler drains it. It is not pub/sub and not event-sourced.
- `cli` is a second composition root: it drives `backend` directly and never imports
  `ipc`. This is why validation must exist on both paths.

This epic does not change the paradigm. It extends the inference strategy to a second and
third engine, introduces one new leaf module and one new shared-validation module, and
adds a state-machine discipline (quiescence and acknowledgement) that the current code
approximates but does not implement.

## Module map

| Module | Location | Owns | Epic impact |
|---|---|---|---|
| `ipc` | `textbrush/ipc/` | Wire schema (`protocol.py`), dispatch (`server.py`), session orchestration and the delivered-image index map (`handler.py`) | New commands/events for model + reference set; pause gate; acknowledgement event |
| `backend` | `textbrush/backend.py` | Coordinator. Engine handle, buffer, worker, preview dir, PNG metadata writing, accept/skip/abort | Runtime engine swap; snapshot construction; reference lifetime |
| `worker` | `textbrush/worker.py` | The generation loop, pause/resume/stop events, per-iteration capture | Quiescence signal; discard of pre-change results |
| `buffer` | `textbrush/buffer.py` | In-flight, not-yet-delivered images and their generation metadata (`BufferedImage`) | Carries model identity and session-local reference identity |
| `inference` | `textbrush/inference/` | `InferenceEngine` ABC, `GenerationOptions`, `GenerationResult`, engine factory, FLUX engines | Reference-carrying request contract; two new engines |
| `model` | `textbrush/model/` | Local checkpoint discovery and download against the HF cache | Per-model registry replacing the single hardcoded checkpoint |
| `config` | `textbrush/config.py` | On-disk TOML schema and the file→env→CLI merge | Additive fields with safe defaults (AC-COMPAT-1) |
| `cli` | `textbrush/cli.py` | Argument parsing, validation, headless driving of `backend` | `--model`, repeatable `--reference`, editing presets, exit codes |
| `paths` | `textbrush/paths.py` | Path constants and `display_path()` | Unchanged |
| `references` | `textbrush/references/` *(new)* | Decode, EXIF orientation, RGB conversion, uniform scale, centered padding, and the lifetime of normalized reference data | Created by this epic |
| `validation` | `textbrush/validation.py` *(new)* | Model/reference cardinality and preset compatibility rules, shared by `cli` and `ipc` | Created by this epic |
| `desktop-shell` | `src-tauri/src/` | Tauri commands and the sidecar transport | New command(s) for reference selection; file-dialog plugin |
| `desktop-ui` | `src-tauri/ui/` | TypeScript UI, config controls, PNG metadata parsing | Reference picker, previews, compatibility messaging, editing presets |
| `docs` | `README.md`, `docs/`, `CHANGELOG.md` | User-facing documentation and release notes | Reference-editing workflow docs per `spec.md` §16 (S13) |

**Why `validation` is a module rather than duplicated logic.** `cli` and `ipc` are separate
composition roots, so today every rule that must hold on both paths is written twice
(the aspect-ratio tables are already triplicated and have drifted — `ipc/handler.py`
accepts three ratios where `cli.py` offers six). This epic adds cardinality rules that
must be identical on both paths by acceptance criterion (`AC-INPUT-2`). Writing them once
is the cheaper correctness guarantee; a fifth uncoordinated copy is the failure mode to
avoid.

**Why `references` is a module rather than helpers on `backend`.** Decoded reference data
has a lifetime tied to an acknowledged configuration (`AC-PROCESS-3`), which is a
different lifetime from the preview files `backend` manages. Keeping it separate keeps
`backend` a coordinator rather than a second resource owner, and keeps normalization —
the most heavily property-tested logic in the epic — importable without dragging in the
backend.

## Boundary rules

1. No direct imports across module boundaries except along the existing acyclic direction:
   `ipc` → `backend` → `worker` → `inference`; leaves import nothing internal. The
   dependency graph currently has **no violations** and must still have none at the end.
2. `references` and `validation` are leaves. They must not import `backend`, `worker`, or
   `ipc`. This is what lets both composition roots use them.
3. `buffer`, `inference`, and `worker` must not import upward into `backend` or `ipc`.
4. The wire schema is owned by `ipc/protocol.py`. Rust and TypeScript mirror it by hand;
   any change to a message shape is three coordinated edits (`protocol.py`,
   the Rust `json!` payload builder, `types.ts`). No story may change one without the
   others.
5. Reference identity is **session-local**. It may live in memory and cross IPC, but it
   must never be written into generated output files (`AC-META-1`).
6. Cardinality and preset rules live in `validation` and are called from both `cli` and
   `ipc`. No story re-implements them locally.

## Seams

*Populated by the story planner once the story split is known.* Each seam is a typed
contract between two stories that can be implemented and verified independently.

Known seam candidates from exploration:

- `InferenceEngine.generate()` request contract — the boundary between the engine stories
  and every caller (`worker`, `backend`, the mock in `tests/mocks.py`).
- `validation` public surface — the boundary between the CLI story and the IPC story.
- `references` public surface — the boundary between normalization and everything that
  consumes normalized data.
- The acknowledgement message shape — the boundary between the backend state story and the
  desktop UI story, crossing all three languages.

### Preset lexicon (canonical — owned by `validation`)

The six editing presets have exactly one spelling across every module and every language.
`spec.md` §5.5 names the orientations and tiers but no identifier; this is that identifier,
declared here because four modules and three languages must agree on it and no single one of
them owns it by position:

| Identifier | Orientation | Small | Medium | Large |
|---|---|---|---|---|
| `landscape-small` / `landscape-medium` / `landscape-large` | Landscape (4:3) | 512x384 | 768x576 | 1024x768 |
| `portrait-small` / `portrait-medium` / `portrait-large` | Portrait (3:4) | 384x512 | 576x768 | 768x1024 |

Scheme: `<orientation>-<tier>`, lowercase, hyphen-separated. `validation`
(`textbrush/validation.py`, S4) owns the constant; `config`, `cli`, `ipc`, and `desktop-ui`
consume it and must not re-spell it. This is deliberately unlike the text-only aspect-ratio
strings (`1:1`, `16:9`) so the two vocabularies cannot be confused. S1 spelled it first, in
`config`, before the owner existed — that is a known encroachment recorded in the ownership
ledger, not a licence for a second spelling.

### Selected-model representation

`spec.md` §7.3 resolves the model from the reference count whenever the user did not choose
one, and §5.1 forbids silently replacing a model the user *did* choose. Those two rules are
only jointly satisfiable if "no choice made" is representable. The configuration schema
therefore carries the selected model as nullable, with null meaning *resolve per §7.3*, and
no default configuration file may materialize a concrete model id — writing one converts
every user into having made an explicit choice they never made.

Model selection lives under `[model]` alongside the existing model-directory settings, not
under `[editing]`: the selected model may be FLUX.1 schnell, which is not an editing model,
so `[editing]` would be a self-contradictory home for it. `[editing]` holds only settings
that apply when an editing-capable model is active.

## Implementation constraints

- **Package manager is `uv`.** Mandated by project `CLAUDE.md`.
- **Never tailor production code to tests.** Project `CLAUDE.md`. The path-injection seam
  in `spec.md` §5.2 is a product requirement (the dialog yields paths; selection logic
  consumes a path list), not a test accommodation — implement it as the former.
- **`make check-all` runs no tests.** Lint/format/typecheck only. Story completion needs
  `make test` as well.
- **Real model weights are gated.** Only `tests/conftest.py:64-88` loads them, only under
  `--run-slow`. Everything else stubs `engine._pipeline`. Keep that line where it is.
- **IPC validation errors are `ErrorEvent(message, fatal=False)`**, not raised exceptions.
- **CLI exit codes**: 0 success, 1 runtime, 2 argparse. Reference/cardinality/preset
  failures use the same code as an empty-prompt failure (`AC-INPUT-2`).
- **CONTRACT-style docstrings** (`Inputs:`/`Outputs:`/`Invariants:`/`Properties:`) on new
  public behavioral functions, matching `inference/base.py` and `cli.py`.
- **No image fixtures exist** and there are no corrupt-file test patterns. That
  infrastructure is part of this epic's cost, not a free assumption.
- **No browser test harness exists.** `AC-ACCESS-1` requires one (headless, desktop bridge
  stubbed). Treat adopting it as real scope.
- **The diffusers floor rises.** The pinned version predates the editing pipelines. The
  existing schnell path must keep its behavior, options, metadata and exit semantics
  across the uplift — contract-level, not pixel-identical (`spec.md` §13).

## Order-Sensitive Composition

**This epic composes order-sensitive subsystems. Yes.**

The composed flow is **configuration change under concurrent generation**: a user pauses,
changes the model and/or reference set, the backend acknowledges, and generation resumes —
while a generation thread, an IPC command thread, and an image-delivery thread all touch
the same state. Correctness here depends on ordering and interleaving, not just on each
step being individually right. The existing code already contains one live instance of the
hazard: `state_changed(paused)` is emitted before the worker is quiescent, and an in-flight
result is `buffer.put()` *after* `update_config` has called `buffer.clear()`, so the first
image a user sees after a reference swap can be one generated with the previous references.

**Participating modules** (name — location):

- `ipc` — `textbrush/ipc/` (command serialization, acknowledgement, delivery thread)
- `backend` — `textbrush/backend.py` (config application, buffer clear, engine swap)
- `worker` — `textbrush/worker.py` (generation loop, pause/resume events, quiescence)
- `buffer` — `textbrush/buffer.py` (the queue the race is observed on)
- `references` — `textbrush/references/` *(new)* (decoded data whose lifetime is bound to an
  acknowledged configuration)
- `desktop-ui` — `src-tauri/ui/` (must not present state as active before acknowledgement)

**Candidate whole-flow guarantees** that must hold across orderings and interleavings:

1. **No stale result is ever observable.** An image whose generation began before an
   acknowledged model or reference change never reaches the buffer or the review history,
   regardless of when it completes relative to the clear (`AC-STATE-1`).
2. **Controls are enabled only on quiescence.** The window in which the UI offers a model
   or reference control that the backend would refuse is empty (`AC-STATE-1`).
3. **Every delivered result is attributable to exactly one snapshot**, and that snapshot is
   immutable from the moment the request is created (`AC-STATE-2`, `spec.md` §9).
4. **A reference set is never partially applied.** No generation observes a mix of old and
   new references, and no mode switch is observable with a model and preset from different
   modes (`AC-PRESET-1`, `spec.md` §5.4).
5. **Decoded reference data outlives exactly its configuration** — released on change,
   abort, fatal error and shutdown, and never re-read from disk mid-configuration
   (`AC-PROCESS-3`).
6. **Command serialization holds under contention.** A resume arriving during an update
   takes effect only after acknowledgement; a failed update leaves the previous
   configuration loaded and ready (`AC-STATE-3`, `spec.md` §5.4, §8).

Stories touching any module in the list above inherit these guarantees as verification
obligations, not just their own local acceptance criteria.
