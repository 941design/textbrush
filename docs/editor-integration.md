# Editor Integration Guide

Examples for integrating textbrush into popular text editors and workflows.

## Overview

Textbrush is designed for editor-driven workflows. It follows these principles:

- **Deterministic output**: Prints file path to stdout on success, nothing on abort
- **Stable exit codes**: 0 on accept, 1 on abort/error
- **Minimal UI**: Fast launch, keyboard-driven review
- **Scriptable**: All features accessible via CLI

This makes it ideal for integration with Emacs, Vim, and other text editors.

## Emacs Integration

### Basic Integration

Add to your Emacs config (`~/.emacs.d/init.el` or `~/.config/emacs/init.el`):

```elisp
(defun textbrush-generate-image (prompt output-file)
  "Generate image from PROMPT and save to OUTPUT-FILE using textbrush."
  (interactive
   (list
    (read-string "Prompt: ")
    (read-file-name "Save to: " nil nil nil "image.png")))
  (let* ((default-directory default-directory)
         (cmd (format "uv run textbrush --prompt \"%s\" --out \"%s\""
                      prompt
                      (expand-file-name output-file)))
         (exit-code (shell-command cmd)))
    (if (zerop exit-code)
        (message "Image saved to: %s" output-file)
      (message "Image generation aborted or failed"))))

;; Bind to C-c i (customize as needed)
(global-set-key (kbd "C-c i") 'textbrush-generate-image)
```

### Usage

1. `M-x textbrush-generate-image` or `C-c i`
2. Enter prompt: "a watercolor cat"
3. Choose output path: `~/images/cat.png`
4. Review images in UI, press Enter to accept
5. Image path inserted or file saved

### Advanced: Insert Path at Point

```elisp
(defun textbrush-insert-image-path (prompt)
  "Generate image from PROMPT and insert path at point."
  (interactive "sPrompt: ")
  (let* ((output-file (make-temp-file "textbrush-" nil ".png"))
         (cmd (format "uv run textbrush --prompt \"%s\" --out \"%s\""
                      prompt output-file))
         (exit-code (shell-command cmd)))
    (if (zerop exit-code)
        (progn
          (insert output-file)
          (message "Inserted: %s" output-file))
      (message "Aborted"))))

(global-set-key (kbd "C-c I") 'textbrush-insert-image-path)
```

### Org Mode Integration

```elisp
(defun textbrush-org-insert-image (prompt)
  "Generate image and insert Org link at point."
  (interactive "sPrompt: ")
  (let* ((filename (format "%s.png"
                          (replace-regexp-in-string "[^a-z0-9]+" "-" (downcase prompt))))
         (output-file (expand-file-name filename "~/org/images/"))
         (cmd (format "uv run textbrush --prompt \"%s\" --out \"%s\""
                      prompt output-file))
         (exit-code (shell-command cmd)))
    (if (zerop exit-code)
        (progn
          (insert (format "[[file:%s][%s]]" output-file prompt))
          (org-display-inline-images))
      (message "Aborted"))))

(with-eval-after-load 'org
  (define-key org-mode-map (kbd "C-c i") 'textbrush-org-insert-image))
```

### With Seed for Reproducibility

```elisp
(defun textbrush-generate-with-seed (prompt seed output-file)
  "Generate image from PROMPT with SEED for reproducibility."
  (interactive
   (list
    (read-string "Prompt: ")
    (read-number "Seed (0 for random): " 0)
    (read-file-name "Save to: ")))
  (let ((cmd (if (zerop seed)
                 (format "uv run textbrush --prompt \"%s\" --out \"%s\""
                         prompt output-file)
               (format "uv run textbrush --prompt \"%s\" --seed %d --out \"%s\""
                       prompt seed output-file))))
    (shell-command cmd)))
```

## Vim Integration

### Basic Integration

Add to your `.vimrc` or `~/.config/nvim/init.vim`:

```vim
" Generate image from prompt
function! TextbrushGenerate()
    let l:prompt = input('Prompt: ')
    if empty(l:prompt)
        echo "Aborted"
        return
    endif

    let l:output = input('Save to: ', '', 'file')
    if empty(l:output)
        echo "Aborted"
        return
    endif

    let l:cmd = printf("uv run textbrush --prompt \"%s\" --out \"%s\"",
                \ l:prompt, expand(l:output))
    let l:result = system(l:cmd)

    if v:shell_error == 0
        echo "Image saved to: " . l:output
    else
        echo "Aborted or failed"
    endif
endfunction

" Bind to <leader>i
nnoremap <leader>i :call TextbrushGenerate()<CR>
```

### NeoVim with Lua

Add to `~/.config/nvim/init.lua` or `~/.config/nvim/lua/textbrush.lua`:

```lua
local M = {}

M.generate = function()
    vim.ui.input({ prompt = "Prompt: " }, function(prompt)
        if not prompt or prompt == "" then
            return
        end

        vim.ui.input({ prompt = "Save to: ", completion = "file" }, function(output)
            if not output or output == "" then
                return
            end

            local cmd = string.format('uv run textbrush --prompt "%s" --out "%s"',
                                     prompt, vim.fn.expand(output))
            local result = vim.fn.system(cmd)

            if vim.v.shell_error == 0 then
                vim.notify("Image saved to: " .. output, vim.log.levels.INFO)
            else
                vim.notify("Aborted or failed", vim.log.levels.WARN)
            end
        end)
    end)
end

-- Keybinding
vim.keymap.set('n', '<leader>i', M.generate, { desc = "Generate image with textbrush" })

return M
```

### Insert Path at Cursor

```vim
function! TextbrushInsertPath()
    let l:prompt = input('Prompt: ')
    if empty(l:prompt)
        return
    endif

    " Use temp file
    let l:tempfile = tempname() . '.png'
    let l:cmd = printf("uv run textbrush --prompt \"%s\" --out \"%s\"",
                \ l:prompt, l:tempfile)
    call system(l:cmd)

    if v:shell_error == 0
        execute "normal! a" . l:tempfile
    endif
endfunction

nnoremap <leader>I :call TextbrushInsertPath()<CR>
```

### Markdown Integration

```vim
" Insert Markdown image link
function! TextbrushMarkdown()
    let l:prompt = input('Prompt: ')
    if empty(l:prompt)
        return
    endif

    " Generate filename from prompt
    let l:filename = substitute(tolower(l:prompt), '[^a-z0-9]', '-', 'g') . '.png'
    let l:output = './images/' . l:filename

    let l:cmd = printf("uv run textbrush --prompt \"%s\" --out \"%s\"",
                \ l:prompt, l:output)
    call system(l:cmd)

    if v:shell_error == 0
        execute "normal! a![" . l:prompt . "](" . l:output . ")"
    endif
endfunction

autocmd FileType markdown nnoremap <buffer> <leader>i :call TextbrushMarkdown()<CR>
```

## VSCode Integration

### Tasks Configuration

Create `.vscode/tasks.json` in your project:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Generate Image with Textbrush",
            "type": "shell",
            "command": "uv",
            "args": [
                "run",
                "textbrush",
                "--prompt",
                "${input:prompt}",
                "--out",
                "${input:outputPath}"
            ],
            "presentation": {
                "reveal": "always",
                "panel": "new"
            }
        }
    ],
    "inputs": [
        {
            "id": "prompt",
            "type": "promptString",
            "description": "Image generation prompt"
        },
        {
            "id": "outputPath",
            "type": "promptString",
            "description": "Output file path",
            "default": "${workspaceFolder}/images/image.png"
        }
    ]
}
```

Usage: `Ctrl+Shift+P` → "Tasks: Run Task" → "Generate Image with Textbrush"

### Custom Extension

For more advanced integration, consider creating a VSCode extension that:
- Provides command palette integration
- Shows image previews inline
- Manages image galleries
- Supports workspace-specific prompts

## Shell Scripts

### Batch Generation

```bash
#!/bin/bash
# batch-generate.sh - Generate multiple images

PROMPTS_FILE="$1"
OUTPUT_DIR="${2:-.}"

if [ ! -f "$PROMPTS_FILE" ]; then
    echo "Usage: $0 prompts.txt [output-dir]"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

while IFS= read -r prompt; do
    [ -z "$prompt" ] && continue

    filename=$(echo "$prompt" | tr '[:upper:]' '[:lower:]' | tr -s ' ' '-' | tr -cd '[:alnum:]-').png
    output="$OUTPUT_DIR/$filename"

    echo "Generating: $prompt"
    if uv run textbrush --prompt "$prompt" --out "$output" --headless --auto-accept; then
        echo "✓ Saved: $output"
    else
        echo "✗ Failed: $prompt"
    fi
done < "$PROMPTS_FILE"
```

Usage:
```bash
# Create prompts file
cat > prompts.txt <<EOF
a watercolor cat
a mountain landscape
an abstract pattern
EOF

# Generate all
./batch-generate.sh prompts.txt ./generated-images/
```

### Reproducible Generation with Seeds

```bash
#!/bin/bash
# reproducible-generate.sh - Generate with seed for docs

PROMPT="$1"
SEED="${2:-42}"
OUTPUT="$3"

if [ -z "$PROMPT" ] || [ -z "$OUTPUT" ]; then
    echo "Usage: $0 \"prompt\" [seed] output.png"
    exit 1
fi

echo "Generating with seed $SEED (reproducible)"
uv run textbrush \
    --prompt "$PROMPT" \
    --seed "$SEED" \
    --out "$OUTPUT" \
    --format png

echo "To regenerate identical image:"
echo "  $0 \"$PROMPT\" $SEED $OUTPUT"
```

### Integration with Make/Build Systems

```makefile
# Makefile for documentation with generated images

IMAGES := $(wildcard docs/images/*.txt)
OUTPUTS := $(IMAGES:.txt=.png)

.PHONY: all clean

all: $(OUTPUTS)

docs/images/%.png: docs/images/%.txt
    @echo "Generating $@..."
    @prompt=$$(cat $<); \
    uv run textbrush \
        --prompt "$$prompt" \
        --out $@ \
        --seed 42 \
        --headless \
        --auto-accept

clean:
    rm -f docs/images/*.png
```

Usage:
```bash
# Create prompt files
echo "a flowchart diagram" > docs/images/flowchart.txt
echo "a sequence diagram" > docs/images/sequence.txt

# Generate all images
make

# Regenerate if prompts change
make clean && make
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/generate-docs-images.yml
name: Generate Documentation Images

on:
  push:
    paths:
      - 'docs/prompts/*.txt'
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev

      - name: Setup UV
        run: pip install uv

      - name: Install textbrush
        run: uv sync

      - name: Generate images
        env:
          HUGGINGFACE_HUB_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          for prompt_file in docs/prompts/*.txt; do
            prompt=$(cat "$prompt_file")
            output="docs/images/$(basename "$prompt_file" .txt).png"
            uv run textbrush \
              --prompt "$prompt" \
              --out "$output" \
              --headless \
              --auto-accept \
              --seed 42
          done

      - name: Commit generated images
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add docs/images/*.png
          git commit -m "Update generated images" || echo "No changes"
          git push
```

## Tips for Editor Integration

1. **Use absolute paths** for output files to avoid confusion
2. **Set seeds** for documentation images to ensure reproducibility
3. **Use headless mode** (`--headless --auto-accept`) for fully automated workflows
4. **Check exit codes** to handle abort vs success in scripts
5. **Configure project defaults** in `.textbrush.toml` for project-specific settings
6. **Use environment variables** for CI/CD environments (`TEXTBRUSH_*` prefix)
7. **Capture stdout** to get the output file path programmatically

## Troubleshooting Editor Integration

**Issue: Editor hangs when running textbrush**
- Use `--headless --auto-accept` to avoid UI blocking editor
- Run in background with `&` or async execution

**Issue: Exit codes not detected**
- Ensure using `shell-command` (Emacs) or `system()` (Vim) that captures exit code
- Check `v:shell_error` (Vim) or `shell-command` return value (Emacs)

**Issue: Paths with spaces fail**
- Always quote file paths in commands: `"%s"` not `%s`
- Use `expand-file-name` (Emacs) or `expand()` (Vim)

**Issue: Environment variables not available**
- Set in editor config before launching:
  ```elisp
  (setenv "HUGGINGFACE_HUB_TOKEN" "hf_xxx")
  ```
  ```vim
  let $HUGGINGFACE_HUB_TOKEN = "hf_xxx"
  ```
