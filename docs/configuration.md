# Configuration Reference

Complete guide to configuring textbrush via config files, environment variables, and CLI arguments.

## Configuration Priority

Textbrush merges configuration from multiple sources with the following priority (highest to lowest):

1. **CLI arguments** - `--prompt "text"`, `--seed 42`, etc.
2. **Environment variables** - `TEXTBRUSH_OUTPUT_FORMAT=jpg`
3. **Config file** - `~/.config/textbrush/config.toml`
4. **Defaults** - Built-in defaults

This allows flexible configuration: set project defaults in config file, override per-environment with env vars, and override per-invocation with CLI args.

## Config File Location

**Default path:** `~/.config/textbrush/config.toml` (XDG-compliant)

**Custom path:** `--config /path/to/config.toml`

The config file is created automatically on first run if it doesn't exist.

## Config File Format (TOML)

### Complete Example

```toml
# ~/.config/textbrush/config.toml

[output]
# Directory for generated images
# Supports ~ expansion and absolute paths
directory = "~/Pictures/textbrush"

# Default output format: png or jpg
format = "png"

[model]
# Additional directories to search for model weights
# Textbrush automatically checks HuggingFace cache first
directories = [
    "~/models/flux",
    "/mnt/storage/models"
]

# Size of image buffer (number of images to prefetch)
# Default: 8
# Higher = smoother UI experience but more memory
buffer_size = 8

# Pin a specific model by id (e.g. "flux1-schnell", "flux1-kontext-dev",
# "flux2-klein-4b"). Commented out and unset by default -- see the
# `selected_id` section details below for what "unset" means.
# selected_id = "flux1-schnell"

[huggingface]
# HuggingFace API token for model downloads
# Alternative: set HUGGINGFACE_HUB_TOKEN environment variable
# Leave empty to use environment variable
token = ""

[inference]
# Inference backend: flux (currently only supported backend)
backend = "flux"

[logging]
# Log verbosity: debug | info | warning | error
# Default: info
# Override with --verbose CLI flag (sets to debug)
verbosity = "info"

[editing]
# Fallback editing preset, applied only when an editing-capable model is
# active and no preset has been explicitly selected.
# Default: "landscape-medium"
default_preset = "landscape-medium"
```

### Section Details

#### `[output]`

**`directory`** (string)
- Where generated images are saved if `--out` not specified
- Supports `~` expansion and environment variables
- Default: `~/Pictures/textbrush`
- Example: `"~/Documents/generated-images"`

**`format`** (string)
- Default output format
- Choices: `"png"` or `"jpg"`
- Default: `"png"`
- Override: `--format jpg`

#### `[model]`

**`directories`** (array of strings)
- Additional paths to search for FLUX.1 model weights
- Checked after HuggingFace cache directories
- Supports `~` expansion
- Default: `[]` (empty)
- Example: `["/mnt/models", "~/ai/models"]`

**`buffer_size`** (integer)
- Number of images to generate ahead in background
- Higher values = smoother UI, more memory usage
- Range: 1-16 (practical maximum)
- Default: `8`
- Memory impact: ~2GB per image @ 1024x1024

**`selected_id`** (string, optional)
- Pins the active model by id, e.g. `"flux1-schnell"`, `"flux1-kontext-dev"`,
  `"flux2-klein-4b"`
- **Default: unset (absent from the file).** Unset does *not* mean "defaults
  to schnell" or any other concrete model — it means the model is resolved
  automatically from the number of active references at launch (spec.md
  §7.3): zero references resolves to a text-to-image model, one to four
  references resolves to an editing-capable model.
- Only set this key if you want to override that automatic resolution and
  always launch with one specific model regardless of the reference count.
- A freshly created config file never writes this key with a concrete
  value — at most a commented-out example is present, precisely so that
  running textbrush for the first time never silently pins a model you
  didn't choose.
- Override: `TEXTBRUSH_MODEL_SELECTED_ID` environment variable, or
  `--model <id>` on the CLI

#### `[huggingface]`

**`token`** (string)
- HuggingFace API token for downloading models
- Required for first-time model download
- Obtain from: https://huggingface.co/settings/tokens
- Alternative: `HUGGINGFACE_HUB_TOKEN` environment variable
- Default: `""` (uses environment variable)
- Security: Token has read access to public/private repos

#### `[inference]`

**`backend`** (string)
- Inference engine to use
- Currently only `"flux"` is supported
- Default: `"flux"`
- Future: May support additional models

#### `[logging]`

**`verbosity`** (string)
- Log level for textbrush output
- Choices: `"debug"`, `"info"`, `"warning"`, `"error"`
- Default: `"info"`
- Override: `--verbose` (sets to `debug`)
- Debug mode shows: model loading, hardware detection, IPC messages

#### `[editing]`

**`default_preset`** (string)
- Backend fallback output size when a reference-capable model is active
  and no canvas is supplied. Desktop and headless CLI launches always
  select a canvas (256×256 if neither size flag is supplied), so this
  setting does not override launch sizing.
- These six identifiers are names for six entries of the one output-size
  table — the `4:3` and `3:4` ladders — not a separate vocabulary.
- Choices (canonical identifiers, `<orientation>-<tier>`):
  `"landscape-small"`, `"landscape-medium"`, `"landscape-large"`,
  `"portrait-small"`, `"portrait-medium"`, `"portrait-large"`
- Default: `"landscape-medium"`
- Override: `TEXTBRUSH_EDITING_DEFAULT_PRESET` environment variable

## Environment Variables

All config file options can be overridden with environment variables.

**Naming convention:** `TEXTBRUSH_<SECTION>_<KEY>`

Examples:

```bash
# Output configuration
export TEXTBRUSH_OUTPUT_DIRECTORY="~/Desktop/images"
export TEXTBRUSH_OUTPUT_FORMAT="jpg"

# Model configuration
export TEXTBRUSH_MODEL_BUFFER_SIZE=12
export TEXTBRUSH_MODEL_DIRECTORIES="/models/flux"

# Pin a specific model, overriding automatic resolution from reference
# count (spec.md §7.3). Leave unset to let textbrush resolve the model
# from how many references are active.
export TEXTBRUSH_MODEL_SELECTED_ID="flux1-kontext-dev"

# HuggingFace token
export TEXTBRUSH_HUGGINGFACE_TOKEN="hf_xxxxxxxxxxxx"
# Or use standard HF env var
export HUGGINGFACE_HUB_TOKEN="hf_xxxxxxxxxxxx"

# Inference backend
export TEXTBRUSH_INFERENCE_BACKEND="flux"

# Logging
export TEXTBRUSH_LOGGING_VERBOSITY="debug"

# Editing: fallback preset used only when an editing-capable model is
# active and no preset has been explicitly selected
export TEXTBRUSH_EDITING_DEFAULT_PRESET="portrait-medium"

# Run with overrides
uv run textbrush --prompt "test"
```

## CLI Arguments

All options can be overridden on the command line (highest priority).

### Required

**`--prompt TEXT`**
- Text description for image generation
- Cannot be empty or whitespace-only
- Example: `--prompt "a watercolor cat"`

### Optional

**`--out PATH`**
- Output file path
- Overrides config `output.directory`
- Supports `~` expansion
- Example: `--out ~/Desktop/image.png`

**`--config PATH`**
- Path to custom config file
- Overrides default `~/.config/textbrush/config.toml`
- Example: `--config ./project-config.toml`

**`--seed INT`**
- Random seed for reproducibility
- Must be non-negative integer
- Same seed + prompt = identical image
- Example: `--seed 42`

**`--aspect-ratio CHOICE`**
- Image aspect ratio preset
- Choices, widest to tallest: `4:1`, `3:1`, `16:9`, `4:3`, `1:1`, `4:5`,
  `3:4`, `9:16`
- Valid for every model. `4:3` and `3:4` hold the same sizes the
  `landscape-*` and `portrait-*` presets name
- Each ratio has multiple available resolutions; desktop and headless CLI
  launches select the smallest. Cannot be combined with `--preset`.
- Default: `1:1` (defaults to 256×256, smallest 1:1 resolution)
- Example: `--aspect-ratio 16:9`
- Note: UI provides resolution selector (+/− buttons) to cycle through available sizes for each ratio

**`--format CHOICE`**
- Output format
- Choices: `png`, `jpg`
- Overrides config `output.format`
- Example: `--format jpg`

**`--verbose`**
- Enable debug logging
- Overrides config `logging.verbosity` to `debug`
- Shows model loading, device selection, IPC events

**`--headless`**
- Run without GUI
- For CI/CD and automated workflows
- Requires `--auto-accept` or `--auto-abort`

**`--auto-accept`**
- Auto-accept first image in headless mode
- Exits with code 0, prints path to stdout
- Example: `--headless --auto-accept`

**`--auto-abort`**
- Auto-abort immediately in headless mode
- Exits with code 1, empty stdout
- For testing error paths
- Example: `--headless --auto-abort`

## Configuration Examples

### Personal Use

```toml
# ~/.config/textbrush/config.toml
[output]
directory = "~/Pictures/AI-Art"
format = "png"

[logging]
verbosity = "info"

[model]
buffer_size = 8
```

### CI/CD Environment

```bash
#!/bin/bash
export TEXTBRUSH_OUTPUT_DIRECTORY="/tmp/test-images"
export TEXTBRUSH_LOGGING_VERBOSITY="error"
export HUGGINGFACE_HUB_TOKEN="${HF_TOKEN}"  # From secrets

uv run textbrush \
    --prompt "test image" \
    --headless \
    --auto-accept \
    --out /tmp/result.png \
    --seed 12345
```

### Project-Specific Config

```toml
# project-config.toml
[output]
directory = "./generated"
format = "jpg"

[model]
buffer_size = 4  # Lower for constrained environments

[logging]
verbosity = "warning"
```

```bash
uv run textbrush --config ./project-config.toml --prompt "diagram"
```

## Validation Rules

Textbrush validates all configuration:

- **Prompt**: Cannot be empty or whitespace-only
- **Seed**: Must be non-negative integer (0 or greater)
- **Format**: Must be `png` or `jpg`
- **Aspect ratio**: Must be `1:1`, `16:9`, or `9:16`
- **Buffer size**: Practical range 1-16 (no hard limit)
- **Paths**: Expanded and validated at runtime

Validation errors print helpful messages and exit with code 1.

## Debugging Configuration

To see effective configuration (after merging all sources):

```bash
uv run textbrush --prompt "test" --verbose
# Logs will show:
# - Config file path loaded
# - Environment variables detected
# - CLI argument overrides
# - Final merged configuration
```

## Security Considerations

**HuggingFace Token:**
- Never commit tokens to version control
- Use environment variables in shared environments
- Token grants read access to public + your private HF repos
- Consider creating a token with minimal scope

**Config File Permissions:**
- Config file is created with user-only permissions (0600)
- Contains sensitive data if token is stored
- Recommended: Use `HUGGINGFACE_HUB_TOKEN` env var instead

**Path Expansion:**
- `~` expands to current user's home directory
- Relative paths resolved from current working directory
- Absolute paths used as-is
- Path traversal is validated (no `../../../etc/passwd`)

## See Also

- [Reference Editing](reference-editing.md) — the user guide for the
  `--model`, `--reference`, and `--preset` workflow, including the
  three registered models, the six editing presets, the desktop flow,
  credentials, hardware expectations, privacy policy, and limitations.

