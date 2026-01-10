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
  prevButton: null,
  nextButton: null,
  acceptButton: null,
  deleteButton: null,
  abortButton: null,
  pauseButton: null,
  pauseIcon: null,
  pauseLabel: null,
  themeToggle: null,
  magnifierLens: null,
};

// Magnifier state
let magnifierActive = false;
const MAGNIFIER_SIZE = 200;
const MAGNIFICATION = 3;

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
  elements.prevButton = document.getElementById('prev-btn') as HTMLButtonElement | null;
  elements.nextButton = document.getElementById('next-btn') as HTMLButtonElement | null;
  elements.acceptButton = document.getElementById('accept-btn') as HTMLButtonElement | null;
  elements.deleteButton = document.getElementById('delete-btn') as HTMLButtonElement | null;
  elements.abortButton = document.getElementById('abort-btn') as HTMLButtonElement | null;
  elements.pauseButton = document.getElementById('pause-btn') as HTMLButtonElement | null;
  elements.pauseIcon = document.getElementById('pause-icon');
  elements.pauseLabel = document.getElementById('pause-label');
  elements.themeToggle = document.getElementById('theme-toggle') as HTMLButtonElement | null;
  elements.magnifierLens = document.getElementById('magnifier-lens');
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
    setupResizeObserver();

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

  // Flash the pause button when generation is paused to draw attention
  if (state.isPaused && elements.pauseButton) {
    ButtonFlash.flashButton(elements.pauseButton);
  }

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
      elements.pauseButton.classList.add('paused');
    }
  } else {
    elements.pauseIcon.textContent = '\u23F8';
    elements.pauseLabel.textContent = 'Pause';
    if (elements.pauseButton) {
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
    if (elements.copyPathBtn) {
      elements.copyPathBtn.style.display = 'none';
    }
  }
}

function clearMetadataPanel(): void {
  updateMetadataPanelFromRecord(null, null);
}

// Dimensions for nav dot layout calculation (must match CSS)
const DOT_WIDTH = 8;      // .nav-dot width
const DOT_GAP = 6;        // .nav-dots gap
const GAP_INDICATOR_WIDTH = 20; // Width of gap indicator (3 small dots + spacing)

/**
 * Calculate max number of dots that fit in given width.
 * For N dots: width = N * DOT_WIDTH + (N - 1) * DOT_GAP = N * (DOT_WIDTH + DOT_GAP) - DOT_GAP
 */
function maxDotsForWidth(width: number): number {
  if (width <= 0) return 0;
  // N * (DOT_WIDTH + DOT_GAP) - DOT_GAP <= width
  // N <= (width + DOT_GAP) / (DOT_WIDTH + DOT_GAP)
  return Math.floor((width + DOT_GAP) / (DOT_WIDTH + DOT_GAP));
}

/**
 * Update navigation dots display.
 *
 * The navigation model:
 * - Total positions = imageList.length + 1 (images + spinner)
 * - Position 0 to imageList.length-1 are images
 * - Position imageList.length is always the "loading/spinner" position
 * - Minimum 1 dot (spinner when no images)
 * - Active position: waitingForNext or no images → spinner; otherwise → currentIndex
 */
function updateNavDots(): void {
  if (!elements.navDots) {
    return;
  }

  const imageCount = state.imageList.length;
  // Total positions = images + 1 (spinner is always the last position)
  const totalPositions = imageCount + 1;

  // Determine active position
  // If waitingForNext or no images, active is the spinner (last position)
  // Otherwise, active is currentIndex
  let activePosition: number;
  if (state.waitingForNext || imageCount === 0) {
    activePosition = imageCount; // Last position = spinner
  } else {
    activePosition = state.currentIndex;
  }

  // Clear existing dots
  elements.navDots.innerHTML = '';

  // Calculate available width from parent container
  const container = elements.navDots.parentElement;
  const availableWidth = container ? container.clientWidth - 32 : 400; // 32px padding buffer
  const maxDots = maxDotsForWidth(availableWidth);

  // If all positions fit, show them all
  if (totalPositions <= maxDots) {
    for (let i = 0; i < totalPositions; i++) {
      const isSpinner = i === imageCount;
      const dot = createNavDot(i, i === activePosition, isSpinner);
      elements.navDots.appendChild(dot);
    }
    announceNavigation(activePosition, totalPositions);
    return;
  }

  // Need gap indicators - calculate how many dots we can show
  // Reserve space for up to 2 gap indicators
  const maxGapIndicators = 2;
  const widthForDots = availableWidth - (maxGapIndicators * (GAP_INDICATOR_WIDTH + DOT_GAP));
  const dotsAvailable = Math.max(3, maxDotsForWidth(widthForDots)); // At least 3 dots (first, active, last)

  // Strategy: always show first dot, last dot (spinner), and current area
  // Distribute remaining dots to edges
  const minEdgeDots = 1; // At least first and last
  const remainingDots = dotsAvailable - 2; // After reserving first and spinner
  const currentRadius = Math.max(0, Math.floor(remainingDots / 2));

  const dotsToShow: Array<number | 'gap'> = [];

  // Always add first dot (position 0) if there are images
  if (imageCount > 0) {
    dotsToShow.push(0);
  }

  // Calculate middle section around active (if not first or last)
  const middleStart = Math.max(minEdgeDots, activePosition - currentRadius);
  const middleEnd = Math.min(imageCount - 1, activePosition + currentRadius);

  // Add gap if there's a jump from first dot to middle section
  if (middleStart > minEdgeDots) {
    dotsToShow.push('gap');
  }

  // Add middle section (images around active position)
  for (let i = middleStart; i <= middleEnd; i++) {
    if (!dotsToShow.includes(i) && i < imageCount) {
      dotsToShow.push(i);
    }
  }

  // Add gap if there's a jump from middle section to spinner
  // (if active is not near the spinner position)
  if (middleEnd < imageCount - 1) {
    dotsToShow.push('gap');
  }

  // Always add spinner dot (last position)
  dotsToShow.push(imageCount);

  // Render the dots
  for (const item of dotsToShow) {
    if (item === 'gap') {
      elements.navDots.appendChild(createGapIndicator());
    } else {
      const isSpinner = item === imageCount;
      const dot = createNavDot(item, item === activePosition, isSpinner);
      elements.navDots.appendChild(dot);
    }
  }

  announceNavigation(activePosition, totalPositions);
}

/**
 * Create a gap indicator element (replaces text ellipsis).
 * Uses 3 small dots that match the nav-dot height to avoid layout shifts.
 */
function createGapIndicator(): HTMLElement {
  const gap = document.createElement('span');
  gap.className = 'nav-gap';
  gap.setAttribute('aria-hidden', 'true');

  // Create 3 small dots
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement('span');
    dot.className = 'nav-gap-dot';
    gap.appendChild(dot);
  }

  return gap;
}

/**
 * Announce navigation change for screen readers.
 */
function announceNavigation(activePosition: number, totalPositions: number): void {
  const navIndicator = elements.navIndicator;
  if (!navIndicator) return;

  const imageCount = totalPositions - 1;
  let announcement: string;

  if (activePosition === imageCount) {
    // Spinner position
    if (imageCount === 0) {
      announcement = 'Waiting for first image';
    } else {
      announcement = `Waiting for next image, ${imageCount} image${imageCount !== 1 ? 's' : ''} available`;
    }
  } else {
    announcement = `Image ${activePosition + 1} of ${imageCount}`;
  }

  // Update aria-label for the nav indicator
  navIndicator.setAttribute('aria-label', announcement);
}

function createNavDot(index: number, isActive: boolean, isSpinner: boolean): HTMLElement {
  const dot = document.createElement('span');
  dot.className = 'nav-dot';
  if (isActive) {
    dot.classList.add('active');
  }
  if (isSpinner) {
    dot.classList.add('spinner-dot');
  }
  dot.setAttribute('role', 'button');

  // Set appropriate aria-label
  if (isSpinner) {
    dot.setAttribute('aria-label', 'Go to loading screen');
  } else {
    dot.setAttribute('aria-label', `Go to image ${index + 1}`);
  }
  dot.setAttribute('tabindex', '0');

  // Click handler to navigate
  dot.addEventListener('click', () => {
    navigateToIndex(index, isSpinner);
  });

  // Keyboard handler
  dot.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      navigateToIndex(index, isSpinner);
    }
  });

  return dot;
}

function navigateToIndex(index: number, isSpinner = false): void {
  if (state.isTransitioning) {
    return;
  }

  // Handle spinner dot click - show loading placeholder
  if (isSpinner) {
    if (state.waitingForNext) {
      return; // Already on spinner
    }
    state.waitingForNext = true;
    showLoadingPlaceholder();
    return;
  }

  // Handle image dot click
  if (index < 0 || index >= state.imageList.length) {
    return;
  }

  if (index === state.currentIndex && !state.waitingForNext) {
    return; // Already on this image
  }

  // If coming from spinner, clear waitingForNext
  if (state.waitingForNext) {
    state.waitingForNext = false;
  }

  state.currentIndex = index;
  const entry = state.imageList[index];
  if (entry) {
    showLoading(false);
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

// Magnifier functions
function isMagnifierActive(): boolean {
  return magnifierActive;
}

function toggleMagnifier(): void {
  if (!elements.magnifierLens || !elements.currentImage) {
    return;
  }

  // Don't toggle if no image is displayed
  if (!elements.currentImage.src || elements.currentImage.classList.contains('hidden')) {
    return;
  }

  magnifierActive = !magnifierActive;

  if (!magnifierActive) {
    elements.magnifierLens.classList.add('hidden');
  }
}

function updateMagnifierPosition(e: MouseEvent): void {
  if (!magnifierActive || !elements.magnifierLens || !elements.currentImage || !elements.imageContainer) {
    return;
  }

  // Get image and container bounds
  const imgRect = elements.currentImage.getBoundingClientRect();
  const containerRect = elements.imageContainer.getBoundingClientRect();

  // Calculate cursor position relative to the image
  const mouseX = e.clientX - imgRect.left;
  const mouseY = e.clientY - imgRect.top;

  // Check if cursor is within image bounds
  if (mouseX < 0 || mouseX > imgRect.width || mouseY < 0 || mouseY > imgRect.height) {
    elements.magnifierLens.classList.add('hidden');
    return;
  }

  // Show magnifier
  elements.magnifierLens.classList.remove('hidden');

  // Calculate lens position relative to container (centered on cursor)
  const lensRadius = MAGNIFIER_SIZE / 2;
  const lensX = (e.clientX - containerRect.left) - lensRadius;
  const lensY = (e.clientY - containerRect.top) - lensRadius;

  // Position the lens
  elements.magnifierLens.style.left = `${lensX}px`;
  elements.magnifierLens.style.top = `${lensY}px`;

  // Set background image to current image
  elements.magnifierLens.style.backgroundImage = `url(${elements.currentImage.src})`;

  // Calculate the magnified background position
  // The background should be scaled by MAGNIFICATION and positioned so the point
  // under the cursor appears at the center of the lens
  const bgWidth = imgRect.width * MAGNIFICATION;
  const bgHeight = imgRect.height * MAGNIFICATION;

  // Position the background so the cursor point is centered in the lens
  const bgX = (mouseX / imgRect.width) * bgWidth - lensRadius;
  const bgY = (mouseY / imgRect.height) * bgHeight - lensRadius;

  elements.magnifierLens.style.backgroundSize = `${bgWidth}px ${bgHeight}px`;
  elements.magnifierLens.style.backgroundPosition = `-${bgX}px -${bgY}px`;
}

function hideMagnifier(): void {
  if (!elements.magnifierLens) {
    return;
  }
  elements.magnifierLens.classList.add('hidden');
}

function deactivateMagnifier(): void {
  magnifierActive = false;
  hideMagnifier();
}

function visualSuccessFeedback(): void {
  if (elements.imageContainer) {
    (elements.imageContainer as HTMLElement).style.boxShadow = '0 0 20px rgba(34, 197, 94, 0.5)';
  }
}

function prev(): void {
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
    updateNavDots();
    return;
  }

  const navigated = ListManager.navigateToPrev(state, (entry: ImageRecord) => {
    void displayImageRecord(entry, state.currentIndex);
  });

  if (!navigated) {
    console.log('At beginning of list, cannot go back');
  }
}

function next(): void {
  if (state.isTransitioning) {
    return;
  }

  if (state.waitingForNext) {
    console.log('Already waiting for next image');
    return;
  }

  const requestNextImage = () => {
    state.waitingForNext = true;
    showLoadingPlaceholder();

    state.actionQueue = state.actionQueue
      .then(async () => {
        await invoke('skip_image');
      })
      .catch(err => {
        console.error('Next failed:', err);
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
    requestNextImage
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
      updateNavDots();
    },
    () => {
      // When last image is deleted, show spinner screen
      state.waitingForNext = true;
      showLoadingPlaceholder();
    }
  );
}

function enableAcceptButton(): void {
  if (elements.acceptButton) {
    elements.acceptButton.disabled = false;
  }
}

function setupButtonListeners(): void {
  if (elements.prevButton) {
    elements.prevButton.addEventListener('click', prev);
  }

  if (elements.nextButton) {
    elements.nextButton.addEventListener('click', next);
  }

  if (elements.acceptButton) {
    elements.acceptButton.addEventListener('click', accept);
  }

  if (elements.deleteButton) {
    elements.deleteButton.addEventListener('click', deleteCurrentImage);
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

  // Click handler for magnifier toggle
  if (elements.currentImage) {
    elements.currentImage.addEventListener('click', toggleMagnifier);
  }

  // Mouse move handler for magnifier
  if (elements.imageContainer) {
    elements.imageContainer.addEventListener('mousemove', updateMagnifierPosition);
    elements.imageContainer.addEventListener('mouseleave', hideMagnifier);
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
      prev();
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      next();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      accept();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      // Deactivate magnifier if active, otherwise abort
      if (isMagnifierActive()) {
        deactivateMagnifier();
      } else {
        abort();
      }
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && ctrlOrCmd) {
      e.preventDefault();
      deleteCurrentImage();
    } else if (e.key === ' ') {
      e.preventDefault();
      togglePause();
    }
  });
}

function setupResizeObserver(): void {
  if (!elements.navIndicator) return;

  const resizeObserver = new ResizeObserver(() => {
    // Always update dots (we always have at least the spinner dot)
    updateNavDots();
  });

  resizeObserver.observe(elements.navIndicator);
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
      prev: typeof prev;
      next: typeof next;
      accept: typeof accept;
      abort: typeof abort;
      togglePause: typeof togglePause;
      updatePauseButton: typeof updatePauseButton;
      deleteCurrentImage: typeof deleteCurrentImage;
      cacheElements: typeof cacheElements;
      allElementsPresent: typeof allElementsPresent;
      isMagnifierActive: typeof isMagnifierActive;
      toggleMagnifier: typeof toggleMagnifier;
      deactivateMagnifier: typeof deactivateMagnifier;
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
    prev,
    next,
    accept,
    abort,
    togglePause,
    updatePauseButton,
    deleteCurrentImage,
    cacheElements,
    allElementsPresent,
    isMagnifierActive,
    toggleMagnifier,
    deactivateMagnifier,
  };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => void init());
} else {
  void init();
}
