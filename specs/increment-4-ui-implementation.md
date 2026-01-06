# Increment 4: UI Implementation - Slideshow Review Interface

## Overview
Build the complete user interface for the image review slideshow. This increment creates the polished, production-ready UI with all visual states, animations, and user interactions.

## Goals
- Create distraction-free, minimal UI layout
- Implement all visual states (loading, image ready, buffer empty)
- Add smooth transitions and loading indicators
- Ensure keyboard and mouse controls are responsive
- Meet performance targets (<100ms skip latency)

## Prerequisites
- Increment 3 complete (Tauri + IPC working)

## Deliverables

### 4.1 UI Architecture

```
src-tauri/ui/
├── index.html
├── styles/
│   ├── main.css
│   ├── variables.css
│   └── animations.css
├── components/
│   ├── ImageViewer.js
│   ├── Controls.js
│   ├── StatusBar.js
│   └── LoadingState.js
└── main.js
```

### 4.2 Window Configuration

Update `tauri.conf.json` for production window:

```json
{
  "app": {
    "windows": [
      {
        "title": "Textbrush",
        "width": 800,
        "height": 700,
        "resizable": false,
        "center": true,
        "decorations": true,
        "transparent": false,
        "alwaysOnTop": false,
        "focus": true
      }
    ]
  }
}
```

### 4.3 Visual Design System

**Design Tokens (`styles/variables.css`):**

```css
:root {
    /* Colors */
    --bg-primary: #0d0d0d;
    --bg-secondary: #1a1a1a;
    --bg-tertiary: #262626;

    --text-primary: #ffffff;
    --text-secondary: #a0a0a0;
    --text-muted: #666666;

    --accent-primary: #3b82f6;
    --accent-success: #22c55e;
    --accent-danger: #ef4444;

    --border-subtle: #333333;
    --border-focus: #3b82f6;

    /* Spacing */
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;

    /* Typography */
    --font-mono: 'SF Mono', 'Menlo', 'Monaco', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

    /* Transitions */
    --transition-fast: 100ms ease;
    --transition-normal: 200ms ease;
    --transition-slow: 300ms ease;

    /* Shadows */
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.5);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.5);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
}
```

### 4.4 Main Layout (`index.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Textbrush</title>
    <link rel="stylesheet" href="styles/variables.css">
    <link rel="stylesheet" href="styles/animations.css">
    <link rel="stylesheet" href="styles/main.css">
</head>
<body>
    <main id="app">
        <!-- Image Display Area -->
        <section id="viewer" class="viewer">
            <div id="image-container" class="image-container">
                <img id="current-image" class="current-image" alt="Generated image">
                <div id="loading-overlay" class="loading-overlay hidden">
                    <div class="spinner"></div>
                    <span class="loading-text">Generating...</span>
                </div>
            </div>
        </section>

        <!-- Status Bar -->
        <section id="status-bar" class="status-bar">
            <div class="status-left">
                <span id="prompt-display" class="prompt-display"></span>
            </div>
            <div class="status-right">
                <span id="buffer-indicator" class="buffer-indicator">
                    <span class="buffer-dots"></span>
                    <span class="buffer-text">0/8</span>
                </span>
                <span id="seed-display" class="seed-display"></span>
            </div>
        </section>

        <!-- Controls -->
        <section id="controls" class="controls">
            <button id="btn-abort" class="control-btn btn-abort" title="Abort (Esc)">
                <span class="btn-icon">✕</span>
                <span class="btn-label">Abort</span>
                <span class="btn-shortcut">Esc</span>
            </button>
            <button id="btn-skip" class="control-btn btn-skip" title="Skip (Space/→)">
                <span class="btn-icon">→</span>
                <span class="btn-label">Skip</span>
                <span class="btn-shortcut">Space</span>
            </button>
            <button id="btn-accept" class="control-btn btn-accept" title="Accept (Enter)">
                <span class="btn-icon">✓</span>
                <span class="btn-label">Accept</span>
                <span class="btn-shortcut">Enter</span>
            </button>
        </section>
    </main>

    <script type="module" src="main.js"></script>
</body>
</html>
```

### 4.5 Main Styles (`styles/main.css`)

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    overflow: hidden;
    user-select: none;
    -webkit-user-select: none;
}

#app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    width: 100vw;
}

/* Image Viewer */
.viewer {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--spacing-lg);
    background: var(--bg-secondary);
    position: relative;
}

.image-container {
    position: relative;
    max-width: 100%;
    max-height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.current-image {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    border-radius: 4px;
    box-shadow: var(--shadow-lg);
    transition: opacity var(--transition-normal);
}

.current-image.loading {
    opacity: 0.3;
}

/* Loading Overlay */
.loading-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.7);
    border-radius: 4px;
    transition: opacity var(--transition-normal);
}

.loading-overlay.hidden {
    opacity: 0;
    pointer-events: none;
}

.loading-text {
    margin-top: var(--spacing-md);
    color: var(--text-secondary);
    font-size: 14px;
}

/* Status Bar */
.status-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-lg);
    background: var(--bg-tertiary);
    border-top: 1px solid var(--border-subtle);
    font-size: 13px;
}

.status-left {
    flex: 1;
    overflow: hidden;
}

.prompt-display {
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.status-right {
    display: flex;
    align-items: center;
    gap: var(--spacing-lg);
}

.buffer-indicator {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
}

.buffer-dots {
    display: flex;
    gap: 3px;
}

.buffer-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--border-subtle);
    transition: background var(--transition-fast);
}

.buffer-dot.filled {
    background: var(--accent-primary);
}

.buffer-text {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 11px;
}

.seed-display {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 11px;
}

/* Controls */
.controls {
    display: flex;
    justify-content: center;
    gap: var(--spacing-md);
    padding: var(--spacing-lg);
    background: var(--bg-primary);
}

.control-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-md) var(--spacing-xl);
    min-width: 100px;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.control-btn:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-focus);
}

.control-btn:active {
    transform: scale(0.98);
}

.control-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-icon {
    font-size: 20px;
}

.btn-label {
    font-size: 13px;
    font-weight: 500;
}

.btn-shortcut {
    font-size: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
}

/* Button Variants */
.btn-accept:hover {
    border-color: var(--accent-success);
    background: rgba(34, 197, 94, 0.1);
}

.btn-abort:hover {
    border-color: var(--accent-danger);
    background: rgba(239, 68, 68, 0.1);
}

/* Focus states for accessibility */
.control-btn:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
}
```

### 4.6 Animations (`styles/animations.css`)

```css
/* Spinner */
.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-subtle);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Image Transitions */
.image-enter {
    animation: fadeIn var(--transition-normal) ease forwards;
}

.image-exit {
    animation: fadeOut var(--transition-fast) ease forwards;
}

@keyframes fadeIn {
    from { opacity: 0; transform: scale(0.98); }
    to { opacity: 1; transform: scale(1); }
}

@keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
}

/* Button press feedback */
.btn-pressed {
    animation: btnPress 150ms ease;
}

@keyframes btnPress {
    0% { transform: scale(1); }
    50% { transform: scale(0.95); }
    100% { transform: scale(1); }
}

/* Buffer dot pulse when generating */
.buffer-generating .buffer-dot:last-child {
    animation: pulse 1s ease infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 1; }
}
```

### 4.7 Application Logic (`main.js`)

```javascript
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { appWindow } = window.__TAURI__.window;

// State
let state = {
    currentImage: null,
    currentSeed: null,
    bufferCount: 0,
    bufferMax: 8,
    isGenerating: false,
    isTransitioning: false,
    prompt: ''
};

// DOM Elements
const elements = {
    image: document.getElementById('current-image'),
    loadingOverlay: document.getElementById('loading-overlay'),
    promptDisplay: document.getElementById('prompt-display'),
    bufferIndicator: document.getElementById('buffer-indicator'),
    seedDisplay: document.getElementById('seed-display'),
    btnSkip: document.getElementById('btn-skip'),
    btnAccept: document.getElementById('btn-accept'),
    btnAbort: document.getElementById('btn-abort'),
};

// Initialize
async function init() {
    // Get launch arguments from Tauri
    const args = await invoke('get_launch_args');
    state.prompt = args.prompt;
    elements.promptDisplay.textContent = `"${args.prompt}"`;

    // Start generation
    await invoke('init_generation', {
        prompt: args.prompt,
        outputPath: args.outputPath,
        seed: args.seed,
        aspectRatio: args.aspectRatio || '1:1'
    });

    showLoading(true, 'Loading model...');
}

// Event Listeners
listen('sidecar-message', (event) => {
    handleMessage(event.payload);
});

function handleMessage(msg) {
    switch (msg.type) {
        case 'ready':
            showLoading(true, 'Generating first image...');
            state.isGenerating = true;
            updateBufferDisplay();
            break;

        case 'image_ready':
            displayImage(msg.payload);
            break;

        case 'buffer_status':
            state.bufferCount = msg.payload.count;
            state.bufferMax = msg.payload.max;
            state.isGenerating = msg.payload.generating;
            updateBufferDisplay();
            break;

        case 'accepted':
            handleAccepted(msg.payload.path);
            break;

        case 'aborted':
            handleAborted();
            break;

        case 'error':
            handleError(msg.payload);
            break;
    }
}

function displayImage(payload) {
    if (state.isTransitioning) return;
    state.isTransitioning = true;

    const img = elements.image;

    // Fade out current
    img.classList.add('image-exit');

    setTimeout(() => {
        // Update image
        img.src = `data:image/png;base64,${payload.image_data}`;
        state.currentSeed = payload.seed;
        state.bufferCount = payload.buffer_count;
        state.bufferMax = payload.buffer_max;

        // Update displays
        elements.seedDisplay.textContent = `seed: ${payload.seed}`;
        updateBufferDisplay();

        // Fade in new
        img.classList.remove('image-exit');
        img.classList.add('image-enter');
        showLoading(false);

        setTimeout(() => {
            img.classList.remove('image-enter');
            state.isTransitioning = false;
        }, 200);
    }, 100);
}

function updateBufferDisplay() {
    const container = elements.bufferIndicator;
    container.classList.toggle('buffer-generating', state.isGenerating);

    // Update dots
    let dotsHtml = '';
    for (let i = 0; i < state.bufferMax; i++) {
        const filled = i < state.bufferCount ? 'filled' : '';
        dotsHtml += `<span class="buffer-dot ${filled}"></span>`;
    }
    container.querySelector('.buffer-dots').innerHTML = dotsHtml;
    container.querySelector('.buffer-text').textContent =
        `${state.bufferCount}/${state.bufferMax}`;
}

function showLoading(show, text = 'Generating...') {
    elements.loadingOverlay.classList.toggle('hidden', !show);
    elements.loadingOverlay.querySelector('.loading-text').textContent = text;
    elements.image.classList.toggle('loading', show);
}

// Actions
async function skip() {
    if (state.isTransitioning) return;

    elements.btnSkip.classList.add('btn-pressed');
    setTimeout(() => elements.btnSkip.classList.remove('btn-pressed'), 150);

    if (state.bufferCount === 0) {
        showLoading(true, 'Waiting for next image...');
    }

    await invoke('skip_image');
}

async function accept() {
    if (state.isTransitioning || !state.currentSeed) return;

    elements.btnAccept.classList.add('btn-pressed');
    elements.btnAccept.disabled = true;

    await invoke('accept_image');
}

async function abort() {
    elements.btnAbort.classList.add('btn-pressed');
    elements.btnAbort.disabled = true;

    await invoke('abort_generation');
}

function handleAccepted(path) {
    // Print path to stdout (handled by Tauri)
    console.log(path);

    // Show brief success state
    elements.image.style.boxShadow = '0 0 20px var(--accent-success)';

    setTimeout(() => {
        appWindow.close();
    }, 300);
}

function handleAborted() {
    setTimeout(() => {
        appWindow.close();
    }, 100);
}

function handleError(payload) {
    if (payload.fatal) {
        showLoading(true, `Error: ${payload.message}`);
        setTimeout(() => appWindow.close(), 3000);
    } else {
        console.error(payload.message);
    }
}

// Button handlers
elements.btnSkip.addEventListener('click', skip);
elements.btnAccept.addEventListener('click', accept);
elements.btnAbort.addEventListener('click', abort);

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Prevent default for our shortcuts
    if (['Enter', ' ', 'ArrowRight', 'Escape'].includes(e.key)) {
        e.preventDefault();
    }

    switch (e.key) {
        case ' ':
        case 'ArrowRight':
            skip();
            break;
        case 'Enter':
            accept();
            break;
        case 'Escape':
            abort();
            break;
    }
});

// Start app
init();
```

### 4.8 Tauri Stdout Handling

Handle the exit contract for CLI integration:

```rust
// src-tauri/src/main.rs additions

use std::process::exit;

fn setup_exit_handler(app: &mut tauri::App) {
    let window = app.get_webview_window("main").unwrap();

    window.on_window_event(move |event| {
        if let tauri::WindowEvent::CloseRequested { .. } = event {
            // Default to abort exit code
            exit(1);
        }
    });
}

#[command]
fn print_and_exit(path: String) {
    // Print accepted path to stdout
    println!("{}", path);
    exit(0);
}

#[command]
fn abort_exit() {
    // Exit with non-zero, empty stdout
    exit(1);
}
```

## Acceptance Criteria

1. [ ] Window opens at correct size, centered
2. [ ] Loading spinner shows during model load
3. [ ] First image displays when ready
4. [ ] Skip transitions smoothly to next image (<100ms when buffered)
5. [ ] Skip shows loading when buffer empty
6. [ ] Buffer indicator updates in real-time
7. [ ] Accept saves image and closes window
8. [ ] Accept prints path to stdout
9. [ ] Abort closes window immediately
10. [ ] Abort exits with non-zero code
11. [ ] Keyboard shortcuts work (Enter/Space/→/Esc)
12. [ ] Mouse buttons work correctly
13. [ ] Prompt displays in status bar
14. [ ] Seed displays for each image

## Testing

**Manual Test Checklist:**
- [ ] Cold start with no cached model
- [ ] Warm start with cached model
- [ ] Rapid skip presses
- [ ] Skip when buffer empty
- [ ] Accept first generated image
- [ ] Accept after multiple skips
- [ ] Abort immediately after launch
- [ ] Abort after viewing images
- [ ] Keyboard navigation only
- [ ] Mouse navigation only

**Performance Targets (per spec):**
- [ ] CLI → UI visible: <500ms
- [ ] Skip latency (buffer non-empty): <100ms
- [ ] First image: as soon as inference allows

## Performance Optimization Notes

1. **Image Preloading**: When buffer > 1, preload next image in hidden element
2. **Base64 Efficiency**: Consider blob URLs for large images
3. **Animation Frames**: Use requestAnimationFrame for transitions
4. **Event Debouncing**: Prevent rapid-fire skip commands
5. **Memory Management**: Clear old image data after transitions
