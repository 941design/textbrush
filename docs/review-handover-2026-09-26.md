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
| R01 | P1 | Reproduced | Preserve acceptance state on save failure | DONE | `7472c1b`; see detailed evidence |
| R02 | P1 | Reproduced | Report worker errors without waiting for an image | DONE | `bf9eb15`; see detailed evidence |
| R03 | P1 | Reproduced | Make base wheel installation importable | DONE | `0b5563a`; installed model-extra evidence below |
| R04 | P1 | Code-confirmed | Install frontend dependencies in release CI | IN_PROGRESS | `6557895`; remaining platform/runtime validation below |
| R05 | P1 | Code-confirmed | Define a reliable packaged Python runtime | IN_PROGRESS | `b8b215e`; isolated installed Linux startup passed; clean-machine matrix remains |
| R06 | P2 | Code-confirmed | Resolve the CLI/desktop workflow mismatch | DONE | `4b7e3ee`; installed console/native evidence below |
| R07 | P2 | Reproduced | Forward desktop model/reference launch arguments | DONE | `8e7a908`; see detailed evidence |
| R08 | P2 | Reproduced | Make configuration changes and image publication atomic | DONE | `52036ba`; see detailed evidence |
| R09 | P2 | Reproduced | Encode actual JPEG output when requested | DONE | `7472c1b`; see detailed evidence |
| R10 | P2 | Mixed: reproduced/code | Honor output path and directory overrides | DONE | `7472c1b`; see detailed evidence |
| R11 | P2 | Code-confirmed | Release deleted-image pixel memory | DONE | `7472c1b`; see detailed evidence |
| R12 | P2 | Reproduced | Surface unexpected sidecar exit | DONE | `e3846cb`; see detailed evidence |
| R13 | P2 | Reproduced | Read installed distribution version correctly | DONE | `0b5563a`; see detailed evidence |
| R14 | P2 | Reproduced | Preserve desktop seed zero | DONE | `a4b4b18`; see detailed evidence |
| R15 | P2 | Code-confirmed; existing backlog | Honor CLI aspect ratio for reference-capable models | PLANNED | — |
| R16 | P3 | Code-confirmed; existing backlog | Resolve generated-schema tracking policy | PLANNED | — |
| R17 | P2 | Reproduced | Fix stale FLUX.2 test and isolate model availability | DONE | `0b5563a`; see detailed evidence |
| R18 | P3 | Reproduced | Replace vacuous contract tests with behavioral coverage | DONE | `7b01878`; see detailed evidence |
| R19 | P2 | Reproduced | Coordinate abort/close, process cleanup, and UI exit | DONE | `5154f6e`; see detailed evidence |
| R20 | P2 | Investigate | Settle worker before engine unload | DONE | `52036ba`; see detailed evidence |
| R21 | P2 | Reproduced | Await frontend event subscription before initialization | DONE | `feb1ae2`; see detailed evidence |
| R22 | P3 | Code-confirmed | Build current frontend bundle before regression tests | DONE | `0b5563a`; see detailed evidence |
| R23 | P2 | Investigate | Preserve backpressure and results when buffer is full | DONE | `52036ba`; see detailed evidence |
| R24 | P3 | Code-confirmed | Return the validated cached model snapshot | DONE | `0b5563a`; see detailed evidence |
| R25 | P2 | Investigate | Reconcile UI acceptance errors and in-flight delivery | DONE | `7472c1b`; see detailed evidence |
| R26 | P3 | Investigate | Check Linux packaging and release runner compatibility | IN_PROGRESS | `6557895`; remaining platform/runtime validation below |
| R27 | P3 | Investigate | Review asset-protocol scope and CSP deliberately | PLANNED | — |
| R28 | P3 | Code-confirmed | Remove stale implementation narratives and align docs | PLANNED | — |
| R29 | P2 | Investigate | Release partially loaded candidate before model recovery | DONE | `fd46404` |

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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `7472c1b` — verification below.

Acceptance keeps session indexes/selections until all outputs are committed. Each BufferedImage stores its planned destination and accepted-path checkpoint; failed batches report completed paths and retain previews for review/retry. Tests inject first-save and second-save disk failures, verify every selection survives, retry once per image, inspect chronological saved PNG seeds, and serialize delivery against the acceptance boundary. Verification: `uv run pytest tests/test_acceptance_recovery.py -q`: 16 passed. Acceptance/IPC/metadata/delivery/failure/publication group: 152 passed before the final repeated-deletion case; acceptance/cleanup/buffer group: 73 passed. The full fast Python command from the delivery gate passed 1,247 tests, with 18 skipped, 42 deselected and 1 xfailed; the final repeated-deletion test was added afterward and passed in the 16-test run. `npm test` rebuilt current sources and passed 156 tests; the final keyboard-path refinement then passed all 11 tests in `node --test src-tauri/ui/main-regressions.test.js`. `npm run check`, Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `0b5563a` — installed-wheel evidence below.

Implementation: `0b5563a` moves Pillow into base dependencies, declares packaging, delays backend import until generation, adds an actionable missing-model-extra error, and corrects README installation commands. `uv build --wheel --out-dir /tmp/textbrush-handover-wheel` succeeded. From `/tmp`, `uv run --isolated --no-project --with /tmp/textbrush-handover-wheel/textbrush-0.1.0-py3-none-any.whl python` verified installed CLI help (exit 0), invalid download parsing (exit 2), version 0.1.0, mocked update dispatch, and the missing-extra diagnostic without torch installed. The wheel imported from site-packages, outside the checkout. Follow-up validation on 2026-09-26 built the current wheel and installed its declared base dependencies into a new system-Python-3.12 venv in a path containing spaces. The actual installed console script, run from /tmp, returned 0 for help, 2 for invalid download arguments, and 1 with the model-extra diagnostic for headless generation. Then `uv pip install --torch-backend cpu --python <venv>/bin/python <wheel>[model]` installed the declared extra. From /tmp with Python -I, imports resolved to site-packages; torch 2.14.0+cpu, diffusers 0.39.0 and transformers 4.57.6 imported successfully, as did FluxPipeline, FluxKontextPipeline and Flux2KleinPipeline. All three Textbrush engine constructors succeeded without weights. This closes the installation/import acceptance; it does not claim model loading or inference validation. The initial default torch install selected large CUDA dependencies and was explicitly terminated for disk pressure before the CPU install succeeded.

Anchors: `pyproject.toml:9`, `textbrush/cli.py:16`, `textbrush/references/normalization.py:34`, `textbrush/buffer.py`.

Pillow is only in the `model` extra, but importing the CLI imports reference normalization and Pillow unconditionally. `main` also imports the backend before argument dispatch. The README/release instructions recommend base `pip install textbrush`.

Reproduction: build a wheel and run its `textbrush.cli.main(['--help'])` in an isolated environment containing only wheel-declared base dependencies, outside the checkout. It fails with `ModuleNotFoundError: No module named 'PIL'`.

Either make required imports base dependencies or make optional inference imports truly lazy. Clarify which commands need the model extra and provide a useful missing-extra error for generation. Do not make `--help`, update checking, or weight download require full inference dependencies unnecessarily.

Acceptance: help, version/update entry path, and download argument parsing work from a clean base wheel installation; generation without required extras fails clearly; model-enabled installation remains usable.

### R04 — Install frontend dependencies in release CI

**Status:** IN_PROGRESS. **Sign-off:** Pending macOS/CI matrix validation.

`6557895` installs Node 22 and locked npm dependencies in release/native CI jobs, pins the npm Tauri CLI to 2.11.5, and uses `make package` in both local and CI packaging. Direct Rust CI builds first rebuild/stage the frontend. The Tauri hook now runs `npm run build` from its actual detected frontend directory; the previous extra `cd ui` was wrong. Runtime assets are staged separately from tests/dependencies. A temporary clean frontend tree with spaces in its path, no node_modules and no bundle passed npm ci, npm run check and all 148 npm tests, with exactly five staged runtime files. That test exposed URL.pathname handling in two esbuild test imports; fileURLToPath fixes both. `make package` began with npm ci and successfully built the native Linux ARM64 release Debian package in 3m07s. Six artifact-collector tests and Ruff lint/format passed. Workflow YAML parsed successfully. Remote CI, macOS packaging and the Linux x64 matrix row have not been run, so cross-platform release readiness is not signed off.


Anchors: `.github/workflows/release.yml:47`, `src-tauri/tauri.conf.json` build hooks, `src-tauri/ui/package.json`.

The release workflow runs `uv sync` and `cargo tauri build` without installing npm dependencies. The Tauri before-build hook runs `npm run build`, which requires local esbuild. The clean-checkout dependency path is missing; the remote workflow itself was not executed during review.

Install a supported Node runtime and locked UI dependencies before the build. Reuse a coherent build path across local packaging and CI. Audit CI's direct `cargo build` path separately: it embeds the tracked bundle without necessarily rebuilding current TypeScript.

Acceptance: clean-checkout frontend and release builds succeed with no pre-existing `node_modules`; built assets reflect current sources; required macOS/Linux artifacts actually exist before upload. See R22/R26.

### R05 — Bundle a portable Python runtime

**Status:** IN_PROGRESS. **Sign-off:** `6557895`, `b8b215e`; isolated installed Linux startup passed, clean-machine/platform evidence remains.

Distribution contract: require external Python 3.11+ with textbrush[model]. Local and CI builds use the same native/frontend packaging path. Packaged startup uses TEXTBRUSH_PYTHON literally when supplied, otherwise python3 on PATH; it no longer searches a copied venv or checkout. Python -I excludes working-directory, PYTHONPATH and user-site imports. Missing executables, missing imports and old Python produce actionable startup errors; a fatal startup message is not overwritten by a generic EOF error. Two process tests cover selection, paths with spaces, no fallback, missing imports, and unsupported versions.

`make package` produced a Linux ARM64 release .deb. A lightweight Xvfb/DBus native-window probe extracted that artifact into a temporary path containing spaces, gave it a fresh HOME, cwd outside the checkout, PATH=/usr/bin:/bin and a separate system-Python-3.12 venv with the installed wheel. It reached awaiting_model through the real frontend INIT/sidecar flow; /proc confirmed the selected external interpreter. Sending the real X11 WM_DELETE_WINDOW event returned exit 1 within eight seconds, left stdout empty, reaped the sidecar and removed its private preview directory. No weights or inference were involved. This probe exposed and verified the R19 follow-up below. Rust tests: 60 passed, one intentionally ignored child probe; fmt, Clippy and git diff --check passed.

This is isolated installed-artifact evidence on the build VM, not a separate clean OS. Clean-machine provisioning and macOS/Linux x64 execution remain unverified, so R05 remains IN_PROGRESS.

Anchors: `Makefile:179` (`bundle-python-env`, `package`), `src-tauri/src/commands.rs` (`bundled_python_from_exe`, `resolve_release_python_command`).

The Makefile copies `.venv` with `cp -R`. The inspected `.venv/bin/python` points to `/Users/mrother/.local/share/uv/python/cpython-3.13.11-macos-aarch64-none/bin/python3.13`, and `pyvenv.cfg` references the same external installation. Copying it does not make the interpreter portable. Release CI currently follows a different packaging path, which does not use this bundling target.

Choose and document a distribution contract: a genuinely bundled runtime with model dependencies, or an explicitly required external runtime with reliable diagnostics. If bundling, verify resource destination layout against Rust's lookup path as well as interpreter/library relocation. Copying only an executable may still miss its standard library or dynamic libraries.

Acceptance: launch an installed app outside the repository, without the build user's interpreter path or virtual environment, and demonstrate sidecar import/startup. Test paths containing spaces. Record clean-machine evidence; a source-tree launch is insufficient.

### R06 — Resolve the CLI/desktop workflow mismatch

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `4b7e3ee` — verification below.

Non-headless CLI now launches the native desktop and waits with inherited stdout/stderr and exit status. It discovers standard installed locations or textbrush-desktop on PATH; TEXTBRUSH_DESKTOP selects an explicit executable, with actionable missing-executable and recursive-Python-CLI diagnostics. It forwards prompt, output path, seed (including zero), ratio/preset, model, ordered references and configured buffer capacity. The sidecar loads the CLI's config file; explicit format/verbosity override its inherited environment. The CLI interpreter is selected unless TEXTBRUSH_PYTHON is already set. Desktop model resolution stays in the sidecar; the launcher neither discovers weights nor constructs a backend. Headless remains the generate-and-save path. Automatic accept/abort require headless; preset and ratio conflict explicitly. README documents installation/discovery and the two workflows.

`uv run pytest tests/test_desktop_dispatch.py tests/test_cli.py tests/test_cli_headless.py tests/test_generation_failures.py -m 'not slow and not integration' -q`: 160 passed. Nine desktop process tests cover literal arguments/paths with spaces, duplicate references, seed zero, config overrides, exact two-path stdout, abort and nonzero status propagation, missing/recursive executables and option conflicts. The virtual slow-success case still proves a 180-second generation is not rejected by an arbitrary deadline. Ruff lint/format and git diff --check passed.

Built the wheel with uv, installed its declared base dependencies into a fresh system-Python-3.12 venv in a path containing spaces, and invoked its actual console script from a temporary cwd outside the checkout. A controlled native fixture confirmed literal prompt/seed forwarding and exact accepted-path stdout. Headless bypassed that fixture and reported missing model dependencies; a separate controlled inference fixture then exercised the installed headless console with the real backend, producing a PNG and path (exit 0), and auto-abort (exit 1, empty stdout). Finally the same installed console launched the extracted real Linux ARM64 release .deb under Xvfb/DBus with a fresh HOME/restricted PATH. The native window reached awaiting_model through the real frontend/sidecar flow; X11 WM_DELETE_WINDOW propagated exit 1 and empty stdout to the console caller. No model weights or inference were run. macOS/Linux x64 platform evidence remains under R26.

The broad fast Python run reported 1,279 passed, 18 skipped, 42 deselected, one xfailed and two failures: an obsolete zero-argument load_config mock (updated) and a pre-existing gated-worker pause race. `6e61f03` requests pause before releasing inference in four affected test sequences, preventing an extra gated generation. The complete affected provenance/shutdown/desktop group then passed all 21 tests in 60.83 seconds. The final delivery gate still requires a fresh broad run after the remaining tasks. Marked integration tests were updated to request headless generation but were not executed. Temporary wheel, venv, probe scripts and logs were removed.

Anchor: `textbrush/cli.py:605` and README's desktop workflow examples.

The non-headless Python CLI branch directly initializes the backend, generates, saves the first image, and exits. It does not launch Tauri. Documentation promises an interactive review window. Its fixed 30-second wait also rejects legitimate slower generation; headless uses 120 seconds.

Recommended direction: implement the documented desktop dispatch and retain explicitly headless generation separately. If product intent has changed, record that decision and update all human-facing usage examples instead. Define process exit/stdout forwarding and avoid loading the model twice. Integrate R07/R10/R14/R15.

Acceptance: invoke the actual installed CLI entry point with and without `--headless`; verify intended window behavior, forwarded options, accepted-path stdout, abort exit code, and slow-generation behavior using controlled fixtures. Do not validate solely by calling the backend directly.

### R07 — Forward desktop model/reference launch arguments

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `8e7a908` — verification below.

Native parsing now forwards model, ordered duplicate references, preset and buffer capacity through LaunchArgs, the actual frontend invoke, Rust INIT serialization, and Python initialization. Named presets select their canonical dimensions; conflicting preset/ratio/dimensions are rejected, width/height must be paired, numeric values are validated, unsupported arguments fail explicitly, and Finder process-serial arguments are tolerated. Python applies buffer capacity before constructing the selected backend. Tests assert exact parser JSON, actual frontend invoke payload, production Rust IPC serialization, selected-backend startup and configuration arguments, and malformed option errors. `npm test`: 164 passed; `uv run pytest tests/test_ipc_handler.py -m 'not slow and not integration' -q`: 102 passed; `cargo test --bin textbrush`: 62 passed; TypeScript/ESLint, Ruff lint/format, Rust fmt/Clippy and `git diff --check` passed. Native options and sizing policy are documented in README. Real-model and packaged-app checks remain with R03/R05/R06/R26.


Anchors: `src-tauri/src/launch_args.rs` (`LaunchArgs`, `parse_launch_args`, fallback at 156), `src-tauri/ui/main.ts:246`.

Rust's launch structure/parser lacks `model_id`, `references`, and `preset`, while TypeScript reads them. `--model`, repeated `--reference`, and `--preset` therefore fall through the unknown-argument branch. `--buffer-max` is parsed but should also be traced through initialization before promising it works. Other Python CLI options are not automatically supported by the native executable.

Define the native launch contract and serialize all supported values through Rust → TypeScript → IPC. Preserve ordered duplicate references. Reject unsupported arguments rather than silently skipping them, accounting for any platform-supplied launch arguments that must be tolerated.

Acceptance: parser tests assert exact returned values; bridge tests assert the actual INIT payload; explicit model choice bypasses deferred selection; reference order/duplicates survive; missing/invalid option values produce useful errors.

### R08 — Make configuration changes and publication atomic

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `52036ba` — verification below.

An immutable input/configuration snapshot captures prompt, sampling, seed and provenance. Configuration replacement, clearing, nonblocking buffer insertion, and seed advancement share one lock. Backend no longer clears the buffer again after the atomic update. `tests/test_worker_publication.py` deterministically covers update during inference (including an obsolete error), update after epoch validation, active/paused full-buffer updates, detached caller/engine options, and publication before backend update returns. No stale seed overwrites the new configuration. Verification: `uv run pytest tests/test_worker_publication.py -q`: 9 passed; worker/quiescence/failure/backend group: 82 passed, 1 skipped (before the last two publication cases were added). Final `uv run pytest tests --ignore=tests/test_buffer_stress.py -m 'not slow and not integration' -q`: 1,232 passed, 18 skipped, 42 deselected, 1 xfailed in 193.45 seconds. Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

Anchors: `textbrush/worker.py:240` (`update_config`), `_run` around 478–528; `textbrush/backend.py:1179` (`update_config`).

The worker's epoch check precedes construction and `buffer.put`. An update may bump the epoch and clear the buffer after the check but before insertion, allowing a stale result into the new buffer. Multiple worker snapshot fields are also read/written separately; seed advancement modifies current options after generation.

Reproduction: intercept the worker's `buffer.put` in a unit-level fixture, perform `worker.update_config('new prompt', ...)` and `buffer.clear`, then permit the original put. The resulting buffer holds an image attributed to `old prompt` after the update.

Use an immutable configuration snapshot and a coordinated publication/update protocol. A second unsynchronized epoch check alone does not eliminate the race. Avoid deadlocking updates against a full buffer.

Acceptance: deterministic barriers cover updates during inference, after epoch validation, and while insertion is blocked. No superseded result is delivered after the update boundary, metadata matches actual inference inputs, and old seed advancement cannot overwrite a newer configuration's seed.

### R09 — Encode actual JPEG output

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `7472c1b` — verification below.

PNG output preserves preview bytes and text metadata without re-encoding. JPEG is encoded to a staging file before publication; RGB, RGBA, L and palette inputs are covered by actual Pillow format/dimension checks. JPEG writes no custom/EXIF metadata. Encoding failure and cross-filesystem copy failure preserve previews, remove partial output, and allow recovery. Reference provenance stays out of saved metadata. Verification: `uv run pytest tests/test_acceptance_recovery.py -q`: 16 passed. Acceptance/IPC/metadata/delivery/failure/publication group: 152 passed before the final repeated-deletion case; acceptance/cleanup/buffer group: 73 passed. The full fast Python command from the delivery gate passed 1,247 tests, with 18 skipped, 42 deselected and 1 xfailed; the final repeated-deletion test was added afterward and passed in the 16-test run. `npm test` rebuilt current sources and passed 156 tests; the final keyboard-path refinement then passed all 11 tests in `node --test src-tauri/ui/main-regressions.test.js`. `npm run check`, Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

Anchors: `textbrush/backend.py:1350` (`save_to_preview`), `accept_from_preview` around 1423–1435.

Previews are always PNG. Acceptance renames/copies preview bytes to a filename using the configured extension without transcoding. Reproduction with `config.output.format='jpg'` produced a `.jpg` path for which `Image.open(path).format == 'PNG'`.

Convert when the requested output format differs from the preview format; retain an efficient move for identical formats. Decide JPEG metadata behavior explicitly; EXIF support is currently documented as future work and must not be claimed merely because the extension is correct.

Acceptance: inspect encoded format and dimensions, not just suffix; PNG metadata stays intact; JPEG modes are supported; failed conversion preserves the source preview and session recovery. Preserve reference-provenance privacy.

### R10 — Honor output destinations

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `7472c1b` — verification below.

Acceptance now forwards the desktop output_path and honors explicit backend output_dir. The first file uses the requested filename; subsequent files receive -002, -003, etc. before its extension. The extension chooses encoding, existing destinations are rejected without overwrite, and per-image destination/checkpoint state survives partial failure. Tests inspect actual files for default/custom directories, filenames with spaces, multi-image suffixes, collisions, and the real handler-to-backend destination bridge. Verification: `uv run pytest tests/test_acceptance_recovery.py -q`: 16 passed. Acceptance/IPC/metadata/delivery/failure/publication group: 152 passed before the final repeated-deletion case; acceptance/cleanup/buffer group: 73 passed. The full fast Python command from the delivery gate passed 1,247 tests, with 18 skipped, 42 deselected and 1 xfailed; the final repeated-deletion test was added afterward and passed in the 16-test run. `npm test` rebuilt current sources and passed 156 tests; the final keyboard-path refinement then passed all 11 tests in `node --test src-tauri/ui/main-regressions.test.js`. `npm run check`, Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

Anchors: `textbrush/ipc/handler.py` (`_start_image_delivery(output_path)`, `handle_accept`), `textbrush/backend.py:1474` (`accept_all`).

Desktop `output_path` reaches delivery but is unused by acceptance. Separately, `accept_all(output_dir=...)` creates the requested directory and then calls `accept_from_preview(..., output_path=None)`, which chooses the configured directory. The explicit-directory failure was reproduced.

Define multi-image semantics for a single `--out` filename: explicit naming/suffix policy or a clear rejection, not silent disregard or repeated overwrite. Pass the resolved destination to each save operation.

Acceptance: explicit directory and single-file overrides, default directory, multiple images, existing destination collisions, paths with spaces, and partial failures all behave as documented. Returned paths identify the files actually written.

### R11 — Release deleted-image memory

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `7472c1b` — verification below.

BufferedImage.cleanup closes decoded pixels even if file deletion fails, leaving only lightweight metadata/tombstones in session indexes. Twenty repeated delete cycles verify closed pixel handles, stable indexes, idempotent deletion, and empty tombstone paths. Deleted images are excluded from acceptance. The existing wire protocol still carries flagged tombstones; frontend recovery filters them, and now also clears stale visible images when no active entries remain. Tests cover retained-image output and recovery with only tombstones. Verification: `uv run pytest tests/test_acceptance_recovery.py -q`: 16 passed. Acceptance/IPC/metadata/delivery/failure/publication group: 152 passed before the final repeated-deletion case; acceptance/cleanup/buffer group: 73 passed. The full fast Python command from the delivery gate passed 1,247 tests, with 18 skipped, 42 deselected and 1 xfailed; the final repeated-deletion test was added afterward and passed in the 16-test run. `npm test` rebuilt current sources and passed 156 tests; the final keyboard-path refinement then passed all 11 tests in `node --test src-tauri/ui/main-regressions.test.js`. `npm run check`, Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

Anchors: `textbrush/ipc/handler.py:1168` (`handle_delete`, `_image_index_map`), `textbrush/buffer.py` (`BufferedImage.cleanup`).

Deletion keeps the full `BufferedImage` in the index map and only unlinks its preview. The decoded PIL image remains strongly referenced. Repeated generation/deletion accumulates pixel memory despite visible deletion. Continuous delivery means the bounded buffer alone does not bound the session's image memory.

Replace deleted entries with lightweight tombstones or remove their image payload while preserving stable indexes and idempotent deletion. Consider retaining only preview/metadata records for older delivered images where feasible.

Acceptance: repeated delete cycles release image payloads; repeated delete still succeeds; deleted items stay absent from recovery lists and acceptance; retained images remain navigable. Use object-lifetime evidence or bounded memory tests, not only assertions that files disappeared.

### R12 — Surface unexpected sidecar exit

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `e3846cb` — verification below.

The stdout reader now reports unexpected EOF/read failure through a fatal `error` event with operation `sidecar_exit`, process status and runtime/stderr diagnostic guidance. Stderr remains inherited and is not copied into UI messages. The reader reaps exiting children; after 100 ms an EOF-producing child that is still alive is force-terminated and reaped because it can no longer serve IPC. Accepted/aborted messages and intentional termination suppress crash reports. Explicit kill is idempotent and reaps; dropping a Sidecar also terminates/reaps it. Fake Python processes cover immediate failure, malformed JSON followed by exit, closed stdout while still alive, invalid UTF-8, normal accepted/aborted exit, intentional kill and drop. Unix tests assert the child PID no longer exists after notification/completion. A real frontend event-subscription test verifies visible fatal output, disabled controls, blocked Enter acceptance and scheduled window close. `cargo test --bin textbrush`: 54 passed, 1 child probe ignored by the outer runner; `npm test`: 146 passed; `cargo fmt --check`, `cargo clippy -- -D warnings`, `npm run check` and `git diff --check` passed. No Python production code changed. R19 still owns graceful abort/close, cleanup of previews after crashes and frontend exit independence from ABORTED; R12 does not claim those are fixed.


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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `a4b4b18` — verification below.

Frontend INIT uses nullish seed handling. Four rebuilt-application tests inspect actual invoke arguments for zero, positive, null and omitted seeds; three Python handler tests execute the initialization callback and assert the seed passed to backend.start_generation. Rust transports Option<i64> directly through serde_json; backend GenerationOptions and FLUX inference use explicit None handling (worker callback `seed or 0` retains zero). `npm test`: 163 passed; `uv run pytest tests/test_ipc_handler.py -m 'not integration and not slow' -q`: 97 passed. `npm run check`, Ruff lint/format and `git diff --check` passed. No real-model tests were run.

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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `7b01878` — verification below.

Replaced twelve vacuous exit tests with a subprocess test invoking the actual production handlers for abort, empty acceptance, one path, and multiple paths with spaces, Unicode, duplicates and non-palindromic ordering. It asserts exact stdout/stderr and process exit codes. The ignored child probe is explicitly run by the parent test, not missing coverage. Replaced nineteen frontend object-only contract tests with actual rebuilt-app INIT calls for seed variants and complete native launch options, using a shared DOM/Tauri harness. Production Rust serialization is covered by R07. Deliberate mutations of success exit code, path ordering, stdout content and seed-zero serialization all failed the relevant tests; mutations were restored. An initial palindrome path fixture missed reversal and was corrected before sign-off. `npm test`: 145 passed; `cargo test --bin textbrush`: 51 passed, 1 child probe ignored by the outer runner; `npm run check`, Rust fmt/Clippy, Ruff lint/format and `git diff --check` passed. The full fast Python suite after R07 passed 1,262 tests, 18 skipped, 42 deselected and 1 xfailed in 200.05 seconds; R18 changes no Python. Test-count reductions reflect removal of vacuous tests. This is scoped boundary coverage, not a claim that every legacy test was audited.


Anchors: `src-tauri/src/exit_handlers.rs` tests; `src-tauri/ui/ipc-contracts.test.js`.

Several exit tests only assert local-vector properties or execute `let _ = ()`; they never call the production exit path. Some frontend IPC contract tests construct sample objects rather than exercise actual serialization/handlers. Large passing counts therefore overstate coverage of cross-language behavior.

Replace the critical cases with subprocess-level exit/stdout assertions or small extracted pure behavior tests used by production code. Add actual bridge payload checks for R07/R14. Do not change production semantics to accommodate mocks.

Acceptance: a deliberate change to exit code, path ordering, stdout content, or real INIT payload causes the relevant test to fail. Keep this scoped to meaningful behavior rather than mechanically rewriting all tests.

## Additional lower-priority findings and investigation candidates

These were not all in the original final review. Evidence and provisional priority are explicit; do not treat an unexecuted concurrency/lifecycle concern as a proven user-facing failure.

### R19 — Abort and window-close lifecycle

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `5154f6e` — verification below.

Native installed-app follow-up (`b8b215e`): the X11 window-close probe initially returned 0 despite `handle.exit(1)` (the local Tauri/wry RequestExit path discarded the requested status). Window close now invokes the same process-exit helper as explicit abort after shared shutdown. The rebuilt installed release passed the real native close check: exit 1, empty stdout, child reaped and private previews removed. Rust tests (60 passed, one ignored probe), fmt and Clippy passed after the fix.

Python handler shutdown closes publication, clears delivered-image ownership, cleans previews, waits for initialization/inference, then unloads once. IPC EOF now uses that same cleanup; loading cannot start generation after closure. Rust owns a private per-session preview directory passed to Python, removes it after termination/crash, and preserves accepted outputs outside that directory. Desktop accept, abort and window close share serialized cleanup with a five-second graceful ABORT deadline followed by kill/reap. Pipe writes run outside the app-state mutex and commands run off the window event thread, so blocked stdin cannot prevent shutdown. Unix children have a dedicated process group; independent leader monitoring kills residual launcher descendants holding stdout open. The frontend exits after abort command completion even without ABORTED and suppresses duplicate exit requests. README documents the five-second grace period plus 500 ms abort feedback delay.

Deterministic tests cover delayed graceful acknowledgement, forced termination with blocked stdin, app-state cleanup while a real command write is blocked, competing exits, crash preview deletion, launcher exit with inherited stdout, actual Python EOF, initialization/cleanup ordering, late delivery, acceptance preservation and frontend exit without acknowledgement or after invocation failure. Existing subprocess exit-contract tests still assert stdout order and status. `cargo test --bin textbrush`: 60 passed, 1 child probe ignored by the outer runner but invoked by its parent test; `npm test`: 148 passed; `uv run pytest tests --ignore=tests/test_buffer_stress.py -m 'not slow and not integration' -q`: 1,266 passed, 18 skipped, 42 deselected, 1 xfailed in 201.87 seconds. The final acceptance-preservation test was added afterward; all five tests in `uv run pytest tests/test_ipc_shutdown.py -q` passed. `npm run check`, Ruff lint/format, Rust fmt/Clippy and `git diff --check` passed. These are fake-process/model tests in the current Linux environment; no model-heavy inference or installed native-window/platform packaging validation was run. Packaging checks remain R03/R05/R26.


Anchors: `src-tauri/src/commands.rs::abort_generation`, `src-tauri/ui/main.ts::abort/handleAborted`, `src-tauri/src/main.rs` close handler, `textbrush/ipc/__main__.py` cleanup.

Rust sends ABORT and immediately kills the sidecar, while the frontend exits after receiving ABORTED. Killing first can prevent that acknowledgement and Python preview cleanup. Window close calls `std::process::exit(1)` directly. Python EOF cleanup shuts down the backend but does not run the handler's delivered-preview cleanup. `Sidecar::kill` also does not wait/reap.

Investigate with a fake sidecar that delays ABORTED and with temporary previews. Implement a bounded graceful shutdown followed by forced termination if needed; make UI exit independent of a response from a process already killed. Ensure delivery cannot register new previews after cleanup begins.

Acceptance: Abort always terminates the UI/backend within the documented bound; accept, abort, window close, and crash clean up their respective resources; no stray previews/processes; exit contracts remain correct. Coordinate R01/R12/R20/R25.

### R20 — Shutdown while inference is active

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `52036ba` — verification below.

Audited the implementation from `bf9eb15` against the revised worker. Backend abort joins without a deadline before engine unload; stop closes publication immediately. The blocking-engine regression exceeds five seconds, verifies unload has not run, releases inference, and verifies no late result is buffered and its pixels are closed. The Python unbounded-shutdown contract is documented. Desktop bounded process termination/delivered-preview cleanup remain separate R19/R25 work. Verification: `uv run pytest tests/test_worker_publication.py -q`: 9 passed; worker/quiescence/failure/backend group: 82 passed, 1 skipped (before the last two publication cases were added). Final `uv run pytest tests --ignore=tests/test_buffer_stress.py -m 'not slow and not integration' -q`: 1,232 passed, 18 skipped, 42 deselected, 1 xfailed in 193.45 seconds. Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

Anchors: `textbrush/backend.py::abort/shutdown` (five-second join), `textbrush/inference/flux.py::unload`.

After a timed join, shutdown unloads the engine without establishing that the worker stopped. Real inference may take longer than five seconds. Reproduce with a blocking fake engine before attempting any expensive model test. Define ownership/cancellation so unload cannot race a live generation call. Also verify whether a late result can be published after abort.

Acceptance: a generation lasting beyond the join timeout cannot use a concurrently unloaded engine; shutdown has a clear bounded/unbounded contract, and no late preview survives abort.

### R21 — Event listener startup ordering

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `feb1ae2` — verification below.

Startup awaits acknowledged event registration before invoking INIT. Subscription failure resets initialization and displays a Retry action; retry after an INIT rejection retains the existing listener. Page teardown owns unsubscription. Tests exercise the rebuilt application with delayed registration, immediate backend state emission, registration rejection, INIT rejection, concurrent/repeated initialization, and page teardown. `node --test main-regressions.test.js`: 14 passed; `npm test`: 159 passed; `npm run check` and `git diff --check`: passed. These are lightweight IPC/browser mocks, without real inference.

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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `52036ba` — verification below.

The worker retains one completed result at capacity and retries insertion without generating again or advancing its seed. Pause settles while retaining that result; resume publishes it first. Stop/update discard and close superseded pending output. Capacity-one tests hold the full buffer beyond the old one-second insertion timeout and assert exact image identity and seed progression, plus pause/update/stop without a consuming thread. README documents the queue-plus-one-pending policy. Verification: `uv run pytest tests/test_worker_publication.py -q`: 9 passed; worker/quiescence/failure/backend group: 82 passed, 1 skipped (before the last two publication cases were added). Final `uv run pytest tests --ignore=tests/test_buffer_stress.py -m 'not slow and not integration' -q`: 1,232 passed, 18 skipped, 42 deselected, 1 xfailed in 193.45 seconds. Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `7472c1b` — verification below.

The frontend tracks acceptance in flight across asynchronous backend responses. Repeated Enter presses cannot submit overlapping accepts; both invoke rejection and backend acceptance ERROR restore the button and show an error outside the hidden loading overlay. Backend publication saves previews before indexing and holds the same delivery lock as acceptance. Failure resumes delivery; success closes it and discards a late in-flight image. Deterministic barriers cover preview completion during accept, late delivery after success, repeated commands, and new delivery after a failed save. Verification: `uv run pytest tests/test_acceptance_recovery.py -q`: 16 passed. Acceptance/IPC/metadata/delivery/failure/publication group: 152 passed before the final repeated-deletion case; acceptance/cleanup/buffer group: 73 passed. The full fast Python command from the delivery gate passed 1,247 tests, with 18 skipped, 42 deselected and 1 xfailed; the final repeated-deletion test was added afterward and passed in the 16-test run. `npm test` rebuilt current sources and passed 156 tests; the final keyboard-path refinement then passed all 11 tests in `node --test src-tauri/ui/main-regressions.test.js`. `npm run check`, Ruff lint/format and `git diff --check` passed. No model-heavy tests were run.

Anchors: `src-tauri/ui/main.ts::accept/handleErrorMessage`, `textbrush/ipc/handler.py::deliver_loop/handle_accept`.

Accept disables its button and re-enables it on invoke rejection, but backend ERROR is an asynchronous message after successful command dispatch. That path does not explicitly restore acceptance. Separately, delivery registers the image index before saving its preview, and acceptance snapshots the map without parking delivery. It may include an image whose preview is not ready; further deliveries can also arrive while saving/exiting.

Reproduce paused-session save failure and acceptance at a barrier between index assignment and preview save. Add explicit acceptance-in-flight state and coordinate publication/acceptance ownership with R01. Ensure an error notification is actually visible when the loading overlay is hidden.

Acceptance: failed acceptance leaves a usable retry UI; repeated keyboard activation does not send overlapping accepts; only fully published images are accepted; delivery during acceptance follows a documented policy.

### R26 — Platform-specific release validation

**Status:** IN_PROGRESS. **Sign-off:** Pending macOS and Linux x64 execution.

`6557895` selects macos-15 (ARM64), macos-15-intel (x64), and ubuntu-24.04 (x64); macos-13 retirement and replacement labels were checked against [GitHub's runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) and [retirement notice](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/). Linux prerequisites follow [Tauri's official prerequisites](https://v2.tauri.app/start/prerequisites/). Node 22 remains supported according to the [Node release schedule](https://github.com/nodejs/Release/blob/main/README.md). Tauri 2.11.5's local build help lists Linux deb/rpm/appimage targets; `tauri bundle --ci --config '{"bundle":{"targets":["app","dmg"]}}'` on Linux returned zero with no output, rather than producing a Linux installer. Configuration now selects deb by default and app/dmg through the macOS override.

Both debug and release Linux ARM64 Debian bundles were produced locally. The artifact helper collected the real release tar/deb, sha256sum verified both, and dpkg-deb reported textbrush 0.1.0 arm64 with GTK/WebKit dependencies. Extraction confirmed an executable and no node_modules. The helper requires a nonempty executable and exactly one platform installer before emitting uploads; six tests cover archive layout/checksums and missing/empty/ambiguous artifacts. Upload steps fail on missing files. macOS DMG/app generation, Linux x64 packaging, remote runner execution and clean-machine runtime prerequisites remain unverified; do not infer these from the local ARM64 result.


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

**Status:** DONE. **Sign-off:** DONE — 2026-09-26 — Codex — `fd46404` — verification below.

Failed candidates are unloaded before recovery, and inactive exception-frame locals are cleared so they cannot retain candidate allocations. Release failures stop recovery with a fatal error; original load and recovery causes remain available. Reference-decoding rollback updates the paused worker to the restored engine, and failed restoration is fatal even when the candidate can be reloaded. Six deterministic cases cover partial allocation lifetime, successful and failed recovery, candidate/previous unload failures, and reference rollback with worker generation. Verification: `uv run pytest tests/test_model_recovery.py tests/test_backend.py tests/test_worker_publication.py tests/test_generation_failures.py tests/test_acceptance_recovery.py -m 'not slow and not integration' -q`: 71 passed, 1 skipped. Ruff lint/format and `git diff --check` passed. Real-model/GPU validation was not run.

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

Next-context starting point: R06 is DONE in `4b7e3ee`: Python CLI now launches the native desktop by default, headless owns Python generation. Installed-wheel console probes demonstrated native window startup/close and controlled headless generation outside the checkout; details above. `6e61f03` removes a pause/release race in four provenance-test sequences. Focused CLI group: 160 passed; provenance/shutdown/desktop follow-up: 21 passed. Broad fast run had 1,279 passed and two failures, both corrected and covered in the follow-up; repeat the broad gate after remaining functional changes. No processes remain running. Next tasks are R15 (CLI canvas precedence), R16 (schema policy/backlog), R27 (asset/CSP assessment), and R28 (stale docs). R03 is DONE; R04/R05/R26 retain honest clean-machine and macOS/Linux x64 validation gaps. The latest installed Linux .deb still contains `b8b215e` native code (unchanged by R06), and normal native build outputs remain. New Python code requires rebuilding the wheel for further installed checks. Existing macOS/Linux schema changes remain untouched. Temporary validation files were removed. No model-heavy tests or remote release publication were run. The overall goal remains active.
