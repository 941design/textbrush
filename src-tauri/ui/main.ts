// Textbrush UI Application Logic
// Handles image review workflow, state management, and user interactions via Tauri IPC

import * as ConfigControls from './config_controls';
import * as ThemeManager from './theme-manager';
import * as HistoryManager from './history-manager';
import * as ButtonFlash from './button-flash';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
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
  HistoryEntry,
} from './types';

// Get current window reference
const appWindow = getCurrentWindow();

// State Management
const state: AppState = {
  currentImage: null,
  currentSeed: null,
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
  viewer: null,
  imageContainer: null,
  currentImage: null,
  loadingOverlay: null,
  loadingSpinner: null,
  loadingPrompt: null,
  statusBar: null,
  promptDisplay: null,
  promptInput: null,
  aspectRatioRadios: null,
  aspectRatioControls: null,
  dimensionControls: null,
  widthInput: null,
  heightInput: null,
  validationError: null,
  bufferIndicator: null,
  bufferDots: null,
  bufferText: null,
  outputPathDisplay: null,
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
  elements.viewer = document.querySelector('.viewer');
  elements.imageContainer = document.querySelector('.image-container');
  elements.currentImage = document.querySelector('.current-image') as HTMLImageElement | null;
  elements.loadingOverlay = document.getElementById('loading-overlay');
  elements.loadingSpinner = document.querySelector('.spinner');
  elements.loadingPrompt = document.getElementById('loading-prompt');
  elements.statusBar = document.querySelector('.status-bar');
  elements.promptDisplay = document.getElementById('prompt-display');
  elements.promptInput = document.getElementById('prompt-input') as HTMLInputElement | null;
  elements.aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');
  elements.aspectRatioControls = document.querySelector('.aspect-ratio-control');
  elements.dimensionControls = document.querySelector('.dimension-control');
  elements.widthInput = document.getElementById('width-input') as HTMLInputElement | null;
  elements.heightInput = document.getElementById('height-input') as HTMLInputElement | null;
  elements.validationError = document.getElementById('validation-error');
  elements.bufferIndicator = document.getElementById('buffer-indicator');
  elements.bufferDots = document.getElementById('buffer-dots');
  elements.bufferText = document.getElementById('buffer-text');
  elements.outputPathDisplay = document.getElementById('output-path-display');
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
    // Initialize theme before DOM manipulation
    ThemeManager.initTheme();

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

    // Initialize config controls
    ConfigControls.initConfigControls(state.prompt, state.aspectRatio, state, elements);

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

function handleImageReady(payload: ImagePayload): void {
  state.currentImage = payload;
  state.currentSeed = payload.seed || null;
  state.bufferCount = payload.buffer_count || 0;
  state.bufferMax = payload.buffer_max || 8;

  // Add new image to history
  state.imageHistory.push({
    image_data: payload.image_data,
    seed: payload.seed,
    blobUrl: null,
    prompt: payload.prompt || '',
    model_name: payload.model_name || '',
  });
  state.historyIndex = state.imageHistory.length - 1;
  state.waitingForNext = false;

  void displayImage(payload);
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
      entry.path = payload.path;
    }
  }

  const allPaths = HistoryManager.getAllRetainedPaths(state);

  visualSuccessFeedback();
  setTimeout(() => {
    void (async () => {
      try {
        for (const entry of state.imageHistory) {
          if (entry.blobUrl) {
            URL.revokeObjectURL(entry.blobUrl);
          }
        }

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
        for (const entry of state.imageHistory) {
          if (entry.blobUrl) {
            URL.revokeObjectURL(entry.blobUrl);
          }
        }

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

interface DisplayPayload {
  image_data?: string;
  blobUrl?: string | null;
  seed?: number;
  prompt?: string;
  model_name?: string;
}

// Display Image with Transitions
async function displayImage(payload: DisplayPayload, historyIdx: number | null = null): Promise<void> {
  console.log('displayImage called, seed:', payload.seed, 'data length:', payload.image_data?.length);
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

    if (state.currentBlobUrl && !isHistoryBlobUrl(state.currentBlobUrl)) {
      URL.revokeObjectURL(state.currentBlobUrl);
      state.currentBlobUrl = null;
    }

    if (elements.currentImage && payload.image_data) {
      console.log('Creating blob from base64 data...');
      const binaryString = atob(payload.image_data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: 'image/png' });
      state.currentBlobUrl = URL.createObjectURL(blob);

      const idx = historyIdx !== null ? historyIdx : state.historyIndex;
      if (idx >= 0 && idx < state.imageHistory.length) {
        const entry = state.imageHistory[idx];
        if (entry) {
          entry.blobUrl = state.currentBlobUrl;
        }
      }

      console.log('Setting image src to blob URL:', state.currentBlobUrl);
      elements.currentImage.src = state.currentBlobUrl;
    } else if (elements.currentImage && payload.blobUrl) {
      console.log('Using existing blob URL from history:', payload.blobUrl);
      state.currentBlobUrl = payload.blobUrl;
      elements.currentImage.src = payload.blobUrl;
    } else {
      console.warn('Cannot display image - missing element or data:', {
        hasElement: !!elements.currentImage,
        hasData: !!payload.image_data,
        hasBlobUrl: !!payload.blobUrl,
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

    updateMetadataPanel(payload);
  } catch (error) {
    console.error('Error displaying image:', error);
  } finally {
    state.isTransitioning = false;
  }
}

function updateMetadataPanel(payload: DisplayPayload | null): void {
  const metadataPrompt = document.getElementById('metadata-prompt');
  const metadataModel = document.getElementById('metadata-model');
  const metadataSeed = document.getElementById('metadata-seed');

  if (!metadataPrompt || !metadataModel || !metadataSeed) {
    return;
  }

  if (payload && payload.image_data) {
    metadataPrompt.textContent = payload.prompt || '—';
    metadataModel.textContent = payload.model_name || '—';
    metadataSeed.textContent = payload.seed !== undefined ? String(payload.seed) : '—';
  } else {
    metadataPrompt.textContent = '—';
    metadataModel.textContent = '—';
    metadataSeed.textContent = '—';
  }
}

function isHistoryBlobUrl(blobUrl: string): boolean {
  return state.imageHistory.some(item => item.blobUrl === blobUrl);
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
      void displayImage(historyItem, state.historyIndex);
    }
    return;
  }

  const navigated = HistoryManager.navigateToPrevious(state, (entry: HistoryEntry) => {
    void displayImage(entry, state.historyIndex);
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
            void displayImage(historyItem, state.historyIndex);
          }
        }
      });
  };

  HistoryManager.navigateToNext(
    state,
    (entry: HistoryEntry) => {
      void displayImage(entry, state.historyIndex);
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
  updateMetadataPanel(null);
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
    (entry: HistoryEntry) => {
      void displayImage(entry, state.historyIndex);
    },
    () => {
      if (elements.currentImage) {
        elements.currentImage.classList.add('hidden');
      }
      updateMetadataPanel(null);
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
      displayImage: typeof displayImage;
      updateBufferDisplay: typeof updateBufferDisplay;
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
      isHistoryBlobUrl: typeof isHistoryBlobUrl;
    };
  }
}

if (typeof window !== 'undefined') {
  window.textbrushApp = {
    state,
    elements,
    init,
    handleMessage,
    displayImage,
    updateBufferDisplay,
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
    isHistoryBlobUrl,
  };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => void init());
} else {
  void init();
}
