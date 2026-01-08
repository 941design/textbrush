// Textbrush UI Application Logic
// Handles image review workflow, state management, and user interactions via Tauri IPC

import * as ConfigControls from './config_controls.js';
import * as ThemeManager from './theme-manager.js';
import * as HistoryManager from './history-manager.js';
import * as ButtonFlash from './button-flash.js';

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { appWindow } = window.__TAURI__.window;

// State Management
const state = {
  currentImage: null,
  currentSeed: null,
  bufferCount: 0,
  bufferMax: 8,
  isGenerating: false,
  isPaused: false,
  isTransitioning: false,
  prompt: '',
  aspectRatio: '1:1',
  actionQueue: Promise.resolve(),
  currentBlobUrl: null,
  // Navigation history
  imageHistory: [],       // Array of {image_data, seed, blobUrl}
  historyIndex: -1,       // Current position in history (-1 = none)
  waitingForNext: false,  // True when at loading placeholder
};

// DOM Element References
const elements = {
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
  validationError: null,
  bufferIndicator: null,
  bufferDots: null,
  bufferText: null,
  seedDisplay: null,
  controls: null,
  skipButton: null,
  acceptButton: null,
  abortButton: null,
  pauseButton: null,
  pauseIcon: null,
  pauseLabel: null,
  themeToggle: null,
};

function cacheElements() {
  elements.app = document.getElementById('app');
  elements.viewer = document.querySelector('.viewer');
  elements.imageContainer = document.querySelector('.image-container');
  elements.currentImage = document.querySelector('.current-image');
  elements.loadingOverlay = document.getElementById('loading-overlay');
  elements.loadingSpinner = document.querySelector('.spinner');
  elements.loadingPrompt = document.getElementById('loading-prompt');
  elements.statusBar = document.querySelector('.status-bar');
  elements.promptDisplay = document.getElementById('prompt-display');
  elements.promptInput = document.getElementById('prompt-input');
  elements.aspectRatioRadios = document.querySelectorAll('input[name="aspect-ratio"]');
  elements.validationError = document.getElementById('validation-error');
  elements.bufferIndicator = document.getElementById('buffer-indicator');
  elements.bufferDots = document.getElementById('buffer-dots');
  elements.bufferText = document.getElementById('buffer-text');
  elements.seedDisplay = document.getElementById('seed-display');
  elements.controls = document.querySelector('.controls');
  elements.skipButton = document.getElementById('skip-btn');
  elements.acceptButton = document.getElementById('accept-btn');
  elements.abortButton = document.getElementById('abort-btn');
  elements.pauseButton = document.getElementById('pause-btn');
  elements.pauseIcon = document.getElementById('pause-icon');
  elements.pauseLabel = document.getElementById('pause-label');
  elements.themeToggle = document.getElementById('theme-toggle');
}

function allElementsPresent() {
  return Object.values(elements).every(el => el !== null);
}

// Initialize Application
async function init() {
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
    const launchArgs = await invoke('get_launch_args');
    console.log('Launch args received:', launchArgs);
    state.prompt = launchArgs.prompt || '';
    state.aspectRatio = launchArgs.aspect_ratio || '1:1';
    state.bufferMax = launchArgs.buffer_max || 8;

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
      elements.loadingPrompt.textContent = `Error: ${error.message}`;
    }
  }
}

// Message Event Listener
function setupMessageListener() {
  console.log('Setting up sidecar message listener...');
  listen('sidecar-message', (event) => {
    const msg = event.payload;
    console.log('Received sidecar message:', msg.type, msg);
    handleMessage(msg);
  }).catch(err => {
    console.error('Failed to setup message listener:', err);
  });
}

// Message Handler with Type Dispatch
function handleMessage(msg) {
  if (!msg || !msg.type) {
    console.warn('Invalid message format:', msg);
    return;
  }

  switch (msg.type) {
    case 'ready':
      handleReady(msg.payload || {});
      break;

    case 'image_ready':
      handleImageReady(msg.payload || {});
      break;

    case 'buffer_status':
      handleBufferStatus(msg.payload || {});
      break;

    case 'accepted':
      handleAccepted(msg.payload || {});
      break;

    case 'aborted':
      handleAborted(msg.payload || {});
      break;

    case 'error':
      handleError(msg.payload || {});
      break;

    case 'paused':
      handlePaused(msg.payload || {});
      break;

    default:
      console.warn('Unknown message type:', msg.type);
  }
}

// Message Handlers
function handleReady(payload) {
  state.isGenerating = true;
  state.bufferCount = payload.buffer_count || 0;
  updateBufferDisplay();
}

function handleImageReady(payload) {
  state.currentImage = payload;
  state.currentSeed = payload.seed || null;
  state.bufferCount = payload.buffer_count || 0;
  state.bufferMax = payload.buffer_max || 8;

  // Add new image to history
  state.imageHistory.push({
    image_data: payload.image_data,
    seed: payload.seed,
    blobUrl: null,  // Will be set when displayed
  });
  state.historyIndex = state.imageHistory.length - 1;
  state.waitingForNext = false;

  displayImage(payload);
  updateBufferDisplay();
  // Always hide loading overlay when we have an image to display
  showLoading(false);
  enableAcceptButton();
}

function handleBufferStatus(payload) {
  state.bufferCount = payload.count || 0;
  state.isGenerating = payload.generating || false;
  updateBufferDisplay();
}

async function handleAccepted(payload) {
  // Payload contains path for the single image that was just accepted via backend
  // Store this path in current history entry if it was the current image
  if (payload.path && state.historyIndex >= 0 && state.historyIndex < state.imageHistory.length) {
    state.imageHistory[state.historyIndex].path = payload.path;
  }

  // Collect all paths from history (including the one just saved)
  const allPaths = HistoryManager.getAllRetainedPaths(state);

  visualSuccessFeedback();
  setTimeout(async () => {
    try {
      // Clean up all blob URLs before exit
      for (const entry of state.imageHistory) {
        if (entry.blobUrl) {
          URL.revokeObjectURL(entry.blobUrl);
        }
      }

      if (allPaths.length === 0) {
        // No images retained - exit as abort
        await invoke('abort_exit');
      } else if (allPaths.length === 1) {
        // Single path - use backward-compatible single-path exit
        await invoke('print_and_exit', { path: allPaths[0] });
      } else {
        // Multiple paths - use multi-path exit
        await invoke('print_paths_and_exit', { paths: allPaths });
      }
    } catch (err) {
      console.error('Failed to call exit handler:', err);
      appWindow.close();
    }
  }, 500);
}

function handleAborted(payload) {
  setTimeout(async () => {
    try {
      // Clean up all blob URLs before exit
      for (const entry of state.imageHistory) {
        if (entry.blobUrl) {
          URL.revokeObjectURL(entry.blobUrl);
        }
      }

      await invoke('abort_exit');
    } catch (err) {
      console.error('Failed to call abort_exit:', err);
      appWindow.close();
    }
  }, 500);
}

function handleError(payload) {
  const message = payload.message || 'Unknown error';
  const fatal = payload.fatal || false;

  console.error('Backend error:', message, 'fatal:', fatal);

  if (fatal) {
    setTimeout(() => {
      appWindow.close();
    }, 2000);
  }
}

function handlePaused(payload) {
  state.isPaused = payload.paused || false;
  updatePauseButton();
  console.log('Generation', state.isPaused ? 'paused' : 'resumed');
}

// Update Pause Button UI
function updatePauseButton() {
  if (!elements.pauseIcon || !elements.pauseLabel) {
    return;
  }

  if (state.isPaused) {
    elements.pauseIcon.textContent = '\u25B6';  // Play symbol
    elements.pauseLabel.textContent = 'Resume';
    if (elements.pauseButton) {
      elements.pauseButton.title = 'Resume image generation (P)';
      elements.pauseButton.classList.add('paused');
    }
  } else {
    elements.pauseIcon.textContent = '\u23F8';  // Pause symbol
    elements.pauseLabel.textContent = 'Pause';
    if (elements.pauseButton) {
      elements.pauseButton.title = 'Pause image generation (P)';
      elements.pauseButton.classList.remove('paused');
    }
  }
}

// Display Image with Transitions
async function displayImage(payload, historyIdx = null) {
  console.log('displayImage called, seed:', payload.seed, 'data length:', payload.image_data?.length);
  if (state.isTransitioning) {
    console.log('Skipping - already transitioning');
    return;
  }

  state.isTransitioning = true;

  try {
    // Skip animations when buffer has multiple images (performance optimization)
    const skipAnimations = state.bufferCount > 1;
    const fadeOutDuration = skipAnimations ? 0 : 100;
    const fadeInDuration = skipAnimations ? 0 : 200;

    // Fade out current image
    if (elements.currentImage && elements.currentImage.src) {
      if (!skipAnimations) {
        elements.currentImage.classList.add('image-exit');
      }
      await new Promise(resolve => setTimeout(resolve, fadeOutDuration));
    }

    // Revoke previous blob URL to prevent memory leak (only if not in history)
    if (state.currentBlobUrl && !isHistoryBlobUrl(state.currentBlobUrl)) {
      URL.revokeObjectURL(state.currentBlobUrl);
      state.currentBlobUrl = null;
    }

    // Update image source using blob URL
    if (elements.currentImage && payload.image_data) {
      console.log('Creating blob from base64 data...');
      const binaryString = atob(payload.image_data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: 'image/png' });
      state.currentBlobUrl = URL.createObjectURL(blob);

      // Store blob URL in history if we have a valid history index
      const idx = historyIdx !== null ? historyIdx : state.historyIndex;
      if (idx >= 0 && idx < state.imageHistory.length) {
        state.imageHistory[idx].blobUrl = state.currentBlobUrl;
      }

      console.log('Setting image src to blob URL:', state.currentBlobUrl);
      elements.currentImage.src = state.currentBlobUrl;
    } else if (elements.currentImage && payload.blobUrl) {
      // Use existing blob URL from history
      console.log('Using existing blob URL from history:', payload.blobUrl);
      state.currentBlobUrl = payload.blobUrl;
      elements.currentImage.src = payload.blobUrl;
    } else {
      console.warn('Cannot display image - missing element or data:', {
        hasElement: !!elements.currentImage,
        hasData: !!payload.image_data,
        hasBlobUrl: !!payload.blobUrl
      });
    }

    // Fade in new image
    if (elements.currentImage) {
      elements.currentImage.classList.remove('image-exit');
      if (!skipAnimations) {
        elements.currentImage.classList.add('image-enter');
      }
      await new Promise(resolve => setTimeout(resolve, fadeInDuration));
      elements.currentImage.classList.remove('image-enter');
    }

    // Update seed display
    if (elements.seedDisplay && payload.seed !== undefined) {
      elements.seedDisplay.textContent = `Seed: ${payload.seed}`;
    }
  } catch (error) {
    console.error('Error displaying image:', error);
  } finally {
    state.isTransitioning = false;
  }
}

// Check if a blob URL is stored in history (should not be revoked)
function isHistoryBlobUrl(blobUrl) {
  return state.imageHistory.some(item => item.blobUrl === blobUrl);
}

// Update Buffer Display
function updateBufferDisplay() {
  if (!elements.bufferDots) {
    return;
  }

  // Update existing buffer dots
  const dots = elements.bufferDots.querySelectorAll('.buffer-dot');
  for (let i = 0; i < dots.length; i++) {
    if (i < state.bufferCount) {
      dots[i].classList.add('filled');
    } else {
      dots[i].classList.remove('filled');
    }
  }

  // Update buffer text
  if (elements.bufferText) {
    elements.bufferText.textContent = `${state.bufferCount}/${state.bufferMax}`;
  }

  // Only show loading if we're waiting for next AND buffer is empty
  // Don't auto-show loading when browsing history
  if (state.waitingForNext && state.bufferCount === 0) {
    showLoading(true);
  }
}

// Show/Hide Loading Overlay
function showLoading(show) {
  if (!elements.loadingOverlay) {
    return;
  }

  if (show) {
    elements.loadingOverlay.classList.remove('hidden');
    // Hide current image when showing loading placeholder
    if (elements.currentImage) {
      elements.currentImage.classList.add('hidden');
    }
  } else {
    elements.loadingOverlay.classList.add('hidden');
    // Show current image when hiding loading
    if (elements.currentImage) {
      elements.currentImage.classList.remove('hidden');
    }
  }
}

// Visual Feedback for Accept
function visualSuccessFeedback() {
  if (elements.imageContainer) {
    elements.imageContainer.style.boxShadow = '0 0 20px rgba(34, 197, 94, 0.5)';
  }
}

// Action Functions

// Navigate to previous image in history (ArrowLeft)
function previous() {
  if (state.isTransitioning) {
    return;
  }

  // If we're at the loading placeholder, go back to the last image
  if (state.waitingForNext && state.imageHistory.length > 0) {
    state.waitingForNext = false;
    state.historyIndex = state.imageHistory.length - 1;
    const historyItem = state.imageHistory[state.historyIndex];
    showLoading(false);
    displayImage(historyItem, state.historyIndex);
    updateSeedDisplay(historyItem.seed);
    return;
  }

  // Use HistoryManager for navigation
  const navigated = HistoryManager.navigateToPrevious(state, (entry) => {
    displayImage(entry, state.historyIndex);
    updateSeedDisplay(entry.seed);
  });

  if (!navigated) {
    console.log('At beginning of history, cannot go back');
  }
}

// Navigate to next image (ArrowRight or Space)
function skip() {
  if (state.isTransitioning) {
    return;
  }

  // If already waiting for next image, do nothing
  if (state.waitingForNext) {
    console.log('Already waiting for next image');
    return;
  }

  // Use HistoryManager for navigation - handles both history forward and buffer request
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
          displayImage(historyItem, state.historyIndex);
        }
      });
  };

  HistoryManager.navigateToNext(
    state,
    (entry) => {
      displayImage(entry, state.historyIndex);
      updateSeedDisplay(entry.seed);
    },
    requestNext
  );
}

// Show loading placeholder (hide current image, show spinner as new view)
function showLoadingPlaceholder() {
  if (elements.currentImage) {
    elements.currentImage.classList.add('hidden');
  }
  if (elements.loadingOverlay) {
    elements.loadingOverlay.classList.remove('hidden');
  }
  if (elements.seedDisplay) {
    elements.seedDisplay.textContent = 'Seed: —';
  }
}

// Update seed display helper
function updateSeedDisplay(seed) {
  if (elements.seedDisplay) {
    elements.seedDisplay.textContent = seed !== undefined ? `Seed: ${seed}` : 'Seed: —';
  }
}

function accept() {
  if (elements.acceptButton && !state.isTransitioning) {
    elements.acceptButton.disabled = true;
    invoke('accept_image').catch(err => {
      console.error('Accept failed:', err);
      elements.acceptButton.disabled = false;
    });
  }
}

function abort() {
  if (state.isTransitioning) {
    return;
  }

  invoke('abort_generation').catch(err => {
    console.error('Abort failed:', err);
  });
}

function togglePause() {
  invoke('pause_generation').catch(err => {
    console.error('Pause toggle failed:', err);
  });
}

// Delete current image from history
function deleteCurrentImage() {
  if (state.isTransitioning) {
    return;
  }

  HistoryManager.deleteCurrentImage(
    state,
    (entry) => {
      displayImage(entry, state.historyIndex);
      updateSeedDisplay(entry.seed);
    },
    () => {
      // Show empty state - hide image, show loading without spinner
      if (elements.currentImage) {
        elements.currentImage.classList.add('hidden');
      }
      if (elements.seedDisplay) {
        elements.seedDisplay.textContent = 'Seed: —';
      }
    }
  );
}

// Enable/Disable Accept Button
function enableAcceptButton() {
  if (elements.acceptButton) {
    elements.acceptButton.disabled = false;
  }
}

// Button Event Listeners
function setupButtonListeners() {
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

// Keyboard Event Listener
function setupKeyboardListeners() {
  document.addEventListener('keydown', (e) => {
    // Ignore keyboard shortcuts when user is typing in input field
    if (e.target.tagName === 'INPUT' && e.target.type === 'text') {
      return;
    }

    // Flash button for visual feedback
    const ctrlOrCmd = e.ctrlKey || e.metaKey;
    ButtonFlash.flashButtonForKey(e.key, ctrlOrCmd);

    // Left Arrow = previous
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      previous();
    }
    // Space or Right Arrow = skip/next
    else if (e.key === ' ' || e.key === 'ArrowRight') {
      e.preventDefault();
      skip();
    }
    // Enter = accept
    else if (e.key === 'Enter') {
      e.preventDefault();
      accept();
    }
    // Escape = abort
    else if (e.key === 'Escape') {
      e.preventDefault();
      abort();
    }
    // Cmd/Ctrl+Delete or Cmd/Ctrl+Backspace = delete current image
    else if ((e.key === 'Delete' || e.key === 'Backspace') && ctrlOrCmd) {
      e.preventDefault();
      deleteCurrentImage();
    }
    // P = toggle pause
    else if (e.key === 'p' || e.key === 'P') {
      e.preventDefault();
      togglePause();
    }
  });
}

// Expose for testing
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
    updateSeedDisplay,
  };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
