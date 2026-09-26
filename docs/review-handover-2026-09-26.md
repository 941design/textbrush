# Project review: implementation handover

Review date: 2026-09-26. Repository: `caricature-builder` (product/package: Textbrush).
Reviewed HEAD: `676a968`. Paths and line numbers below refer to this baseline; locate symbols again after edits.

This document transfers the review findings and proposed remediation to a new implementation context. It is not evidence that the fixes have been implemented. The review made no production or test source changes. The user subsequently requested this document, including lower-priority findings and task sign-off tracking.

## Instructions for the next implementor

1. Read repository guidance, including `CLAUDE.md`, and check for any newly applicable `AGENTS.md` files. Use `uv` for Python dependency/environment management. Run appropriate lint and formatting checks. Do not rewrite history.
2. Inspect `git status` before editing. At review start and finish there were two pre-existing changes: modified `src-tauri/gen/schemas/macOS-schema.json` and untracked `src-tauri/gen/schemas/linux-schema.json`. Preserve them; they are not review-generated changes to discard.
3. Revalidate each finding against the current code before changing it. Implement focused fixes, not a wholesale rewrite of the three-language architecture.
4. Do not run model-heavy integration tests without user confirmation: `CLAUDE.md` explicitly says, “NEVER run integration tests without user confirmation, as they are very resource intensive.” Fast unit tests, mocks, and static checks supplied most review evidence. This handover does not grant new permission to run expensive tests, publish, or release.
5. Update the task register and its detailed task entry together. Record actual commands, results, commit IDs, and limitations. Do not mark a task done solely because a mocked test passed when its acceptance criteria require packaged-app or model validation.
6. Keep the two existing `BACKLOG.json` findings linked to R15 and R16. This handover does not modify that file or create feature epics. If updating canonical backlog/feature records later, use the applicable project-record workflow.

## Status and evidence conventions

Statuses: `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `DEFERRED`, `NOT_A_BUG`.

`PLANNED` means implementation is pending for confirmed defects and investigation is pending for candidates. `BLOCKED` must include the missing prerequisite. `DEFERRED` needs a reason. `NOT_A_BUG` needs counter-evidence or an explicit product decision. `DONE` needs acceptance evidence and a sign-off.

Evidence levels:

- **Reproduced:** a lightweight execution or the existing test suite demonstrated the behavior.
- **Code-confirmed:** the code path is clear, but the full user-facing scenario was not executed.
- **Investigate:** a plausible issue or hardening opportunity; reproduce or reject it before committing to a fix.

Priority: **P1** release/core-workflow blocker or serious recovery failure; **P2** user-visible correctness/reliability defect; **P3** lower-impact correctness, test quality, or maintenance work. Candidate priorities are provisional.

For each task replace its sign-off line with: `DONE — YYYY-MM-DD — implementor/reviewer — commit — verification evidence`. If validation remains incomplete, keep the status honest and describe the gap.

## Task register

| ID | Priority | Evidence | Task | Status | Sign-off |
| --- | --- | --- | --- | --- | --- |
| R01 | P1 | Reproduced | Preserve acceptance state on save failure | PLANNED | — |
| R02 | P1 | Reproduced | Report worker errors without waiting for an image | DONE | `bf9eb15`; see detailed evidence |
| R03 | P1 | Reproduced | Make base wheel installation importable | IN_PROGRESS | `0b5563a`; see detailed evidence |
| R04 | P1 | Code-confirmed | Install frontend dependencies in release CI | PLANNED | — |
| R05 | P1 | Code-confirmed | Bundle a portable Python runtime | PLANNED | — |
| R06 | P2 | Code-confirmed | Resolve the CLI/desktop workflow mismatch | PLANNED | — |
| R07 | P2 | Code-confirmed | Forward desktop model/reference launch arguments | PLANNED | — |
| R08 | P2 | Reproduced | Make configuration changes and image publication atomic | PLANNED | — |
| R09 | P2 | Reproduced | Encode actual JPEG output when requested | PLANNED | — |
| R10 | P2 | Mixed: reproduced/code | Honor output path and directory overrides | PLANNED | — |
| R11 | P2 | Code-confirmed | Release deleted-image pixel memory | PLANNED | — |
| R12 | P2 | Code-confirmed | Surface unexpected sidecar exit | PLANNED | — |
| R13 | P2 | Reproduced | Read installed distribution version correctly | DONE | `0b5563a`; see detailed evidence |
| R14 | P2 | Code-confirmed | Preserve desktop seed zero | PLANNED | — |
| R15 | P2 | Code-confirmed; existing backlog | Honor CLI aspect ratio for reference-capable models | PLANNED | — |
| R16 | P3 | Code-confirmed; existing backlog | Resolve generated-schema tracking policy | PLANNED | — |
| R17 | P2 | Reproduced | Fix stale FLUX.2 test and isolate model availability | DONE | `0b5563a`; see detailed evidence |
| R18 | P3 | Code-confirmed | Replace vacuous contract tests with behavioral coverage | PLANNED | — |
| R19 | P2 | Investigate | Coordinate abort/close, process cleanup, and UI exit | PLANNED | — |
| R20 | P2 | Investigate | Settle worker before engine unload | IN_PROGRESS | `bf9eb15`; see detailed evidence |
| R21 | P2 | Investigate | Await frontend event subscription before initialization | PLANNED | — |
| R22 | P3 | Code-confirmed | Build current frontend bundle before regression tests | DONE | `0b5563a`; see detailed evidence |
| R23 | P2 | Investigate | Preserve backpressure and results when buffer is full | PLANNED | — |
| R24 | P3 | Code-confirmed | Return the validated cached model snapshot | DONE | `0b5563a`; see detailed evidence |
| R25 | P2 | Investigate | Reconcile UI acceptance errors and in-flight delivery | PLANNED | — |
| R26 | P3 | Investigate | Check Linux packaging and release runner compatibility | PLANNED | — |
| R27 | P3 | Investigate | Review asset-protocol scope and CSP deliberately | PLANNED | — |
| R28 | P3 | Code-confirmed | Remove stale implementation narratives and align docs | PLANNED | — |
| R29 | P2 | Investigate | Release partially loaded candidate before model recovery | PLANNED | — |

## Architecture and constraints worth preserving

- Python `TextbrushBackend` owns inference engine, acknowledged model/references/canvas, and generation worker. `GenerationWorker` produces `BufferedImage` objects into `ImageBuffer`.
- Python `MessageHandler` owns delivered-image indexes, ordering, deletion state, and preview delivery. JSON-line IPC travels over the Rust-managed Python process's stdin/stdout.
- Rust launches the sidecar, forwards messages as Tauri events, and provides commands and process exits. TypeScript owns desktop presentation and input handling.
- Model/reference changes require a paused, settled worker. References are normalized at configuration acknowledgement against the model's reference canvas. Preserve this invariant when changing sizes or launch flow.
- Reference paths and session-local reference identities must not leak into saved image metadata. Existing normalization, provenance, and metadata tests are relevant regression protection.
- Do not load old and new full models simultaneously as a routine switching strategy. Recovery and memory limits matter for these large pipelines.
- FLUX.2 klein permits **zero through four** references. Kontext requires one; Schnell accepts none. Prefer the registry as the capability source.
- The CLI ratio table, inference ratio defaults, Rust startup dimensions, and frontend resolution ladder are not currently identical concepts. Decide precedence explicitly instead of copying whichever table is nearest.

## Confirmed findings and implementation tasks

### R01 — Preserve acceptance state on save failure

**Status:** PLANNED. **Sign-off:** —

Anchors: `textbrush/ipc/handler.py:513` (`handle_accept`, especially 573–581), `textbrush/backend.py:1440` (`accept_all`).

The handler clears `_image_index_map`, `_deleted_indices`, `_delivery_order`, and `_delivered_images` before `accept_all` succeeds. The backend moves images sequentially, so a later failure can leave both already-saved files and unsaved previews, with no usable session ownership or reported partial results.

Reproduction: use a handler with a mock backend, register an image through `_assign_image_index`, make `accept_all` raise `OSError('disk full')`, then accept twice. The map is empty after the first error; the second response is `No images to accept`. This is loss of retry/recovery state, not proof that all preview files were physically deleted.

Implement explicit acceptance ownership and commit/recovery semantics. Preserve failed items; track completed moves so retry neither duplicates them nor tries to move nonexistent previews. Coordinate with R10 and R25.

Acceptance: first-save failure retains all selections; failure on the second of several images preserves/reportable partial completion; retry completes once per image; successful paths stay chronological; concurrent delivery cannot corrupt the accepted batch.

### R02 — Report worker errors independently of image delivery

**Status:** DONE. **Sign-off:** See verification below.

DONE — 2026-09-26 — Codex — `bf9eb15` — Inference exceptions terminate the current run, preserve the original error, and close the buffer immediately to wake delivery even before the first image. Delivery checks the error before interpreting an empty read. Both CLI branches check worker errors without an arbitrary inference deadline. Explicit worker restart clears the previous error. `uv run pytest tests/test_generation_failures.py tests/test_worker.py tests/test_worker_quiescence.py tests/test_image_delivery_update.py tests/test_cli.py -m 'not slow and not integration' -q`: 160 passed before adding the slow-success test. Latest `uv run pytest tests/test_cli_headless.py tests/test_generation_failures.py -q`: 54 passed, including the virtual 180-second successful-generation case, real worker-to-delivery error signalling, and both CLI branches. Ruff lint/format and `git diff --check` passed. The broad fast run reported 1,212 passed and 11 failures in headless mocks that did not configure check_worker_error; those mocks and obsolete timeout-contract tests were corrected, and their entire file passes in the latest 54-test run. The final project-wide gate still needs a fresh broad run after the remaining tasks.

Anchors: `textbrush/ipc/handler.py:1244` (`deliver_loop`), `textbrush/worker.py:530`, CLI wait loops in `textbrush/cli.py`.

Delivery calls `get_next_image(timeout=None)` before checking `check_worker_error`. If inference fails without producing an image, delivery never reaches the check. A `None` result also exits before the check. The worker catches errors and immediately retries without backoff or a terminal transition. CLI loops poll only the buffer and eventually replace useful inference errors with a timeout.

Reproduction: a mock backend's image read blocks on an event and its error accessor already returns an exception. Error-accessor call count remains zero while blocked and after the read returns `None`.

Provide an independent failure signal or bounded polling that checks worker state. Define terminal versus retryable failures; avoid tight repeated failure loops. Keep successful slow inference supported.

Acceptance: failure before the first image promptly reaches the UI and CLI with the original useful message; no infinite busy retry; shutdown unblocks consumers; a recovered generation does not accidentally consume an obsolete fatal error.

### R03 — Make a base wheel installation importable

**Status:** IN_PROGRESS. **Sign-off:** Pending remaining validation.

Implementation: `0b5563a` moves Pillow into base dependencies, declares packaging, delays backend import until generation, adds an actionable missing-model-extra error, and corrects README installation commands. `uv build --wheel --out-dir /tmp/textbrush-handover-wheel` succeeded. From `/tmp`, `uv run --isolated --no-project --with /tmp/textbrush-handover-wheel/textbrush-0.1.0-py3-none-any.whl python` verified installed CLI help (exit 0), invalid download parsing (exit 2), version 0.1.0, mocked update dispatch, and the missing-extra diagnostic without torch installed. The wheel imported from site-packages, outside the checkout. Remaining: model-enabled installation/runtime validation; no real-model test was run.

Anchors: `pyproject.toml:9`, `textbrush/cli.py:16`, `textbrush/references/normalization.py:34`, `textbrush/buffer.py`.

Pillow is only in the `model` extra, but importing the CLI imports reference normalization and Pillow unconditionally. `main` also imports the backend before argument dispatch. The README/release instructions recommend base `pip install textbrush`.

Reproduction: build a wheel and run its `textbrush.cli.main(['--help'])` in an isolated environment containing only wheel-declared base dependencies, outside the checkout. It fails with `ModuleNotFoundError: No module named 'PIL'`.

Either make required imports base dependencies or make optional inference imports truly lazy. Clarify which commands need the model extra and provide a useful missing-extra error for generation. Do not make `--help`, update checking, or weight download require full inference dependencies unnecessarily.

Acceptance: help, version/update entry path, and download argument parsing work from a clean base wheel installation; generation without required extras fails clearly; model-enabled installation remains usable.

### R04 — Install frontend dependencies in release CI

**Status:** PLANNED. **Sign-off:** —

Anchors: `.github/workflows/release.yml:47`, `src-tauri/tauri.conf.json` build hooks, `src-tauri/ui/package.json`.

The release workflow runs `uv sync` and `cargo tauri build` without installing npm dependencies. The Tauri before-build hook runs `npm run build`, which requires local esbuild. The clean-checkout dependency path is missing; the remote workflow itself was not executed during review.

Install a supported Node runtime and locked UI dependencies before the build. Reuse a coherent build path across local packaging and CI. Audit CI's direct `cargo build` path separately: it embeds the tracked bundle without necessarily rebuilding current TypeScript.

Acceptance: clean-checkout frontend and release builds succeed with no pre-existing `node_modules`; built assets reflect current sources; required macOS/Linux artifacts actually exist before upload. See R22/R26.

### R05 — Bundle a portable Python runtime

**Status:** PLANNED. **Sign-off:** —

Anchors: `Makefile:179` (`bundle-python-env`, `package`), `src-tauri/src/commands.rs` (`bundled_python_from_exe`, `resolve_release_python_command`).

The Makefile copies `.venv` with `cp -R`. The inspected `.venv/bin/python` points to `/Users/mrother/.local/share/uv/python/cpython-3.13.11-macos-aarch64-none/bin/python3.13`, and `pyvenv.cfg` references the same external installation. Copying it does not make the interpreter portable. Release CI currently follows a different packaging path, which does not use this bundling target.

Choose and document a distribution contract: a genuinely bundled runtime with model dependencies, or an explicitly required external runtime with reliable diagnostics. If bundling, verify resource destination layout against Rust's lookup path as well as interpreter/library relocation. Copying only an executable may still miss its standard library or dynamic libraries.

Acceptance: launch an installed app outside the repository, without the build user's interpreter path or virtual environment, and demonstrate sidecar import/startup. Test paths containing spaces. Record clean-machine evidence; a source-tree launch is insufficient.

### R06 — Resolve the CLI/desktop workflow mismatch

**Status:** PLANNED. **Sign-off:** —

Anchor: `textbrush/cli.py:605` and README's desktop workflow examples.

The non-headless Python CLI branch directly initializes the backend, generates, saves the first image, and exits. It does not launch Tauri. Documentation promises an interactive review window. Its fixed 30-second wait also rejects legitimate slower generation; headless uses 120 seconds.

Recommended direction: implement the documented desktop dispatch and retain explicitly headless generation separately. If product intent has changed, record that decision and update all human-facing usage examples instead. Define process exit/stdout forwarding and avoid loading the model twice. Integrate R07/R10/R14/R15.

Acceptance: invoke the actual installed CLI entry point with and without `--headless`; verify intended window behavior, forwarded options, accepted-path stdout, abort exit code, and slow-generation behavior using controlled fixtures. Do not validate solely by calling the backend directly.

### R07 — Forward desktop model/reference launch arguments

**Status:** PLANNED. **Sign-off:** —

Anchors: `src-tauri/src/launch_args.rs` (`LaunchArgs`, `parse_launch_args`, fallback at 156), `src-tauri/ui/main.ts:246`.

Rust's launch structure/parser lacks `model_id`, `references`, and `preset`, while TypeScript reads them. `--model`, repeated `--reference`, and `--preset` therefore fall through the unknown-argument branch. `--buffer-max` is parsed but should also be traced through initialization before promising it works. Other Python CLI options are not automatically supported by the native executable.

Define the native launch contract and serialize all supported values through Rust → TypeScript → IPC. Preserve ordered duplicate references. Reject unsupported arguments rather than silently skipping them, accounting for any platform-supplied launch arguments that must be tolerated.

Acceptance: parser tests assert exact returned values; bridge tests assert the actual INIT payload; explicit model choice bypasses deferred selection; reference order/duplicates survive; missing/invalid option values produce useful errors.

### R08 — Make configuration changes and publication atomic

**Status:** PLANNED. **Sign-off:** —

Anchors: `textbrush/worker.py:240` (`update_config`), `_run` around 478–528; `textbrush/backend.py:1179` (`update_config`).

The worker's epoch check precedes construction and `buffer.put`. An update may bump the epoch and clear the buffer after the check but before insertion, allowing a stale result into the new buffer. Multiple worker snapshot fields are also read/written separately; seed advancement modifies current options after generation.

Reproduction: intercept the worker's `buffer.put` in a unit-level fixture, perform `worker.update_config('new prompt', ...)` and `buffer.clear`, then permit the original put. The resulting buffer holds an image attributed to `old prompt` after the update.

Use an immutable configuration snapshot and a coordinated publication/update protocol. A second unsynchronized epoch check alone does not eliminate the race. Avoid deadlocking updates against a full buffer.

Acceptance: deterministic barriers cover updates during inference, after epoch validation, and while insertion is blocked. No superseded result is delivered after the update boundary, metadata matches actual inference inputs, and old seed advancement cannot overwrite a newer configuration's seed.

### R09 — Encode actual JPEG output

**Status:** PLANNED. **Sign-off:** —

Anchors: `textbrush/backend.py:1350` (`save_to_preview`), `accept_from_preview` around 1423–1435.

Previews are always PNG. Acceptance renames/copies preview bytes to a filename using the configured extension without transcoding. Reproduction with `config.output.format='jpg'` produced a `.jpg` path for which `Image.open(path).format == 'PNG'`.

Convert when the requested output format differs from the preview format; retain an efficient move for identical formats. Decide JPEG metadata behavior explicitly; EXIF support is currently documented as future work and must not be claimed merely because the extension is correct.

Acceptance: inspect encoded format and dimensions, not just suffix; PNG metadata stays intact; JPEG modes are supported; failed conversion preserves the source preview and session recovery. Preserve reference-provenance privacy.

### R10 — Honor output destinations

**Status:** PLANNED. **Sign-off:** —

Anchors: `textbrush/ipc/handler.py` (`_start_image_delivery(output_path)`, `handle_accept`), `textbrush/backend.py:1474` (`accept_all`).

Desktop `output_path` reaches delivery but is unused by acceptance. Separately, `accept_all(output_dir=...)` creates the requested directory and then calls `accept_from_preview(..., output_path=None)`, which chooses the configured directory. The explicit-directory failure was reproduced.

Define multi-image semantics for a single `--out` filename: explicit naming/suffix policy or a clear rejection, not silent disregard or repeated overwrite. Pass the resolved destination to each save operation.

Acceptance: explicit directory and single-file overrides, default directory, multiple images, existing destination collisions, paths with spaces, and partial failures all behave as documented. Returned paths identify the files actually written.

### R11 — Release deleted-image memory

**Status:** PLANNED. **Sign-off:** —

Anchors: `textbrush/ipc/handler.py:1168` (`handle_delete`, `_image_index_map`), `textbrush/buffer.py` (`BufferedImage.cleanup`).

Deletion keeps the full `BufferedImage` in the index map and only unlinks its preview. The decoded PIL image remains strongly referenced. Repeated generation/deletion accumulates pixel memory despite visible deletion. Continuous delivery means the bounded buffer alone does not bound the session's image memory.

Replace deleted entries with lightweight tombstones or remove their image payload while preserving stable indexes and idempotent deletion. Consider retaining only preview/metadata records for older delivered images where feasible.

Acceptance: repeated delete cycles release image payloads; repeated delete still succeeds; deleted items stay absent from recovery lists and acceptance; retained images remain navigable. Use object-lifetime evidence or bounded memory tests, not only assertions that files disappeared.

### R12 — Surface unexpected sidecar exit

**Status:** PLANNED. **Sign-off:** —

Anchor: `src-tauri/src/sidecar.rs:162` (`start_reader`), `commands.rs` initialization.

EOF/read failures silently end the reader. Spawning Python can succeed even when Python immediately fails to import `textbrush`; the spawn error mapping for “No module” cannot catch that child stderr failure. The UI receives no terminal error and may stay waiting.

Observe child termination, distinguish expected shutdown from crashes, and emit a useful terminal event. Reap child processes. Avoid exposing secrets if collecting stderr. Coordinate R19 so an intentional abort is not reported as a crash.

Acceptance: fake sidecars that exit immediately, produce malformed output then exit, or close stdout unexpectedly generate deterministic UI errors; normal accept/abort produces no spurious fatal event; no unreaped child remains.

### R13 — Read installed distribution version

**Status:** DONE. **Sign-off:** See verification below.

DONE — 2026-09-26 — Codex — `0b5563a` — Isolated installed wheel returned 0.1.0 outside the checkout. `uv run pytest tests/test_updates.py -q`: 44 passed, covering newer/equal/older releases and missing local metadata without a remote request or misleading API error. Version now comes from importlib.metadata.

Anchor: `textbrush/updates.py:42` (`get_current_version`).

Version detection reads `Path(__file__).parent.parent / 'pyproject.toml'`. The built wheel contains no such site-packages file. Isolated execution reproduced `FileNotFoundError`. The update path subsequently compares `unknown` as a version and reports an API error even if the release response is valid.

Use installed distribution metadata, with a deliberate source-development fallback only if needed. Review update error classification while touching this path. No live GitHub API request is needed for the regression test.

Acceptance: version detection works from a wheel outside the checkout; mocked newer/equal/older release responses are classified correctly; missing local version metadata is not misreported as a remote API failure.

### R14 — Preserve seed zero

**Status:** PLANNED. **Sign-off:** —

Anchor: `src-tauri/ui/main.ts:249`.

`seed: launchArgs.seed || null` converts valid seed zero to the random-seed sentinel. Use nullish handling. Trace other seed truthiness checks before concluding the whole contract is fixed.

Acceptance: actual frontend INIT calls preserve `0`, a positive seed, and the absent-seed sentinel distinctly; backend receives the supplied integer unchanged. Do not require real inference just to test serialization.

### R15 — CLI aspect ratio for reference-capable models

**Status:** PLANNED. **Sign-off:** —

Existing backlog slug: `cli-aspect-ratio-ignored-for-reference-capable-models`.
Anchors: `textbrush/cli.py` generation call sites; `textbrush/backend.py:776` preset fallback; `tests/test_cli.py::test_cli_accepts_any_aspect_ratio_for_editing`.

The CLI sends a ratio without explicit dimensions. For an editing-capable model, the backend substitutes its editing preset dimensions first. Thus a FLUX.2 `--aspect-ratio 16:9` request still gets the default 768×576 canvas. README/config/reference documentation claims the ratio works for every model.

Choose coherent precedence for explicit preset, explicit ratio, and defaults. When implementing ratio dimensions, send the same canvas to configuration acknowledgement and generation, so reference normalization and inference agree. The frontend ladder's first rung and inference's text-only ratio defaults differ; do not introduce an undocumented model-dependent size policy accidentally.

Acceptance: drive the real CLI orchestration with mocked inference for both dispatch branches; cover editing with and without references, explicit preset/ratio conflict, and defaults; assert generated options and normalized-reference canvas, not merely `validate_selection`'s result.

### R16 — Generated capability schemas

**Status:** PLANNED. **Sign-off:** —

Existing backlog slug: `tauri-generated-schemas-tracked-on-two-platform-tree`.
Anchor: `src-tauri/gen/schemas/`, `.gitignore`.

Platform builds rewrite tracked generated schemas, producing persistent cross-platform churn. The exact dirty files are listed at the start of this document. Decide whether generated schemas should remain tracked; if not, ignore and untrack them in an explicit housekeeping change. Preserve pre-existing content until that decision is implemented. Verify no packaging/test consumer depends on checked-in files.

Acceptance: agreed policy documented; builds on both supported development platforms do not create unexplained tracked changes, or the retained tracking/update workflow is explicit. Do not fold unrelated dirty schemas into a functional fix.

### R17 — Correct the stale FLUX.2 test and remove environment dependence

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `0b5563a` — verification below.

Implementation: `0b5563a` corrects FLUX.2 to zero through four references and mocks availability explicitly. All 18 cardinality cases exercise CLI dispatch, with invalid combinations rejected before availability/backend construction and valid combinations forwarded to headless orchestration. `uv run pytest tests/test_cli.py tests/test_updates.py tests/test_weights.py tests/test_model_weights.py -m 'not slow and not integration' -q`: 263 passed (before adding the additional missing-version-metadata test). `uv run pytest tests --ignore=tests/test_buffer_stress.py -m 'not slow and not integration' -q`: 1,217 passed, 18 skipped, 42 deselected, 1 xfailed in 213.05 seconds. This broad run began before the R24 edit and added missing-extra/missing-metadata tests; those later changes have separate focused passing evidence, so the final all-task delivery gate still requires a fresh broad run.

Anchor: `tests/test_cli.py:646`, especially the `('flux2-klein-4b', 1, 4)` row at 653.

The fast suite failed `test_cli_model_reference_cardinality_before_backend[flux2-klein-4b-0-False]`. The registry/docs allow zero references. The test expects exit 1 but received exit 0. It patches the backend but leaves availability resolution dependent on the actual machine's installed weights, so a missing model can hide the stale assertion.

Update the intended cardinality contract and mock availability explicitly. Prefer deriving shared expectations from a deliberate contract table or registry while retaining independent assertions of the intended capability; do not make every test simply restate implementation logic.

Acceptance: zero-reference FLUX.2 succeeds in validation/orchestration; Kontext without a reference fails before model construction; identical results with no cache, complete cache, and unrelated local models. The complete fast suite passes.

### R18 — Replace vacuous contract tests

**Status:** PLANNED. **Sign-off:** —

Anchors: `src-tauri/src/exit_handlers.rs` tests; `src-tauri/ui/ipc-contracts.test.js`.

Several exit tests only assert local-vector properties or execute `let _ = ()`; they never call the production exit path. Some frontend IPC contract tests construct sample objects rather than exercise actual serialization/handlers. Large passing counts therefore overstate coverage of cross-language behavior.

Replace the critical cases with subprocess-level exit/stdout assertions or small extracted pure behavior tests used by production code. Add actual bridge payload checks for R07/R14. Do not change production semantics to accommodate mocks.

Acceptance: a deliberate change to exit code, path ordering, stdout content, or real INIT payload causes the relevant test to fail. Keep this scoped to meaningful behavior rather than mechanically rewriting all tests.

## Additional lower-priority findings and investigation candidates

These were not all in the original final review. Evidence and provisional priority are explicit; do not treat an unexecuted concurrency/lifecycle concern as a proven user-facing failure.

### R19 — Abort and window-close lifecycle

**Status:** PLANNED. **Sign-off:** —

Anchors: `src-tauri/src/commands.rs::abort_generation`, `src-tauri/ui/main.ts::abort/handleAborted`, `src-tauri/src/main.rs` close handler, `textbrush/ipc/__main__.py` cleanup.

Rust sends ABORT and immediately kills the sidecar, while the frontend exits after receiving ABORTED. Killing first can prevent that acknowledgement and Python preview cleanup. Window close calls `std::process::exit(1)` directly. Python EOF cleanup shuts down the backend but does not run the handler's delivered-preview cleanup. `Sidecar::kill` also does not wait/reap.

Investigate with a fake sidecar that delays ABORTED and with temporary previews. Implement a bounded graceful shutdown followed by forced termination if needed; make UI exit independent of a response from a process already killed. Ensure delivery cannot register new previews after cleanup begins.

Acceptance: Abort always terminates the UI/backend within the documented bound; accept, abort, window close, and crash clean up their respective resources; no stray previews/processes; exit contracts remain correct. Coordinate R01/R12/R20/R25.

### R20 — Shutdown while inference is active

**Status:** IN_PROGRESS. **Sign-off:** Pending task audit.

Implementation committed with R02 in `bf9eb15`: Python abort/shutdown joins active inference without a deadline before clearing resources or unloading the engine. Worker stop immediately closes the buffer, and an inference result returned after stop is closed and discarded. README documents the unbounded Python cleanup contract. `tests/test_generation_failures.py::test_shutdown_never_unloads_engine_during_inference` holds a fake engine beyond the old five-second timeout, proves unload has not run, then releases it and checks the worker stopped, unload ran once, and no late result entered the buffer. All six tests in that file pass. Separate task acceptance audit/sign-off remains pending because the user requested stopping after the next completed task (R02). Desktop bounded termination and delivered-preview cleanup remain R19/R25 work.

Anchors: `textbrush/backend.py::abort/shutdown` (five-second join), `textbrush/inference/flux.py::unload`.

After a timed join, shutdown unloads the engine without establishing that the worker stopped. Real inference may take longer than five seconds. Reproduce with a blocking fake engine before attempting any expensive model test. Define ownership/cancellation so unload cannot race a live generation call. Also verify whether a late result can be published after abort.

Acceptance: a generation lasting beyond the join timeout cannot use a concurrently unloaded engine; shutdown has a clear bounded/unbounded contract, and no late preview survives abort.

### R21 — Event listener startup ordering

**Status:** PLANNED. **Sign-off:** —

Anchor: `src-tauri/ui/main.ts::setupMessageListener`, called immediately before `init_generation`.

`listen(...)` returns a promise, but initialization does not await subscription completion. A fast backend may emit initial catalogue/state events first. The initialized flag is set before subscription succeeds and is not reset on failure.

Reproduce with delayed listener registration and immediate backend events. Await subscription readiness, retain cleanup/unlisten ownership, and make failed initialization retryable without duplicate handlers.

Acceptance: initial model/state events are observed under adversarial ordering; listener failure is visible and recoverable; repeated initialization does not duplicate event handling.

### R22 — Regression tests must consume current frontend code

**Status:** DONE. **Sign-off:** See verification below.

DONE — 2026-09-26 — Codex — `0b5563a` — `npm test` now runs esbuild before TypeScript module compilation and all tests. `make ui-deps` detected the darwin-arm64 → linux-arm64 platform switch, removed stale node_modules and installed dependencies. `npm test`: 153 passed against the rebuilt bundle. `npm run check` passed. CI build-path changes remain tracked separately under R04.

Anchors: `src-tauri/ui/package.json` test/build scripts, `main-regressions.test.js` dynamic import of `bundle.js`, `tsconfig.json`.

`npm test` runs `tsc`, but main regression tests import `bundle.js`, which esbuild creates separately. TypeScript edits can pass tests against an old tracked bundle. The review's selected tests used the existing bundle; their pass does not independently prove it matches current TypeScript.

Build the bundle before tests that import it, or make tests load the actual compiled modules consistently. Apply the same current-source policy to CI packaging. Respect the Makefile's platform-sensitive npm dependency guard when sharing the tree between macOS and Linux.

Acceptance: modifying a main.ts behavior is reflected by the next test invocation without a manual build; fresh checkout and incremental runs behave identically.

### R23 — Buffer-full backpressure and dropped results

**Status:** PLANNED. **Sign-off:** —

Anchor: `textbrush/worker.py:520`.

`buffer.put(..., timeout=1.0)` returning false only ends generation if stop is also set. Otherwise the image is discarded, the seed advances, and another inference begins. The documented bounded-buffer behavior implies useful backpressure. Desktop continuous delivery may mask this; direct/backend consumers can fill the buffer.

Use a capacity-one buffer and controlled consumer to establish the intended behavior. Preserve pending output or explicitly document a deliberate dropping policy. Keep pause/config-change/shutdown responsive; do not simply introduce an indefinite put that prevents settling.

Acceptance: no unexplained loss or wasteful regeneration at capacity; seed progression matches the chosen contract; pause/stop/config updates remain deadlock-free.

### R24 — Return the snapshot that was actually validated

**Status:** DONE. **Sign-off:** See verification below.

DONE — 2026-09-26 — Codex — `0b5563a` — Cached downloads return AvailabilityReport.root. `uv run pytest tests/test_weights.py tests/test_model_weights.py -m 'not slow and not integration' -q`: 122 passed. Real temporary snapshot trees cover default and custom cache locations, complete aaa versus incomplete zzz snapshots, and no download/token requirement. Discovery validates the complete root before it is returned.

Anchor: `textbrush/model/weights.py:993` (`download_model_weights` cached path).

After availability succeeds, the function independently sorts snapshot directory names and returns the lexicographically last one, or the cache directory itself. A commit hash's lexicographic order does not identify the snapshot availability validated. Multiple/incomplete snapshots can produce a misleading success path.

Reuse `AvailabilityReport.root` or the resolved cache reference. Reproduce using temporary snapshots where the validated root sorts before an unrelated/incomplete root; no download is necessary.

Acceptance: cached-download success returns the validated model root for multi-snapshot/custom-cache layouts; it never returns an unrelated directory merely because it sorts last.

### R25 — Frontend acceptance errors and delivery races

**Status:** PLANNED. **Sign-off:** —

Anchors: `src-tauri/ui/main.ts::accept/handleErrorMessage`, `textbrush/ipc/handler.py::deliver_loop/handle_accept`.

Accept disables its button and re-enables it on invoke rejection, but backend ERROR is an asynchronous message after successful command dispatch. That path does not explicitly restore acceptance. Separately, delivery registers the image index before saving its preview, and acceptance snapshots the map without parking delivery. It may include an image whose preview is not ready; further deliveries can also arrive while saving/exiting.

Reproduce paused-session save failure and acceptance at a barrier between index assignment and preview save. Add explicit acceptance-in-flight state and coordinate publication/acceptance ownership with R01. Ensure an error notification is actually visible when the loading overlay is hidden.

Acceptance: failed acceptance leaves a usable retry UI; repeated keyboard activation does not send overlapping accepts; only fully published images are accepted; delivery during acceptance follows a documented policy.

### R26 — Platform-specific release validation

**Status:** PLANNED. **Sign-off:** —

Anchors: `.github/workflows/{ci,release}.yml`, `src-tauri/tauri.conf.json` (`bundle.targets = ['app', 'dmg']`), `Makefile::package`.

Linux appears in the release matrix while configured bundle targets and the local package recipe are macOS-specific. Verify the exact Tauri behavior for the installed CLI version instead of assuming it filters unsupported targets. CI also names a `macos-13` runner; check current runner availability at implementation time. This review did not browse provider documentation or execute remote CI, so runner retirement/platform failure is not asserted as confirmed.

Acceptance: each matrix row uses supported runners and platform-appropriate bundle targets; artifact paths/checksums match actual outputs; platform claims and prerequisites are tested, not inferred from a successful Rust compile.

### R27 — Asset access and content security policy

**Status:** PLANNED. **Sign-off:** —

Anchor: `src-tauri/tauri.conf.json::app.security`.

The CSP is null and asset scope broadly allows `**`, including dotfiles. This is a hardening concern, not an identified exploit: no concrete injection path was demonstrated. Assess required preview/reference access and trust boundaries before narrowing policy. Avoid reporting arbitrary local-file exposure as exploitable without evidence.

Acceptance: record a threat/requirements assessment; either justify current scope or constrain it while keeping previews and user-selected references usable. Validate denial of unrelated asset paths if restrictions are introduced.

### R28 — Documentation and contract maintenance

**Status:** PLANNED. **Sign-off:** —

Anchors: large CONTRACT/IMPLEMENTATION GUIDANCE blocks in backend, IPC, Rust main/exit handlers; README and docs.

Several comments describe obsolete behavior: delivery waiting for user action despite continuous delivery; output-path handling that does not occur; a “GUI” CLI branch that never starts a window; claims of atomic/thread-safe operations without synchronization. Historical review-round narratives make it difficult to identify the current invariant. Installation/package documentation also differs between local Makefile bundles and release CI.

After functional decisions, replace stale narratives with concise current invariants and meaningful rationale. Preserve important normalization/privacy/model-memory constraints. Ensure examples are executable and explicit about Python CLI versus native desktop flags. Check the ambiguous JPEG feature/TODO descriptions.

Acceptance: touched code comments describe actual control flow; documented commands match tested entry points; installation and output-format claims agree with implemented behavior. Avoid a broad stylistic rewrite unrelated to correctness.

### R29 — Recovery after a partially loaded model fails

**Status:** PLANNED. **Sign-off:** —

Anchors: `textbrush/backend.py::_swap_engine`, `textbrush/inference/flux.py::load`.

The swap exception path reloads the previous engine while `next_engine` is still held. `load` assigns `_pipeline` before device placement/offload, so a failure during those later operations may leave substantial candidate allocations alive during recovery. This was not reproduced against a real model.

Use a fake candidate that allocates/retains a resource then raises during load. Ensure candidate cleanup occurs before previous-engine recovery, while preserving original and recovery causes. Also audit rollback after reference-decode failure for consistent worker-engine ownership. Do not regress the unload-before-load memory constraint.

Acceptance: candidate resources are released before recovery begins; recoverable failure leaves a loaded usable previous model/worker; double failure reports fatal state accurately; no simultaneous full-model residency is required by design.

## Suggested implementation sequence

1. **Establish trustworthy verification:** R17 and R22; keep R18 scoped to the boundaries being fixed. This prevents false-green or environment-dependent results.
2. **Repair installation/release entry points:** R03, R04, R05, R12, R13; investigate R26 before promising cross-platform release readiness.
3. **Make the core session recoverable:** R01, R02, R08, R19, R20, R25, with deterministic thread/process barriers and fault injection.
4. **Unify user-facing contracts:** R06, R07, R10, R14, R15; agree precedence and multi-image output semantics before implementing overlapping pieces.
5. **Correct formats and resource retention:** R09, R11, R23, R24, R29.
6. **Finish maintenance and hardening:** R16, R18 remaining coverage, R21 if not already handled with startup, R27, R28.

Tasks are grouped for shared reasoning, not a requirement to make one large commit. Startup listener ordering (R21) can be addressed with R12. Acceptance/output tasks should share tests but remain individually signable. Candidate tasks may be rejected with evidence instead of implemented.

## Review verification baseline

These results describe the reviewed baseline, not the future fixed tree.

| Check | Result |
| --- | --- |
| Python fast suite | 1 failed, 1,216 passed, 18 skipped, 42 deselected, 1 xfailed; 226.35 seconds |
| Failure | `test_cli_model_reference_cardinality_before_backend[flux2-klein-4b-0-False]` (R17) |
| Selected frontend tests | 114 passed |
| Rust tests | 58 passed |
| Python ruff lint/format | Passed; 69 files already formatted |
| TypeScript/ESLint | Passed |
| Rust fmt/Clippy | Passed |
| Wheel build | Succeeded |
| Isolated base-wheel CLI help | Failed: missing PIL (R03) |
| Isolated installed version lookup | Failed: missing site-packages/pyproject.toml (R13) |
| Focused acceptance/output checks | Reproduced R01, R09, explicit-directory part of R10 |
| Controlled worker/delivery checks | Reproduced R02 and R08 |

Commands used from the repository root unless specified:

```sh
uv run pytest tests --ignore=tests/test_buffer_stress.py -m 'not slow and not integration' -q
uv run ruff check textbrush tests
uv run ruff format --check textbrush tests
```

From `src-tauri/ui`:

```sh
npm run check
npm run build:modules
node --test button-flash.test.js config_controls.test.js list-manager.test.js metadata-sync.test.js reference_picker.test.js theme-manager.test.js main-regressions.test.js ipc-contracts.test.js
```

From `src-tauri`:

```sh
cargo test --bin textbrush
cargo fmt --check
cargo clippy -- -D warnings
```

Wheel isolation pattern used (substitute a temporary directory and actual wheel filename; execute the isolated checks outside the checkout):

```sh
uv build --wheel --out-dir /private/tmp/textbrush-review-wheel
# Run the following from /private/tmp, not the source checkout:
uv run --isolated --no-project --with /private/tmp/textbrush-review-wheel/textbrush-0.1.0-py3-none-any.whl python -c 'import textbrush.cli; textbrush.cli.main(["--help"])'
uv run --isolated --no-project --with /private/tmp/textbrush-review-wheel/textbrush-0.1.0-py3-none-any.whl python -c 'from textbrush.updates import get_current_version; print(get_current_version())'
```

The wheel directory and generated `build/` from this review were removed afterward. Focused reproductions were inline temporary scripts, not committed regression tests; recreate them as meaningful tests when implementing the associated tasks. `uv run` refreshed the local virtual environment to CPython 3.13.11 with default development dependencies; the passing checks do not establish behavior with the full model extra. Do not rely on the review environment containing inference dependencies.

Not executed: real-model/GPU inference, model-heavy integration tests, the complete frontend test glob, accessibility browser tests, live release CI, clean-machine packaged-app execution, or a dependency vulnerability audit. No exploit or platform-runner retirement was verified. The frontend bundle caveat is R22. Rust test output included child-process BrokenPipe stderr although all 58 tests passed; investigate process lifecycle in R12/R19 rather than treating that output alone as proof of a production defect.

## Final delivery gate and context handoff checklist

- [ ] Every addressed task has a status, commit, and specific verification evidence; unresolved tasks remain visible.
- [x] R17's baseline failure is resolved for the correct product contract, independent of local weights.
- [ ] The fast Python suite, current-source frontend tests, Rust tests, and applicable lint/format checks pass after the final functional edits.
- [ ] Saved outputs have correct encoding, destination, metadata, and ordering; save failures retain a usable recovery path.
- [ ] Startup, configuration changes, worker failure, accept, abort, close, and child crash have deterministic behavioral tests.
- [ ] The installed wheel is tested outside the checkout with exactly its declared dependencies.
- [ ] Release readiness is withheld until the intended packaging contract is verified outside the build environment; remaining platform/model checks are stated explicitly.
- [ ] Existing unrelated schema changes are preserved or handled only under the explicit R16 decision.
- [ ] Temporary reproduction artifacts are removed; no credentials, reference-image contents, or machine-specific runtime paths are embedded in committed production configuration.
- [ ] README/docs and canonical backlog records are updated through their appropriate workflow, without claiming deferred verification is complete.

Next-context starting point: paused at the user's request after completing R02. On an explicit resume, re-read guidance and git status, audit/sign off the R20 implementation, then continue the remaining tasks (especially R08/R23 publication/backpressure and R01/R25 acceptance ownership). R13/R17/R22/R24 were completed in the previous increment. R03 still needs model-enabled validation. Source commits are `0b5563a` and `bf9eb15`; the final project-wide gate remains open. Original macOS/Linux schema changes remain untouched. Temporary wheel/build artifacts and test logs have been removed. The overall goal is not complete.
