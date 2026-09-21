# Reference Editing

Textbrush can generate images from text alone (FLUX.1 [schnell]) or edit
local images using locally installed FLUX models that accept one or more
reference images as part of the prompt. This document covers reference
editing end to end: which model does what, what files are accepted, the
output presets, CLI examples, the desktop flow, storage and credentials,
how to write prompts, what is and is not persisted, and the limitations
of the first release.

The reference editing workflow is additive to the existing text-to-image
workflow: the existing FLUX.1 schnell path, its arguments, its exit
codes, and its PNG metadata are unchanged. Editing models are not
substituted for a text-only model automatically when the user has not
asked for them.

## Models and Capabilities

Three models are registered today. Each has a short slug (used on the CLI
and in config), a display name (used in messages and the UI), a mode, and
a fixed reference count band.

| Slug | Display name | Mode | References | Gated |
|---|---|---|---|---|
| `flux1-schnell` | FLUX.1 [schnell] | text-to-image | 0 | yes |
| `flux1-kontext-dev` | FLUX.1 Kontext [dev] | single-reference editing | exactly 1 | yes |
| `flux2-klein-4b` | FLUX.2 [klein] 4B | text-to-image and multi-reference editing | 0 to 4 | no |

References are **optional** wherever the lower bound of that band is
zero: FLUX.2 [klein] 4B generates from a prompt alone just as readily as
it edits one to four references, so "accepts references" and "requires
references" are different questions. Only FLUX.1 Kontext [dev] insists
on one.

The short slugs and the HuggingFace repo ids they map to are owned by
`textbrush.model.registry` (see `get_repo_id(slug)`); no other module
should hardcode either spelling. FLUX.2 [klein] 4B is the only model that
accepts more than one reference — when two or more references are
supplied, the resolver will surface a "FLUX.2 [klein] 4B is required"
message and refuse to launch.

## Supported Reference Formats

Reference files are local image files on disk. The decoder matches the
extension case-insensitively against this set:

- `.png`
- `.jpg`
- `.jpeg` (including `.JPG`)

Unsupported extensions are rejected with a message naming the file and
the supported set. Corrupt or truncated files are rejected with a
`corrupt reference image` message at acknowledgement time, not per
generation — the failure is reported once and the configuration is
unchanged.

Up to four references are accepted in a single request. Duplicates are
allowed: passing the same path twice counts as two references and is
forwarded to the pipeline twice. The order of references is preserved
end to end and is the only signal the prompt has to distinguish them.

Reference images are decoded once at acknowledgement and held in
memory for the lifetime of the acknowledged configuration. Deleting or
overwriting the source file on disk after acknowledgement does not
affect the in-flight or subsequent generations of that configuration.

## Output Size

There is **one** output-size vocabulary, and every model is offered all
of it. Each aspect ratio has a ladder of resolutions, smallest to
largest (owned by `textbrush.cli.SUPPORTED_RATIOS`):

| Ratio | Resolutions (width × height) |
|---|---|
| `4:1` | 1200 × 300, 1600 × 400 |
| `3:1` | 900 × 300, 1500 × 500, 1800 × 600 |
| `16:9` | 640 × 360, 1280 × 720, 1920 × 1080 |
| `4:3` | 512 × 384, 768 × 576, 1024 × 768 |
| `1:1` | 256 × 256, 512 × 512, 1024 × 1024 |
| `4:5` | 540 × 675, 1080 × 1350 |
| `3:4` | 384 × 512, 576 × 768, 768 × 1024 |
| `9:16` | 360 × 640, 1080 × 1920 |

The rows are ordered by height/width — widest first, tallest last — and
the desktop app lays the same order out in two columns, so the group
reads as one progression of shapes.

`--aspect-ratio` selects a ratio for any model; the desktop app shows
every ratio in one group with the pixel dimensions it currently
produces, and the `−`/`+` step moves the whole group up or down its
ladders together.

The six `--preset` identifiers are names for six of those sizes — the
4:3 and 3:4 ladders — and remain valid so existing config files and
scripts keep working:

| Identifier | Ratio | Dimensions (width × height) |
|---|---|---|
| `landscape-small` | 4:3 | 512 × 384 |
| `landscape-medium` | 4:3 | 768 × 576 |
| `landscape-large` | 4:3 | 1024 × 768 |
| `portrait-small` | 3:4 | 384 × 512 |
| `portrait-medium` | 3:4 | 576 × 768 |
| `portrait-large` | 3:4 | 768 × 1024 |

The default when a reference-capable model is active and no size has
been chosen explicitly is `landscape-medium` (configurable under
`[editing] default_preset`; see [Configuration Reference](configuration.md)).

A size with no preset name is not second-class: the desktop app sends
explicit pixel dimensions with every change, and the backend reports the
preset identifier only when one happens to name the acknowledged canvas.

## CLI Examples

The editing workflow is invoked through `--model`, repeatable
`--reference`, and `--preset`. Every command below is executable as
written against `uv run textbrush --help`; the model slugs and preset
identifiers are the canonical spellings.

**One reference with FLUX.1 Kontext [dev]:**

```bash
uv run textbrush --model flux1-kontext-dev --reference portrait.jpg \
  --preset portrait-medium --prompt "paint this person as a 1920s poster"
```

Kontext requires exactly one reference; supplying zero or two is
rejected before any model is loaded.

**Three references with FLUX.2 [klein] 4B:**

```bash
uv run textbrush --model flux2-klein-4b \
  --reference subject.png --reference palette.jpg --reference lighting.png \
  --preset landscape-large --prompt "render the subject in the palette and lighting"
```

FLUX.2 [klein] 4B accepts one to four references; the order in which
they appear on the command line is the order they reach the model.

**Validation error — two references on a single-reference model:**

```bash
uv run textbrush --model flux1-kontext-dev \
  --reference a.png --reference b.png --prompt "x"
```

Exits with code 1, empty stdout, and writes a cardinality message to
stderr that names the model and the rule:

```
Error: flux1-kontext-dev (FLUX.1 Kontext [dev]) requires exactly 1 reference image; got 2
```

**Any aspect ratio, with or without references:**

```bash
uv run textbrush --aspect-ratio 16:9 --model flux2-klein-4b \
  --reference a.png --prompt "x"

uv run textbrush --aspect-ratio 16:9 --model flux2-klein-4b \
  --prompt "x"
```

Both are accepted. Every ratio is valid for every model, and references
are optional for a model whose lower bound is zero.

**More than the maximum cardinality:**

```bash
uv run textbrush --model flux2-klein-4b \
  --reference a.png --reference b.png --reference c.png \
  --reference d.png --reference e.png --prompt "x"
```

Exits 1 with:

```
Error: flux2-klein-4b (FLUX.2 [klein] 4B) requires between 0 and 4 reference images; got 5; no supported model accepts more than 4
```

## Desktop Walkthrough

**Nothing is loaded until you pick a model.** Loading a model takes tens
of seconds — and a multi-gigabyte download if its weights are missing —
during which no other model can be chosen, so the app does not load one
speculatively. The window opens on a live model selector listing every
registered model with its reference capability and whether its weights
are installed; the viewer reads "select a model to begin". Picking one
starts the load, and generation begins paused as before. A model pinned
in the config (`[model] selected_id`) or passed on the command line is
already a choice and loads at launch. Picking a model whose weights are
absent reports that (non-fatally) and leaves the selection open.

The header carries three groups side by side: **Model** (one per line),
**Output size** (every ratio with its current pixel dimensions, plus the
`−`/`+` step), and **Reference images**. All three are shown for every
model — the reference control is greyed out, not hidden, for a model
that takes none, so the capability is visible rather than merely absent.

The reference picker uses the OS-native multi-file dialog (Finder on
macOS, the file chooser on Linux); it appends in order, accepts
duplicates, rejects unsupported extensions case-insensitively, and stops
at the selected model's maximum. Removing and replacing a reference is
available per item.

Model and reference changes are **never** applied while the worker is
generating. The selector and picker controls are disabled until the
generation loop comes to rest. To change the model or reference set:

1. Press **Space** (or click Pause) to pause the worker.
2. Wait for the settled indicator (the controls re-enable only once the
   in-flight generation has actually returned, not when the pause
   request is acknowledged — T7 in the implementation plan).
3. Choose a model, and pick reference files if you want any — for
   FLUX.2 [klein] 4B they are optional. Optionally pick a different
   output size.
4. Resume; the new configuration takes effect on the next generation.

If the chosen model and reference count are not compatible, the
configuration is still acknowledged (the model and the files you picked
are now the active set), but a compatibility message is rendered and
**resume is refused** until you fix the mismatch. The recommended model
— the one that would have made the selection compatible — is
pre-highlighted with a "recommended" badge; clicking it is your choice
and never happens automatically. Picking the recommended model does
not itself pick references; you still need to provide a count it
accepts.

The model is never swapped under the hood: if you ask for
`flux1-kontext-dev` and supply two references, you get a compatibility
error and the configuration you had before the edit remains active.

## Model Storage, Gated Licences, Credentials, Hardware

**Storage.** Weights are stored under the standard HuggingFace cache
(typically `~/.cache/huggingface/hub/`) and any additional directories
listed in `[model] directories` in `config.toml`. Textbrush does not
maintain a separate weights store.

**Gated licences.** FLUX.1 [schnell] and FLUX.1 Kontext [dev] are gated
repositories: a HuggingFace account with an accepted license and an
authenticated token is required. FLUX.2 [klein] 4B is ungated and can be
downloaded anonymously.

**Credentials.** The token can be supplied three ways (highest priority
last):

1. The standard HuggingFace environment variable `HUGGINGFACE_HUB_TOKEN`
   (or its short form `HF_TOKEN`) — read by both `--download-model` and
   the runtime when weights are missing.
2. `[huggingface] token` in `~/.config/textbrush/config.toml`.
3. `TEXTBRUSH_HUGGINGFACE_TOKEN` in the environment, which the
   configuration loader promotes into the `[huggingface] token` field.

The token grants read access to the configured HuggingFace account;
treat it as you would any other read-scope credential. Never commit it
to version control. See [Configuration Reference](configuration.md) for
the precedence rules.

**Downloading weights.** The `--download-model` flag downloads a
model's weights and exits. Given no value it fetches FLUX.1 [schnell]
(~23 GB); given a registry slug it fetches that model instead:

```bash
textbrush --download-model                     # FLUX.1 schnell (default)
textbrush --download-model flux1-kontext-dev   # gated: needs a token
textbrush --download-model flux2-klein-4b      # ungated: no token needed
```

`make download-model MODEL=<slug>` does the same through the build
system. FLUX.1 [schnell] and FLUX.1 [Kontext] dev are gated and require
a token plus an accepted license; FLUX.2 [klein] 4B is not gated and
downloads anonymously. Editing models are large; allow time and disk
space accordingly.

**Hardware.** FLUX.1 [schnell] needs roughly 12 GB of VRAM in
BFloat16 on CUDA, or about 16 GB of unified memory on Apple Silicon.
Editing models need substantially more VRAM than schnell — FLUX.2
[klein] 4B in particular runs comfortably only on a high-VRAM NVIDIA
GPU or a top-tier Apple Silicon configuration. CPU generation is
available as a fallback but is on the order of 10–30× slower than the
GPU paths and is not a realistic option for editing at production
quality.

**Memory.** Two models are never held in GPU memory at the same time.
Switching models unloads the previous model before loading the next; if
the new load fails, the previous model is reloaded and a recoverable
error is reported. See [GPU Setup Guide](gpu-setup.md) for hardware
details and [Troubleshooting](troubleshooting.md) for the failure modes
of `--download-model` and first-time model loads.

## Prompt Guidance

Textbrush does not assign roles, weights, or crops to individual
references. The prompt is the only signal that distinguishes them, and
the order in which references are supplied is the only positional
information the prompt can refer to. Prompt wording controls identity
and reference use: telling the model which image is the subject and
which is the style reference, in plain language, is the supported
mechanism for combining references.

Identity fidelity is not guaranteed. The model treats the reference as
guidance and may diverge from it; small visual features (a particular
hairstyle, an exact pose, a small object) may not survive a generation.
Treat the references as the strongest available signal, not as a
template that must be reproduced verbatim.

References are equal and untyped. There is no first/reference/second/
style distinction. If you want one reference to dominate, say so in the
prompt.

## Privacy

Reference editing is fully local: the reference images, the prompt, the
model weights, and the generated images never leave the host. No data
is uploaded to a server, and no remote calls are made outside the
HuggingFace Hub download path used to fetch weights.

Output images are saved with a closed, documented metadata key set:

- PNG: `AspectRatio`, `Width`, `Height`, `Prompt`, `Model`, `Seed`, and
  optionally `GeneratedWidth`, `GeneratedHeight`.
- JPEG: no custom metadata, no EXIF.

The key set is closed. No reference path, filename, basename, hash, or
raw bytes are written into the output file. The session-local
identifiers used internally to attribute each image to its snapshot are
never persisted to disk. The source files on disk are never read again
after acknowledgement; mutating or deleting a source file after
acknowledgement does not change the in-memory data and does not write
back to disk.

## Limitations and Roadmap

The first release supports the editing workflow described above and
nothing more. It deliberately does not support:

- **Face-aware cropping or selection.** References are not analysed for
  faces, nor cropped to the most informative region. The whole image is
  forwarded to the model.
- **Masks, inpainting, or regional control.** There is no way to specify
  "edit only this part of the image"; the whole frame is regenerated.
- **Per-reference roles or weights.** All references are equal and
  untyped; only the prompt can distinguish them.
- **Iterative editing.** A generated image cannot be fed back in as a
  reference without saving it to disk and re-acknowledging it.
- **Identity preservation guarantees.** Visual fidelity to a reference
  is a model property, not a Textbrush promise.

Face-aware selection is a known future direction and will likely arrive
as a per-reference role rather than automatic detection; until then,
selecting well-composed, on-subject references is the most effective
mitigation.
