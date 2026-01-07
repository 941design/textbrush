// Textbrush UI Application Logic
// Handles image review workflow, state management, and user interactions via Tauri IPC

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
  isTransitioning: false,
  prompt: '',
  actionQueue: Promise.resolve(),
  currentBlobUrl: null,
};

// DOM Element References
const elements = {
  app: null,
  viewer: null,
  imageContainer: null,
  currentImage: null,
  loadingOverlay: null,
  loadingSpinner: null,
  loadingText: null,
  statusBar: null,
  promptDisplay: null,
  bufferIndicator: null,
  bufferDots: null,
  bufferText: null,
  seedDisplay: null,
  controls: null,
  skipButton: null,
  acceptButton: null,
  abortButton: null,
};

function cacheElements() {
  elements.app = document.getElementById('app');
  elements.viewer = document.querySelector('.viewer');
  elements.imageContainer = document.querySelector('.image-container');
  elements.currentImage = document.querySelector('.current-image');
  elements.loadingOverlay = document.getElementById('loading-overlay');
  elements.loadingSpinner = document.querySelector('.spinner');
  elements.loadingText = document.querySelector('.loading-text');
  elements.statusBar = document.querySelector('.status-bar');
  elements.promptDisplay = document.getElementById('prompt-display');
  elements.bufferIndicator = document.getElementById('buffer-indicator');
  elements.bufferDots = document.getElementById('buffer-dots');
  elements.bufferText = document.getElementById('buffer-text');
  elements.seedDisplay = document.getElementById('seed-display');
  elements.controls = document.querySelector('.controls');
  elements.skipButton = document.getElementById('skip-btn');
  elements.acceptButton = document.getElementById('accept-btn');
  elements.abortButton = document.getElementById('abort-btn');
}

function allElementsPresent() {
  return Object.values(elements).every(el => el !== null);
}

// Initialize Application
async function init() {
  console.log('Textbrush UI initializing...');
  try {
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
    state.bufferMax = launchArgs.buffer_max || 8;

    // Display the prompt
    if (elements.promptDisplay) {
      elements.promptDisplay.textContent = `Prompt: ${state.prompt}`;
    }

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
    if (elements.loadingText) {
      elements.loadingText.textContent = `Error: ${error.message}`;
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

function handleAccepted(payload) {
  const path = payload.path || 'unknown';
  visualSuccessFeedback();
  setTimeout(async () => {
    try {
      await invoke('print_and_exit', { path });
    } catch (err) {
      console.error('Failed to call print_and_exit:', err);
      appWindow.close();
    }
  }, 500);
}

function handleAborted(payload) {
  setTimeout(async () => {
    try {
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

// Display Image with Transitions
async function displayImage(payload) {
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

    // Revoke previous blob URL to prevent memory leak
    if (state.currentBlobUrl) {
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
      console.log('Setting image src to blob URL:', state.currentBlobUrl);
      elements.currentImage.src = state.currentBlobUrl;
    } else {
      console.warn('Cannot display image - missing element or data:', {
        hasElement: !!elements.currentImage,
        hasData: !!payload.image_data
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

  // Show/hide loading overlay based on buffer
  showLoading(state.bufferCount === 0);
}

// Show/Hide Loading Overlay
function showLoading(show) {
  if (!elements.loadingOverlay) {
    return;
  }

  if (show) {
    elements.loadingOverlay.classList.remove('hidden');
  } else {
    elements.loadingOverlay.classList.add('hidden');
  }
}

// Visual Feedback for Accept
function visualSuccessFeedback() {
  if (elements.imageContainer) {
    elements.imageContainer.style.boxShadow = '0 0 20px rgba(34, 197, 94, 0.5)';
  }
}

// Action Functions
function skip() {
  if (state.isTransitioning) {
    return;
  }

  // Queue skip action to prevent race conditions
  state.actionQueue = state.actionQueue
    .then(async () => {
      await invoke('skip_image');
    })
    .catch(err => {
      console.error('Skip failed:', err);
    });
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
}

// Keyboard Event Listener
function setupKeyboardListeners() {
  document.addEventListener('keydown', (e) => {
    // Space or Right Arrow = skip
    if (e.key === ' ' || e.key === 'ArrowRight') {
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
    skip,
    accept,
    abort,
    cacheElements,
    allElementsPresent,
  };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
