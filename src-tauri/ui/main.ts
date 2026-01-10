// Textbrush UI Application Logic
// Handles image review workflow, state management, and user interactions via Tauri IPC

import * as ConfigControls from './config_controls';
import * as ThemeManager from './theme-manager';
import * as FontSizeManager from './font-size-manager';
import * as HistoryManager from './history-manager';
import * as ButtonFlash from './button-flash';
import { invoke, convertFileSrc } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { fetchAndParsePngMetadata } from './png-metadata';
import type {
  AppState,
  Elements,
  LaunchArgs,
  SidecarMessage,
  ImagePayload,
  BufferStatusPayload,
  AcceptedPayload,
  ErrorPayload,
  PausedPayload,
  ReadyPayload,
  ImageRecord,
} from './types';

// Get current window reference
const appWindow = getCurrentWindow();

// State Management
const state: AppState = {
  currentImage: null,
  bufferCount: 0,
  bufferMax: 8,
  isGenerating: false,
  isPaused: false,
  isTransitioning: false,
  prompt: '',
  aspectRatio: '1:1',
  width: 1024,
  height: 1024,
  outputPath: null,
  actionQueue: Promise.resolve(),
  currentBlobUrl: null,
  imageHistory: [],
  historyIndex: -1,
  waitingForNext: false,
};

// DOM Element References
const elements: Elements = {
  app: null,
  headerBar: null,
  viewer: null,
  imageContainer: null,
  currentImage: null,
  loadingOverlay: null,
  loadingSpinner: null,
  loadingPrompt: null,
  navIndicator: null,
  navDots: null,
  statusBar: null,
  promptDisplay: null,
  promptInput: null,
  aspectRatioRadios: null,
  aspectRatioControls: null,
  resolutionControls: null,
  dimensionDisplay: null,
  resolutionDecrease: null,
  resolutionIncrease: null,
  validationError: null,
  fontSizeRadios: null,
  bufferIndicator: null,
  bufferDots: null,
  bufferText: null,
  outputPathDisplay: null,
  metadataPath: null,
  controls: null,
  skipButton: null,
  acceptButton: null,
  abortButton: null,
  pauseButton: null,
  pauseIcon: null,
  pauseLabel: null,
  themeToggle: null,
};

function cacheElements(): void {
  elements.app = document.getElementById('app');
  elements.headerBar = document.querySelector('.header-bar');
  elements.viewer = document.querySelector('.viewer');
  elements.imageContainer = document.querySelector('.image-container');
  elements.currentImage = document.querySelector('.current-image') as HTMLImageElement | null;
  elements.loadingOverlay = document.getElementById('loading-overlay');
  elements.loadingSpinner = document.querySelector('.spinner');
  elements.loadingPrompt = document.getElementById('loading-prompt');
  elements.navIndicator = document.getElementById('nav-indicator');
  elements.navDots = document.getElementById('nav-dots');
  elements.statusBar = document.querySelector('.status-bar');
  elements.promptDisplay = document.getElementById('prompt-display');
  elements.promptInput = document.getElementById('prompt-input') as HTMLInputElement | null;
  elements.aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');
  elements.aspectRatioControls = document.querySelector('.aspect-ratio-control');
  elements.resolutionControls = document.querySelector('.resolution-control');
  elements.dimensionDisplay = document.getElementById('dimension-display');
  elements.resolutionDecrease = document.getElementById('resolution-decrease') as HTMLButtonElement | null;
  elements.resolutionIncrease = document.getElementById('resolution-increase') as HTMLButtonElement | null;
  elements.validationError = document.getElementById('validation-error');
  elements.fontSizeRadios = document.querySelectorAll('input[name="font-size"]');
  elements.bufferIndicator = document.getElementById('buffer-indicator');
  elements.bufferDots = document.getElementById('buffer-dots');
  elements.bufferText = document.getElementById('buffer-text');
  elements.outputPathDisplay = document.getElementById('output-path-display');
  elements.metadataPath = document.getElementById('metadata-path');
  elements.controls = document.querySelector('.controls');
  elements.skipButton = document.getElementById('skip-btn') as HTMLButtonElement | null;
  elements.acceptButton = document.getElementById('accept-btn') as HTMLButtonElement | null;
  elements.abortButton = document.getElementById('abort-btn') as HTMLButtonElement | null;
  elements.pauseButton = document.getElementById('pause-btn') as HTMLButtonElement | null;
  elements.pauseIcon = document.getElementById('pause-icon');
  elements.pauseLabel = document.getElementById('pause-label');
  elements.themeToggle = document.getElementById('theme-toggle') as HTMLButtonElement | null;
}

function allElementsPresent(): boolean {
  return Object.values(elements).every(el => el !== null);
}

// Initialize Application
async function init(): Promise<void> {
  console.log('Textbrush UI initializing...');
  try {
    // Initialize theme and font size before DOM manipulation
    ThemeManager.initTheme();
    FontSizeManager.initFontSize();

    // Cache all DOM elements
    cacheElements();

    if (!allElementsPresent()) {
      const missing = Object.entries(elements)
        .filter(([, el]) => el === null)
        .map(([key]) => key);
      console.error('Missing DOM elements:', missing);
      throw new Error(`Missing DOM elements: ${missing.join(', ')}`);
    }

    console.log('DOM elements cached, getting launch args...');
    // Get launch arguments from invoke call
    const launchArgs = await invoke<LaunchArgs>('get_launch_args');
    console.log('Launch args received:', launchArgs);
    state.prompt = launchArgs.prompt || '';
    state.aspectRatio = launchArgs.aspect_ratio || '1:1';
    state.bufferMax = launchArgs.buffer_max || 8;
    state.outputPath = launchArgs.output_path || null;

    // Display the output path
    if (elements.outputPathDisplay) {
      if (state.outputPath) {
        elements.outputPathDisplay.textContent = `path: ${state.outputPath}`;
        elements.outputPathDisplay.title = state.outputPath;
      } else {
        elements.outputPathDisplay.textContent = 'path: (default)';
        elements.outputPathDisplay.title = 'Using default output directory';
      }
    }

    // Display the prompt (legacy support if config controls not initialized)
    if (elements.promptDisplay) {
      elements.promptDisplay.textContent = `Prompt: ${state.prompt}`;
    }

    // Set the prompt in the loading caption
    if (elements.loadingPrompt) {
      elements.loadingPrompt.textContent = state.prompt || 'waiting...';
    }

    // Initialize config controls with dimensions from launch args
    state.width = launchArgs.width;
    state.height = launchArgs.height;
    ConfigControls.initConfigControls(
      state.prompt,
      state.aspectRatio,
      launchArgs.width,
      launchArgs.height,
      state,
      elements
    );

    // Setup event listeners
    setupMessageListener();
    setupButtonListeners();
    setupKeyboardListeners();

    // Initialize image generation
    await invoke('init_generation', {
      prompt: state.prompt,
      outputPath: launchArgs.output_path || null,
      seed: launchArgs.seed || null,
      aspectRatio: launchArgs.aspect_ratio || '1:1',
      width: launchArgs.width,
      height: launchArgs.height,
    });

    console.log('Application initialized successfully');
  } catch (error) {
    console.error('Initialization failed:', error);
    if (elements.loadingPrompt) {
      elements.loadingPrompt.textContent = `Error: ${error instanceof Error ? error.message : String(error)}`;
    }
  }
}

// Message Event Listener
function setupMessageListener(): void {
  console.log('Setting up sidecar message listener...');
  listen<SidecarMessage>('sidecar-message', (event) => {
    const msg = event.payload;
    console.log('Received sidecar message:', msg.type, msg);
    handleMessage(msg);
  }).catch(err => {
    console.error('Failed to setup message listener:', err);
  });
}

// Message Handler with Type Dispatch
function handleMessage(msg: SidecarMessage): void {
  if (!msg || !msg.type) {
    console.warn('Invalid message format:', msg);
    return;
  }

  switch (msg.type) {
    case 'ready':
      handleReady(msg.payload as ReadyPayload);
      break;

    case 'image_ready':
      handleImageReady(msg.payload as ImagePayload);
      break;

    case 'buffer_status':
      handleBufferStatus(msg.payload as BufferStatusPayload);
      break;

    case 'accepted':
      void handleAccepted(msg.payload as AcceptedPayload);
      break;

    case 'aborted':
      handleAborted();
      break;

    case 'error':
      handleError(msg.payload as ErrorPayload);
      break;

    case 'paused':
      handlePaused(msg.payload as PausedPayload);
      break;

    default:
      console.warn('Unknown message type:', msg.type);
  }
}

// Message Handlers
function handleReady(payload: ReadyPayload): void {
  state.isGenerating = true;
  state.bufferCount = payload.buffer_count || 0;
  updateBufferDisplay();
}

async function handleImageReady(payload: ImagePayload): Promise<void> {
  state.currentImage = payload;
  state.bufferCount = payload.buffer_count || 0;
  state.bufferMax = payload.buffer_max || 8;

  // Convert file path to asset URL for display
  const assetUrl = convertFileSrc(payload.path);
  console.log('Loading image from:', payload.path, '-> asset URL:', assetUrl);

  // Parse PNG metadata from file (includes seed)
  const metadata = await fetchAndParsePngMetadata(assetUrl);
  console.log('Parsed metadata:', metadata);

  // Create image record with parsed metadata
  const record: ImageRecord = {
    path: payload.path,
    seed: metadata.seed ?? 0,
    blobUrl: assetUrl,
    prompt: metadata.prompt ?? '',
    model: metadata.model ?? '',
    aspectRatio: metadata.aspectRatio ?? state.aspectRatio,
    width: metadata.width ?? 0,
    height: metadata.height ?? 0,
    generatedWidth: metadata.generatedWidth,
    generatedHeight: metadata.generatedHeight,
  };

  // Add to history
  state.imageHistory.push(record);
  state.historyIndex = state.imageHistory.length - 1;
  state.waitingForNext = false;

  void displayImageRecord(record);
  updateBufferDisplay();
  showLoading(false);
  enableAcceptButton();
}

function handleBufferStatus(payload: BufferStatusPayload): void {
  state.bufferCount = payload.count || 0;
  state.isGenerating = payload.generating || false;
  updateBufferDisplay();
}

async function handleAccepted(payload: AcceptedPayload): Promise<void> {
  if (payload.path && state.historyIndex >= 0 && state.historyIndex < state.imageHistory.length) {
    const entry = state.imageHistory[state.historyIndex];
    if (entry) {
      entry.outputPath = payload.path;
    }
  }

  const allPaths = HistoryManager.getAllRetainedPaths(state);

  visualSuccessFeedback();
  setTimeout(() => {
    void (async () => {
      try {
        // Note: asset URLs from convertFileSrc don't need revoking like blob URLs

        if (allPaths.length === 0) {
          await invoke('abort_exit');
        } else if (allPaths.length === 1) {
          await invoke('print_and_exit', { path: allPaths[0] });
        } else {
          await invoke('print_paths_and_exit', { paths: allPaths });
        }
      } catch (err) {
        console.error('Failed to call exit handler:', err);
        await appWindow.close();
      }
    })();
  }, 500);
}

function handleAborted(): void {
  setTimeout(() => {
    void (async () => {
      try {
        // Note: asset URLs from convertFileSrc don't need revoking like blob URLs

        await invoke('abort_exit');
      } catch (err) {
        console.error('Failed to call abort_exit:', err);
        await appWindow.close();
      }
    })();
  }, 500);
}

function handleError(payload: ErrorPayload): void {
  const message = payload.message || 'Unknown error';
  const fatal = payload.fatal || false;

  console.error('Backend error:', message, 'fatal:', fatal);

  if (fatal) {
    setTimeout(() => {
      void appWindow.close();
    }, 2000);
  }
}

function handlePaused(payload: PausedPayload): void {
  state.isPaused = payload.paused || false;
  updatePauseButton();
  console.log('Generation', state.isPaused ? 'paused' : 'resumed');
}

// Update Pause Button UI
function updatePauseButton(): void {
  if (!elements.pauseIcon || !elements.pauseLabel) {
    return;
  }

  if (state.isPaused) {
    elements.pauseIcon.textContent = '\u25B6';
    elements.pauseLabel.textContent = 'Resume';
    if (elements.pauseButton) {
      elements.pauseButton.title = 'Resume image generation (P)';
      elements.pauseButton.classList.add('paused');
    }
  } else {
    elements.pauseIcon.textContent = '\u23F8';
    elements.pauseLabel.textContent = 'Pause';
    if (elements.pauseButton) {
      elements.pauseButton.title = 'Pause image generation (P)';
      elements.pauseButton.classList.remove('paused');
    }
  }
}

// Display ImageRecord with Transitions
async function displayImageRecord(record: ImageRecord, historyIdx: number | null = null): Promise<void> {
  console.log('displayImageRecord called, seed:', record.seed, 'path:', record.path);
  if (state.isTransitioning) {
    console.log('Skipping - already transitioning');
    return;
  }

  state.isTransitioning = true;

  try {
    const skipAnimations = state.bufferCount > 1;
    const fadeOutDuration = skipAnimations ? 0 : 100;
    const fadeInDuration = skipAnimations ? 0 : 200;

    if (elements.currentImage && elements.currentImage.src) {
      if (!skipAnimations) {
        elements.currentImage.classList.add('image-exit');
      }
      await new Promise(resolve => setTimeout(resolve, fadeOutDuration));
    }

    // Asset URLs from convertFileSrc don't need revoking
    state.currentBlobUrl = record.blobUrl;

    if (elements.currentImage && record.blobUrl) {
      console.log('Setting image src to asset URL:', record.blobUrl);
      elements.currentImage.src = record.blobUrl;
    } else {
      console.warn('Cannot display image - missing element or blobUrl:', {
        hasElement: !!elements.currentImage,
        hasBlobUrl: !!record.blobUrl,
      });
    }

    if (elements.currentImage) {
      elements.currentImage.classList.remove('image-exit');
      if (!skipAnimations) {
        elements.currentImage.classList.add('image-enter');
      }
      await new Promise(resolve => setTimeout(resolve, fadeInDuration));
      elements.currentImage.classList.remove('image-enter');
    }

    const idx = historyIdx !== null ? historyIdx : state.historyIndex;
    updateMetadataPanelFromRecord(record, idx);
    updateNavDots();
  } catch (error) {
    console.error('Error displaying image:', error);
  } finally {
    state.isTransitioning = false;
  }
}

function updateMetadataPanelFromRecord(record: ImageRecord | null, _historyIdx: number | null = null): void {
  const metadataPrompt = document.getElementById('metadata-prompt');
  const metadataModel = document.getElementById('metadata-model');
  const metadataSeed = document.getElementById('metadata-seed');
  const metadataGeneratedSize = document.getElementById('metadata-generated-size');
  const metadataFinalSize = document.getElementById('metadata-final-size');

  if (!metadataPrompt || !metadataModel || !metadataSeed || !metadataGeneratedSize || !metadataFinalSize) {
    return;
  }

  if (record) {
    metadataPrompt.textContent = record.prompt || '—';
    metadataModel.textContent = record.model || '—';
    metadataSeed.textContent = record.seed !== undefined ? String(record.seed) : '—';

    // Update dimension fields
    // CONTRACT:
    // - If generated dimensions present: display both generated and final
    // - If generated dimensions absent: display final only (or "—" if unavailable)
    // - Format: "width×height"
    if (record.generatedWidth !== undefined && record.generatedHeight !== undefined) {
      metadataGeneratedSize.textContent = `${record.generatedWidth}×${record.generatedHeight}`;
    } else {
      metadataGeneratedSize.textContent = '—';
    }

    if (record.width && record.height) {
      metadataFinalSize.textContent = `${record.width}×${record.height}`;
    } else {
      metadataFinalSize.textContent = '—';
    }

    // Update path display - show output path if accepted, otherwise preview path
    if (elements.metadataPath) {
      const path = record.outputPath || record.path;
      const isSaved = !!record.outputPath;
      elements.metadataPath.textContent = isSaved ? path : '(not saved)';
      elements.metadataPath.title = isSaved ? `Click to copy: ${path}` : 'Image not yet saved';
    }
  } else {
    metadataPrompt.textContent = '—';
    metadataModel.textContent = '—';
    metadataSeed.textContent = '—';
    metadataGeneratedSize.textContent = '—';
    metadataFinalSize.textContent = '—';
    if (elements.metadataPath) {
      elements.metadataPath.textContent = '—';
      elements.metadataPath.title = '';
    }
  }
}

function clearMetadataPanel(): void {
  updateMetadataPanelFromRecord(null, null);
}

// Maximum number of dots to display before using ellipsis
const MAX_VISIBLE_DOTS = 9;

function updateNavDots(): void {
  if (!elements.navDots) {
    return;
  }

  const total = state.imageHistory.length;
  const currentIdx = state.historyIndex;

  // Clear existing dots
  elements.navDots.innerHTML = '';

  if (total === 0) {
    return;
  }

  // If total is within limit, show all dots
  if (total <= MAX_VISIBLE_DOTS) {
    for (let i = 0; i < total; i++) {
      const dot = createNavDot(i, i === currentIdx);
      elements.navDots.appendChild(dot);
    }
    return;
  }

  // Otherwise, use ellipsis in the middle
  // Pattern: [first few] ... [current area] ... [last few]
  // We want to show: first 2, current-1, current, current+1, last 2
  // With ellipsis between groups when there are gaps

  const dotsToShow: Array<number | 'ellipsis'> = [];
  const leftEdge = 2; // Show first 2 dots
  const rightEdge = total - 2; // Last 2 dots start here

  // Always show first 2
  for (let i = 0; i < Math.min(leftEdge, total); i++) {
    dotsToShow.push(i);
  }

  // Middle section around current
  const middleStart = Math.max(leftEdge, currentIdx - 1);
  const middleEnd = Math.min(rightEdge - 1, currentIdx + 1);

  // Add ellipsis if there's a gap
  if (middleStart > leftEdge) {
    dotsToShow.push('ellipsis');
  }

  // Add middle section
  for (let i = middleStart; i <= middleEnd; i++) {
    if (!dotsToShow.includes(i)) {
      dotsToShow.push(i);
    }
  }

  // Add ellipsis if there's a gap before the end
  if (middleEnd < rightEdge - 1) {
    dotsToShow.push('ellipsis');
  }

  // Always show last 2
  for (let i = rightEdge; i < total; i++) {
    if (!dotsToShow.includes(i)) {
      dotsToShow.push(i);
    }
  }

  // Render the dots
  for (const item of dotsToShow) {
    if (item === 'ellipsis') {
      const ellipsis = document.createElement('span');
      ellipsis.className = 'nav-ellipsis';
      ellipsis.textContent = '...';
      elements.navDots.appendChild(ellipsis);
    } else {
      const dot = createNavDot(item, item === currentIdx);
      elements.navDots.appendChild(dot);
    }
  }
}

function createNavDot(index: number, isActive: boolean): HTMLElement {
  const dot = document.createElement('span');
  dot.className = 'nav-dot';
  if (isActive) {
    dot.classList.add('active');
  }
  dot.setAttribute('role', 'button');
  dot.setAttribute('aria-label', `Go to image ${index + 1}`);
  dot.setAttribute('tabindex', '0');

  // Click handler to navigate to this image
  dot.addEventListener('click', () => {
    navigateToIndex(index);
  });

  // Keyboard handler
  dot.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      navigateToIndex(index);
    }
  });

  return dot;
}

function navigateToIndex(index: number): void {
  if (state.isTransitioning || index < 0 || index >= state.imageHistory.length) {
    return;
  }

  if (index === state.historyIndex) {
    return;
  }

  state.historyIndex = index;
  const entry = state.imageHistory[index];
  if (entry) {
    void displayImageRecord(entry, index);
  }
}

function updateBufferDisplay(): void {
  if (!elements.bufferDots) {
    return;
  }

  const dots = elements.bufferDots.querySelectorAll('.buffer-dot');
  for (let i = 0; i < dots.length; i++) {
    if (i < state.bufferCount) {
      dots[i]?.classList.add('filled');
    } else {
      dots[i]?.classList.remove('filled');
    }
  }

  if (elements.bufferText) {
    elements.bufferText.textContent = `${state.bufferCount}/${state.bufferMax}`;
  }

  if (state.waitingForNext && state.bufferCount === 0) {
    showLoading(true);
  }
}

function showLoading(show: boolean): void {
  if (!elements.loadingOverlay) {
    return;
  }

  if (show) {
    elements.loadingOverlay.classList.remove('hidden');
    if (elements.currentImage) {
      elements.currentImage.classList.add('hidden');
    }
  } else {
    elements.loadingOverlay.classList.add('hidden');
    if (elements.currentImage) {
      elements.currentImage.classList.remove('hidden');
    }
  }
}

function visualSuccessFeedback(): void {
  if (elements.imageContainer) {
    (elements.imageContainer as HTMLElement).style.boxShadow = '0 0 20px rgba(34, 197, 94, 0.5)';
  }
}

function previous(): void {
  if (state.isTransitioning) {
    return;
  }

  if (state.waitingForNext && state.imageHistory.length > 0) {
    state.waitingForNext = false;
    state.historyIndex = state.imageHistory.length - 1;
    const historyItem = state.imageHistory[state.historyIndex];
    showLoading(false);
    if (historyItem) {
      void displayImageRecord(historyItem, state.historyIndex);
    }
    return;
  }

  const navigated = HistoryManager.navigateToPrevious(state, (entry: ImageRecord) => {
    void displayImageRecord(entry, state.historyIndex);
  });

  if (!navigated) {
    console.log('At beginning of history, cannot go back');
  }
}

function skip(): void {
  if (state.isTransitioning) {
    return;
  }

  if (state.waitingForNext) {
    console.log('Already waiting for next image');
    return;
  }

  const requestNext = () => {
    state.waitingForNext = true;
    showLoadingPlaceholder();

    state.actionQueue = state.actionQueue
      .then(async () => {
        await invoke('skip_image');
      })
      .catch(err => {
        console.error('Skip failed:', err);
        state.waitingForNext = false;
        if (state.imageHistory.length > 0) {
          const historyItem = state.imageHistory[state.historyIndex];
          showLoading(false);
          if (historyItem) {
            void displayImageRecord(historyItem, state.historyIndex);
          }
        }
      });
  };

  HistoryManager.navigateToNext(
    state,
    (entry: ImageRecord) => {
      void displayImageRecord(entry, state.historyIndex);
    },
    requestNext
  );
}

function showLoadingPlaceholder(): void {
  if (elements.currentImage) {
    elements.currentImage.classList.add('hidden');
  }
  if (elements.loadingOverlay) {
    elements.loadingOverlay.classList.remove('hidden');
  }
  clearMetadataPanel();
  updateNavDots();
}

function accept(): void {
  if (elements.acceptButton && !state.isTransitioning) {
    elements.acceptButton.disabled = true;
    invoke('accept_image').catch(err => {
      console.error('Accept failed:', err);
      if (elements.acceptButton) {
        elements.acceptButton.disabled = false;
      }
    });
  }
}

function abort(): void {
  if (state.isTransitioning) {
    return;
  }

  invoke('abort_generation').catch(err => {
    console.error('Abort failed:', err);
  });
}

function togglePause(): void {
  invoke('pause_generation').catch(err => {
    console.error('Pause toggle failed:', err);
  });
}

function deleteCurrentImage(): void {
  if (state.isTransitioning) {
    return;
  }

  HistoryManager.deleteCurrentImage(
    state,
    (entry: ImageRecord) => {
      void displayImageRecord(entry, state.historyIndex);
    },
    () => {
      if (elements.currentImage) {
        elements.currentImage.classList.add('hidden');
      }
      clearMetadataPanel();
      updateNavDots();
    }
  );
}

function enableAcceptButton(): void {
  if (elements.acceptButton) {
    elements.acceptButton.disabled = false;
  }
}

function setupButtonListeners(): void {
  if (elements.skipButton) {
    elements.skipButton.addEventListener('click', skip);
  }

  if (elements.acceptButton) {
    elements.acceptButton.addEventListener('click', accept);
  }

  if (elements.abortButton) {
    elements.abortButton.addEventListener('click', abort);
  }

  if (elements.pauseButton) {
    elements.pauseButton.addEventListener('click', togglePause);
  }

  if (elements.themeToggle) {
    elements.themeToggle.addEventListener('click', () => {
      ThemeManager.toggleTheme();
    });
  }

  // Click handler for metadata path to copy to clipboard
  if (elements.metadataPath) {
    elements.metadataPath.addEventListener('click', () => {
      const idx = state.historyIndex;
      const entry = idx >= 0 && idx < state.imageHistory.length ? state.imageHistory[idx] : null;
      const path = entry?.path;
      if (path) {
        navigator.clipboard.writeText(path).then(() => {
          // Visual feedback
          const original = elements.metadataPath?.textContent;
          if (elements.metadataPath) {
            elements.metadataPath.textContent = 'Copied!';
            setTimeout(() => {
              if (elements.metadataPath && original) {
                elements.metadataPath.textContent = original;
              }
            }, 1000);
          }
        }).catch(err => {
          console.error('Failed to copy path:', err);
        });
      }
    });
  }

  // Font size radio button listeners
  if (elements.fontSizeRadios) {
    // Sync radio buttons with current font size
    const currentSize = FontSizeManager.getCurrentFontSize();
    elements.fontSizeRadios.forEach((radio) => {
      radio.checked = radio.value === currentSize;
      radio.addEventListener('change', () => {
        if (radio.checked) {
          FontSizeManager.setFontSize(radio.value as FontSizeManager.FontSize);
        }
      });
    });
  }
}

function setupKeyboardListeners(): void {
  document.addEventListener('keydown', (e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'INPUT' && (target as HTMLInputElement).type === 'text') {
      return;
    }

    const ctrlOrCmd = e.ctrlKey || e.metaKey;
    ButtonFlash.flashButtonForKey(e.key, ctrlOrCmd);

    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      previous();
    } else if (e.key === ' ' || e.key === 'ArrowRight') {
      e.preventDefault();
      skip();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      accept();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      abort();
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && ctrlOrCmd) {
      e.preventDefault();
      deleteCurrentImage();
    } else if (e.key === 'p' || e.key === 'P') {
      e.preventDefault();
      togglePause();
    }
  });
}

// Expose for testing
declare global {
  interface Window {
    textbrushApp?: {
      state: AppState;
      elements: Elements;
      init: typeof init;
      handleMessage: typeof handleMessage;
      displayImageRecord: typeof displayImageRecord;
      updateBufferDisplay: typeof updateBufferDisplay;
      updateNavDots: typeof updateNavDots;
      navigateToIndex: typeof navigateToIndex;
      showLoading: typeof showLoading;
      showLoadingPlaceholder: typeof showLoadingPlaceholder;
      previous: typeof previous;
      skip: typeof skip;
      accept: typeof accept;
      abort: typeof abort;
      togglePause: typeof togglePause;
      updatePauseButton: typeof updatePauseButton;
      deleteCurrentImage: typeof deleteCurrentImage;
      cacheElements: typeof cacheElements;
      allElementsPresent: typeof allElementsPresent;
    };
  }
}

if (typeof window !== 'undefined') {
  window.textbrushApp = {
    state,
    elements,
    init,
    handleMessage,
    displayImageRecord,
    updateBufferDisplay,
    updateNavDots,
    navigateToIndex,
    showLoading,
    showLoadingPlaceholder,
    previous,
    skip,
    accept,
    abort,
    togglePause,
    updatePauseButton,
    deleteCurrentImage,
    cacheElements,
    allElementsPresent,
  };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => void init());
} else {
  void init();
}
