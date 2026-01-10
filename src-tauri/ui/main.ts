// Textbrush UI Application Logic
// Handles image review workflow, state management, and user interactions via Tauri IPC

import * as ConfigControls from './config_controls';
import * as ThemeManager from './theme-manager';
import * as FontSizeManager from './font-size-manager';
import * as ListManager from './list-manager';
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
  GenerationStartedPayload,
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
  backendReady: false,  // Becomes true when backend sends 'ready' message
  prompt: '',
  generationPrompt: '',  // Confirmed prompt the backend is generating with
  aspectRatio: '1:1',
  width: 1024,
  height: 1024,
  outputPath: null,
  actionQueue: Promise.resolve(),
  currentBlobUrl: null,
  imageList: [],
  currentIndex: -1,
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
  loadingLabel: null,
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
  imagePathDisplay: null,
  pathText: null,
  copyPathBtn: null,
  controls: null,
  previousButton: null,
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
  elements.loadingLabel = document.querySelector('.loading-label');
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
  elements.imagePathDisplay = document.getElementById('image-path-display');
  elements.pathText = document.getElementById('path-text');
  elements.copyPathBtn = document.getElementById('copy-path-btn') as HTMLButtonElement | null;
  elements.controls = document.querySelector('.controls');
  elements.previousButton = document.getElementById('previous-btn') as HTMLButtonElement | null;
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
    state.generationPrompt = launchArgs.prompt || '';  // Initially, generation uses launch prompt
    state.aspectRatio = launchArgs.aspect_ratio || '1:1';
    state.bufferMax = launchArgs.buffer_max || 8;
    state.outputPath = launchArgs.output_path || null;

    // Display the prompt (legacy support if config controls not initialized)
    if (elements.promptDisplay) {
      elements.promptDisplay.textContent = `Prompt: ${state.prompt}`;
    }

    // Loading prompt stays empty until backend is ready (initial state is "waiting for backend")

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

    case 'generation_started':
      handleGenerationStarted(msg.payload as GenerationStartedPayload);
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
  state.backendReady = true;
  state.bufferCount = payload.buffer_count || 0;

  // Update loading overlay to "waiting for image" state with prompt
  if (elements.loadingLabel) {
    elements.loadingLabel.textContent = 'waiting for image';
  }
  if (elements.loadingPrompt) {
    elements.loadingPrompt.textContent = state.generationPrompt || state.prompt;
  }
}

function handleGenerationStarted(payload: GenerationStartedPayload): void {
  // Update loading overlay to show generation is active
  // Only update if loading overlay is currently visible (waiting for image)
  if (elements.loadingLabel && !elements.loadingOverlay?.classList.contains('hidden')) {
    elements.loadingLabel.textContent = 'generating';
  }
  console.log(`Generation started: seed=${payload.seed}, queue_position=${payload.queue_position}`);
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
    displayPath: payload.display_path,
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

  // Add to list
  state.imageList.push(record);
  state.currentIndex = state.imageList.length - 1;
  state.waitingForNext = false;

  // Immediately update nav dots so new image appears in indicator
  updateNavDots();

  // Update generationPrompt when we receive confirmation via image metadata
  // This ensures the loading prompt reflects the actual prompt being generated
  if (record.prompt && record.prompt !== state.generationPrompt) {
    state.generationPrompt = record.prompt;
    if (elements.loadingPrompt) {
      elements.loadingPrompt.textContent = state.generationPrompt;
    }
  }

  void displayImageRecord(record);
  showLoading(false);
  enableAcceptButton();
}

function handleBufferStatus(payload: BufferStatusPayload): void {
  state.bufferCount = payload.count || 0;
  state.isGenerating = payload.generating || false;

  // Show loading if waiting for next image and buffer is empty
  if (state.waitingForNext && state.bufferCount === 0) {
    showLoading(true);
  }
}

async function handleAccepted(payload: AcceptedPayload): Promise<void> {
  if (payload.path && state.currentIndex >= 0 && state.currentIndex < state.imageList.length) {
    const entry = state.imageList[state.currentIndex];
    if (entry) {
      entry.outputPath = payload.path;
      entry.outputDisplayPath = payload.display_path;
    }
  }

  const allPaths = ListManager.getAllRetainedPaths(state);

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
  updateLoadingOverlayForPause();
  console.log('Generation', state.isPaused ? 'paused' : 'resumed');
}

function updateLoadingOverlayForPause(): void {
  // Update spinner visibility, label text, and prompt visibility based on paused state
  if (elements.loadingSpinner) {
    if (state.isPaused) {
      elements.loadingSpinner.classList.add('hidden');
    } else {
      elements.loadingSpinner.classList.remove('hidden');
    }
  }

  if (elements.loadingLabel && !elements.loadingOverlay?.classList.contains('hidden')) {
    if (state.isPaused) {
      elements.loadingLabel.textContent = 'generation paused';
    } else {
      elements.loadingLabel.textContent = 'waiting for image';
    }
  }

  // Hide prompt when paused, show when active
  if (elements.loadingPrompt) {
    if (state.isPaused) {
      elements.loadingPrompt.classList.add('hidden');
    } else {
      elements.loadingPrompt.classList.remove('hidden');
    }
  }
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
      elements.pauseButton.title = 'Resume image generation (Space)';
      elements.pauseButton.classList.add('paused');
    }
  } else {
    elements.pauseIcon.textContent = '\u23F8';
    elements.pauseLabel.textContent = 'Pause';
    if (elements.pauseButton) {
      elements.pauseButton.title = 'Pause image generation (Space)';
      elements.pauseButton.classList.remove('paused');
    }
  }
}

// Display ImageRecord with Transitions
async function displayImageRecord(record: ImageRecord, listIdx: number | null = null): Promise<void> {
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

    const idx = listIdx !== null ? listIdx : state.currentIndex;
    updateMetadataPanelFromRecord(record, idx);
    updateNavDots();
  } catch (error) {
    console.error('Error displaying image:', error);
  } finally {
    state.isTransitioning = false;
  }
}

function updateMetadataPanelFromRecord(record: ImageRecord | null, _listIdx: number | null = null): void {
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

    // Update path display in status bar - show output path if accepted, else preview path
    // Use display paths (with ~ for home dir) for UI, keep absolute paths for copy
    const displayPathStr = record.outputDisplayPath || record.displayPath || '—';
    const absolutePath = record.outputPath || record.path || '';
    if (elements.pathText) {
      elements.pathText.textContent = displayPathStr;
    }
    if (elements.imagePathDisplay) {
      elements.imagePathDisplay.title = absolutePath || 'Current image path';
    }
    if (elements.copyPathBtn) {
      elements.copyPathBtn.style.display = absolutePath ? 'inline-flex' : 'none';
    }
  } else {
    metadataPrompt.textContent = '—';
    metadataModel.textContent = '—';
    metadataSeed.textContent = '—';
    metadataGeneratedSize.textContent = '—';
    metadataFinalSize.textContent = '—';
    if (elements.pathText) {
      elements.pathText.textContent = '—';
    }
    if (elements.imagePathDisplay) {
      elements.imagePathDisplay.title = 'Current image path';
    }
    if (elements.copyPathBtn) {
      elements.copyPathBtn.style.display = 'none';
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

  const total = state.imageList.length;
  const currentIdx = state.currentIndex;

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
  if (state.isTransitioning || index < 0 || index >= state.imageList.length) {
    return;
  }

  if (index === state.currentIndex) {
    return;
  }

  state.currentIndex = index;
  const entry = state.imageList[index];
  if (entry) {
    void displayImageRecord(entry, index);
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

  if (state.waitingForNext && state.imageList.length > 0) {
    state.waitingForNext = false;
    state.currentIndex = state.imageList.length - 1;
    const entry = state.imageList[state.currentIndex];
    showLoading(false);
    if (entry) {
      void displayImageRecord(entry, state.currentIndex);
    }
    return;
  }

  const navigated = ListManager.navigateToPrevious(state, (entry: ImageRecord) => {
    void displayImageRecord(entry, state.currentIndex);
  });

  if (!navigated) {
    console.log('At beginning of list, cannot go back');
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
        if (state.imageList.length > 0) {
          const entry = state.imageList[state.currentIndex];
          showLoading(false);
          if (entry) {
            void displayImageRecord(entry, state.currentIndex);
          }
        }
      });
  };

  ListManager.navigateToNext(
    state,
    (entry: ImageRecord) => {
      void displayImageRecord(entry, state.currentIndex);
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
  // Show "waiting for image" with current prompt
  if (elements.loadingLabel) {
    elements.loadingLabel.textContent = 'waiting for image';
  }
  if (elements.loadingPrompt) {
    elements.loadingPrompt.textContent = state.generationPrompt || state.prompt;
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

  ListManager.deleteCurrentImage(
    state,
    (entry: ImageRecord) => {
      void displayImageRecord(entry, state.currentIndex);
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
  if (elements.previousButton) {
    elements.previousButton.addEventListener('click', previous);
  }

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

  // Click handler for copy path button
  if (elements.copyPathBtn) {
    elements.copyPathBtn.addEventListener('click', () => {
      const idx = state.currentIndex;
      const entry = idx >= 0 && idx < state.imageList.length ? state.imageList[idx] : null;
      // Copy output path if accepted, otherwise preview path
      const path = entry?.outputPath || entry?.path;
      if (path) {
        navigator.clipboard.writeText(path).then(() => {
          // Visual feedback - temporarily change path text
          const original = elements.pathText?.textContent;
          if (elements.pathText) {
            elements.pathText.textContent = 'Copied!';
            setTimeout(() => {
              if (elements.pathText && original) {
                elements.pathText.textContent = original;
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
    } else if (e.key === 'ArrowRight') {
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
    } else if (e.key === ' ') {
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
