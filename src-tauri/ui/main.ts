// Textbrush UI Application Logic
// Handles image review workflow, state management, and user interactions via Tauri IPC

import * as ConfigControls from './config_controls';
import * as ThemeManager from './theme-manager';
import * as FontSizeManager from './font-size-manager';
import * as ListManager from './list-manager';
import * as ButtonFlash from './button-flash';
import { invoke, convertFileSrc } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { fetchAndParsePngMetadata } from './png-metadata';
import {
  applyPickedPaths, removeReference, replaceReference, previewLabel,
  isEditingModel, compatibilityMessage, adoptModelCapabilities,
  maxReferencesFor, modelCapability,
} from './reference_picker';
import type {
  AppState,
  Elements,
  LaunchArgs,
  SidecarMessage,
  ImagePayload,
  ImageListPayload,
  StateChangedPayload,
  AcceptedPayload,
  DeleteAckPayload,
  ErrorPayload,
  ConfigAckPayload,
  ModelListPayload,
  ImageRecord,
} from './types';

// Get current window reference
const appWindow = getCurrentWindow();

// State Management
const state: AppState = {
  currentImage: null,
  backendState: null,  // null until first state_changed(loading) event arrives from backend
  isPaused: false,  // DEPRECATED - kept for compatibility, use backendState.state === "paused"
  isTransitioning: false,
  acceptInFlight: false,
  prompt: '',
  generationPrompt: '',
  aspectRatio: '1:1',
  width: 1024,
  height: 1024,
  outputPath: null,
  actionQueue: Promise.resolve(),
  currentBlobUrl: null,
  imageList: [],
  currentIndex: -1,
  modelId: null,
  pendingModelId: null,
  references: [],
  pendingReferences: null,
  preset: null,
  settled: false,
  compatibility: null,
  configUpdateInFlight: false,
  deferredConfigChange: null,
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
  modelSelector: null,
  modelRadios: null,
  referencePicker: null,
  referenceAdd: null,
  referenceList: null,
  referenceError: null,
  outputSize: null,
  referenceLegend: null,
};

// Magnifier state
let magnifierActive = false;
const MAGNIFIER_SIZE = 200;
const MAGNIFICATION = 3;
let imageReadyQueue: Promise<void> = Promise.resolve();
let pendingDisplayRequest: { record: ImageRecord; listIdx: number | null } | null = null;

// Recovery guard: prevent duplicate get_image_list invocations per session
let recoveryAttempted = false;
let initPromise: Promise<void> | null = null;
let messageUnlisten: UnlistenFn | null = null;
let buttonListenersInitialized = false;
let keyboardListenersInitialized = false;
let pauseCommandInFlight = false;
let desiredPausedState: boolean | null = null;
// Set when a deferred configuration change paused a running worker; the
// acknowledging config_ack resumes generation and clears it.
let resumeAfterConfigAck = false;
let abortExitScheduled = false;

function isBackendStatePaused(stateValue: string): boolean | null {
  if (stateValue === 'paused') {
    return true;
  }
  if (stateValue === 'idle' || stateValue === 'generating') {
    return false;
  }
  return null;
}

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
  elements.modelSelector = document.getElementById('model-selector') as HTMLFieldSetElement | null;
  elements.modelRadios = document.querySelectorAll('input[name="model"]');
  elements.referencePicker = document.getElementById('reference-picker');
  elements.referenceAdd = document.getElementById('reference-add') as HTMLButtonElement | null;
  elements.referenceList = document.getElementById('reference-list') as HTMLUListElement | null;
  elements.referenceError = document.getElementById('reference-error');
  elements.outputSize = document.getElementById('output-size') as HTMLFieldSetElement | null;
  elements.referenceLegend = document.getElementById('reference-legend');
}

function allElementsPresent(): boolean {
  return Object.values(elements).every(el => el !== null);
}

// Initialize Application
async function init(): Promise<void> {
  if (initPromise) {
    return initPromise;
  }

  initPromise = (async () => {
    console.log('Textbrush UI initializing...');
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
      elements,
      claimOutputSizeChange
    );

    if (elements.loadingPrompt) elements.loadingPrompt.textContent = '';

    // Setup event listeners
    await setupMessageListener();
    setupButtonListeners();
    setupKeyboardListeners();
    setupEditingControls();
    renderEditingControls();
    updatePauseButton();

    // Initialize image generation
    await invoke('init_generation', {
      prompt: state.prompt,
      outputPath: launchArgs.output_path || null,
      seed: launchArgs.seed ?? null,
      aspectRatio: launchArgs.aspect_ratio || '1:1',
      width: launchArgs.width,
      height: launchArgs.height,
      modelId: launchArgs.model_id ?? null,
      references: launchArgs.references ?? null,
      preset: launchArgs.preset ?? null,
      bufferMax: launchArgs.buffer_max ?? null,
    });

    console.log('Application initialized successfully');
  })().catch((error: unknown) => {
    initPromise = null;
    console.error('Initialization failed:', error);
    if (elements.loadingPrompt) {
      showLoading(true);
      elements.loadingPrompt.textContent = `Error: ${error instanceof Error ? error.message : String(error)}`;
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Retry initialization';
      retry.addEventListener('click', () => {
        retry.disabled = true;
        void init();
      }, { once: true });
      elements.loadingPrompt.append(retry);
    }
  });

  return initPromise;
}

// Message Event Listener
async function setupMessageListener(): Promise<void> {
  if (messageUnlisten) return;

  // INIT can emit immediately; subscription must be acknowledged first.
  messageUnlisten = await listen<SidecarMessage>('sidecar-message', (event) => {
    handleMessage(event.payload);
  });
  window.addEventListener('pagehide', () => {
    messageUnlisten?.();
    messageUnlisten = null;
  }, { once: true });
}

function activeReferencePaths(): string[] {
  return state.pendingReferences ?? state.references;
}

/** True while no model has been selected, so nothing is loading. */
function isAwaitingModel(): boolean {
  return state.backendState?.state === 'awaiting_model';
}

/** True while the worker is running (between or during generations). */
function isWorkerRunning(): boolean {
  const current = state.backendState?.state;
  return current === 'idle' || current === 'generating';
}

/** True after a pause was requested but before the worker reported quiescence. */
function isWorkerPausing(): boolean {
  return state.backendState?.state === 'paused' && !state.settled;
}

/**
 * True when a model, reference, or canvas change may be requested now.
 *
 * The backend only applies such a change to a settled worker, but the
 * user does not have to arrange that by hand: while the worker is
 * running (or still coming to rest after a pause) the request is
 * deferred -- the UI pauses the worker, sends the change once it has
 * settled, and resumes if generation was running when the user asked.
 * What stays shut is a model load in progress (`loading`), a change
 * already in flight, and one already waiting its turn.
 */
function canRequestEditingChange(): boolean {
  if (state.configUpdateInFlight || state.deferredConfigChange) return false;
  return state.settled || isAwaitingModel() || isWorkerRunning() || isWorkerPausing();
}

function renderEditingControls(): void {
  const editable = canRequestEditingChange();
  const selectable = editable;
  elements.modelRadios?.forEach(radio => {
    // Backend truth only: a click does not check the radio, the
    // acknowledgement does (FR9, no optimistic updates). While a
    // selection is in flight the viewer names the model being loaded.
    radio.checked = radio.value === state.modelId;
    radio.disabled = !selectable;
    const label = radio.closest('label');
    label?.querySelector('.recommended-badge')?.remove();
    if (label && radio.value === state.compatibility?.requiredModel) {
      const badge = document.createElement('span');
      badge.className = 'recommended-badge';
      badge.textContent = ' recommended';
      label.append(badge);
    }
    // Availability only. What a model does with reference images is the
    // reference group's own business -- stating it again per model line
    // made the selector a wall of text for a fact one control already
    // carries.
    const capability = modelCapability(radio.value);
    const note = label?.querySelector('.model-note');
    if (note) {
      note.textContent = capability?.available === false ? 'not installed' : '';
    }
    label?.classList.toggle('model-unavailable', capability?.available === false);
  });

  // The output-size group is the same group for every model, so it is
  // never hidden -- only the prompt waits for a settled worker.
  const promptEditable = state.settled && !state.configUpdateInFlight;
  if (elements.promptInput) elements.promptInput.disabled = !promptEditable && !isAwaitingModel();

  // A model that takes references sizes its output through the
  // acknowledged-configuration seam (its references must be re-decoded
  // onto the new canvas). A change requested while the worker runs is
  // deferred like a model change; the group is shut only while a change
  // is in flight or waiting, so a click cannot move the controls while
  // the backend keeps generating at the old canvas.
  const sizeLocked = isEditingModel(state.modelId) && !editable;
  elements.aspectRatioRadios?.forEach(radio => {
    radio.disabled = sizeLocked;
  });
  if (elements.resolutionDecrease) elements.resolutionDecrease.disabled ||= sizeLocked;
  if (elements.resolutionIncrease) elements.resolutionIncrease.disabled ||= sizeLocked;

  // The reference picker is always present. A model that takes no
  // references greys it out rather than making it disappear, so the
  // capability is visible instead of merely absent.
  const referenceLimit = maxReferencesFor(state.modelId);
  const canAddReference =
    editable && referenceLimit > 0 && activeReferencePaths().length < referenceLimit;
  if (elements.referenceAdd) elements.referenceAdd.disabled = !canAddReference;
  elements.referencePicker?.classList.toggle('disabled', referenceLimit === 0);
  if (elements.referenceLegend) {
    // Before a model is acknowledged there is nothing to say about its
    // capability -- saying "not supported" while one is still loading
    // would describe the absence of an answer as an answer.
    elements.referenceLegend.textContent =
      state.modelId === null
        ? 'Reference images'
        : referenceLimit === 0
          ? 'Reference images (not supported by this model)'
          : `Reference images (up to ${referenceLimit})`;
  }
  if (elements.referenceError) {
    elements.referenceError.textContent = state.compatibility?.reason ?? '';
  }
  if (elements.pauseButton) updatePauseButton();
  renderReferenceList();
}

function renderReferenceList(): void {
  const list = elements.referenceList;
  if (!list) return;
  list.replaceChildren();
  const paths = activeReferencePaths();
  const editable = canRequestEditingChange();
  paths.forEach((path, index) => {
    const item = document.createElement('li');
    const preview = document.createElement('img');
    preview.src = convertFileSrc(path);
    preview.alt = previewLabel(path, index, paths.length);
    const filename = path.split(/[\\/]/).at(-1) ?? path;
    const name = document.createElement('span');
    name.textContent = filename;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', `Remove reference ${index + 1} of ${paths.length}: ${filename}`);
    remove.disabled = !editable;
    remove.addEventListener('click', () => {
      requestEditingUpdate(state.modelId, removeReference(state.references, index));
    });
    const replace = document.createElement('button');
    replace.type = 'button';
    replace.textContent = 'Replace';
    replace.setAttribute('aria-label', `Replace reference ${index + 1} of ${paths.length}: ${filename}`);
    replace.disabled = !editable;
    replace.addEventListener('click', async () => {
      if (!canRequestEditingChange()) return;
      try {
        const picked = await invoke<string[]>('pick_reference_files');
        if (!picked.length) return;
        const result = replaceReference(state.references, index, picked[0]!);
        if (result.errors.length) {
          if (elements.referenceError) elements.referenceError.textContent = result.errors.join(' ');
          return;
        }
        requestEditingUpdate(state.modelId, result.references);
      } catch (error) {
        if (elements.referenceError) elements.referenceError.textContent = String(error);
      }
    });
    item.append(preview, name, remove, replace);
    list.append(item);
  });
}

/**
 * Send one acknowledged-configuration update: model, references, and the
 * output canvas in explicit pixels. Returns whether it actually sent --
 * it withholds while a worker is unsettled or an update is in flight,
 * and the caller has to undo any display it moved ahead of the send.
 *
 * This is also the command that starts a deferred session: when no model
 * has been selected yet there is no backend, and the backend the user
 * just picked is created from exactly this message (see `handle_init`
 * in textbrush/ipc/handler.py). Hence the `awaiting_model` branch --
 * waiting for a settled worker there would wait forever.
 */
function sendEditingUpdate(
  modelId: string | null,
  references: string[],
  size?: { aspectRatio: string; width: number; height: number },
): boolean {
  if (!modelId || state.configUpdateInFlight) return false;
  if (!state.settled && !isAwaitingModel()) return false;
  state.pendingReferences = references;
  state.pendingModelId = modelId;
  state.configUpdateInFlight = true;
  renderEditingControls();
  const aspectRatio = size?.aspectRatio ?? state.aspectRatio;
  const width = size?.width ?? state.width;
  const height = size?.height ?? state.height;
  const localReason = compatibilityMessage(modelId, references.length);
  if (localReason && elements.referenceError) elements.referenceError.textContent = localReason;
  void invoke('update_generation_config', {
    prompt: elements.promptInput?.value || state.prompt,
    aspectRatio,
    width,
    height,
    modelId,
    references,
    // The backend derives the preset identifier from the dimensions;
    // sending one here would override the size the user just picked.
    preset: null,
  }).catch(error => {
    state.configUpdateInFlight = false;
    state.pendingReferences = null;
    state.pendingModelId = null;
    renderEditingControls();
    if (elements.referenceError) elements.referenceError.textContent = String(error);
  });
  return true;
}

/**
 * Request a model/reference/canvas change from wherever the worker is.
 *
 * A settled worker (or none yet) takes the change at once. A running
 * worker is paused for it: the change is parked in
 * `state.deferredConfigChange`, `pumpDeferredConfigChange` sends it when
 * `state_changed(paused, settled=true)` arrives, and `handleConfigAck`
 * resumes generation afterwards if it was running when the user asked.
 * A worker that is already coming to rest after a manual pause simply
 * waits for the settled signal and stays paused afterwards.
 *
 * Returns whether the change was taken (sent or parked). Nothing is
 * taken while a model loads, while a change is in flight, or while one
 * is already parked; the controls are disabled in those cases so a
 * refused click is not the normal path.
 */
function requestEditingUpdate(
  modelId: string | null,
  references: string[],
  size?: { aspectRatio: string; width: number; height: number },
): boolean {
  if (!modelId || !canRequestEditingChange()) return false;
  if (state.settled || isAwaitingModel()) {
    return sendEditingUpdate(modelId, references, size);
  }
  state.deferredConfigChange = { modelId, references, size, resumeAfter: isWorkerRunning() };
  // The viewer names the model being switched to and the list shows the
  // references being applied, exactly as for an in-flight update.
  state.pendingModelId = modelId;
  state.pendingReferences = references;
  renderEditingControls();
  updateLoadingOverlayForState();
  pumpDeferredConfigChange();
  return true;
}

/**
 * Advance a parked change: ask the worker to pause while it runs, and
 * send the change the moment it reports quiescence. Called whenever the
 * backend state moves.
 */
function pumpDeferredConfigChange(): void {
  const deferred = state.deferredConfigChange;
  if (!deferred) return;
  if (state.settled) {
    state.deferredConfigChange = null;
    resumeAfterConfigAck = deferred.resumeAfter;
    if (!sendEditingUpdate(deferred.modelId, deferred.references, deferred.size)) {
      resumeAfterConfigAck = false;
      state.pendingModelId = null;
      state.pendingReferences = null;
      renderEditingControls();
    }
    return;
  }
  if (isWorkerRunning() && !pauseCommandInFlight) {
    requestPauseToggle();
  }
  // Otherwise the pause is under way; the settled signal drives the send.
}

/**
 * Claim an output-size change for the acknowledged-configuration seam.
 *
 * Returns true when this module owns the update -- whether it sent it or
 * withheld it; see `OutputSizeHandler` in config_controls.ts for the
 * contract. A model that takes references must go through
 * `apply_configuration` so its references are re-decoded onto the new
 * canvas, and with no model selected there is nothing to send at all.
 */
function claimOutputSizeChange(aspectRatio: string, width: number, height: number): boolean {
  if (!state.modelId) {
    // Nothing is loaded yet, so there is no backend to acknowledge this
    // and no ack to reconcile against: the local state IS the truth
    // until a model is selected, and it travels with that selection.
    state.aspectRatio = aspectRatio;
    state.width = width;
    state.height = height;
    return true;
  }
  if (!isEditingModel(state.modelId)) return false;
  const sent = requestEditingUpdate(state.modelId, state.references, { aspectRatio, width, height });
  if (!sent) {
    // The seam withheld the update (unsettled worker, or one already in
    // flight). Nothing reached the backend, so no ack will come back to
    // reconcile against -- put the controls back where they were rather
    // than leaving them showing a size that is not being generated.
    ConfigControls.syncOutputSizeControls(state);
  }
  return true;
}

function setupEditingControls(): void {
  elements.modelRadios?.forEach(radio => {
    radio.addEventListener('change', () => {
      const requested = radio.value;
      renderEditingControls(); // Selection changes only after config_ack.
      // A model that takes no references cannot carry the ones the
      // previous model held; dropping them here keeps the update the
      // backend acknowledges the same one the user can see.
      const references = maxReferencesFor(requested) > 0 ? state.references : [];
      requestEditingUpdate(requested, references, {
        aspectRatio: state.aspectRatio,
        width: state.width,
        height: state.height,
      });
    });
  });
  elements.referenceAdd?.addEventListener('click', async () => {
    // The picker opens whether or not the worker is settled: choosing
    // files needs nothing from the backend, and the change they produce
    // is taken by `requestEditingUpdate`, which pauses the worker when
    // it has to.
    if (!canRequestEditingChange()) return;
    const limit = maxReferencesFor(state.modelId);
    if (limit === 0) return;
    try {
      const picked = await invoke<string[]>('pick_reference_files');
      const result = applyPickedPaths(state.references, picked, limit);
      if (result.errors.length && elements.referenceError) {
        elements.referenceError.textContent = result.errors.join(' ');
      }
      if (result.references.length !== state.references.length) {
        requestEditingUpdate(state.modelId, result.references);
      }
    } catch (error) {
      if (elements.referenceError) elements.referenceError.textContent = String(error);
    }
  });
}

function handleConfigAck(payload: ConfigAckPayload): void {
  state.modelId = payload.model_id;
  state.references = [...payload.reference_paths];
  state.preset = payload.preset;
  state.compatibility = {
    compatible: payload.compatible,
    reason: payload.incompatibility_reason,
    requiredModel: payload.required_model,
  };
  state.pendingReferences = null;
  state.pendingModelId = null;
  state.configUpdateInFlight = false;
  // The acknowledged canvas is backend truth; the output-size group must
  // show the size the next image is actually generated at, not the one
  // the UI last asked for.
  if (typeof payload.width === 'number' && typeof payload.height === 'number') {
    const ratio = ConfigControls.ratioForDimensions(payload.width, payload.height);
    if (ratio) state.aspectRatio = ratio;
    state.width = payload.width;
    state.height = payload.height;
    ConfigControls.syncOutputSizeControls(state);
  }
  // config_ack is the second channel of truth for the settled gate. An omitted
  // value leaves whatever state_changed last reported intact.
  if (typeof payload.settled === 'boolean') {
    state.settled = payload.settled;
  }
  renderEditingControls();
  // A change that interrupted a running worker hands generation back
  // once it is acknowledged -- but only a compatible configuration can
  // run, and the backend refuses to resume an incompatible one anyway.
  const resume = resumeAfterConfigAck;
  resumeAfterConfigAck = false;
  if (resume && payload.compatible && state.backendState?.state === 'paused') {
    requestPauseToggle();
  }
}

/**
 * Adopt the backend's model catalogue.
 *
 * This is the registry's own answer to "which models exist, how many
 * references does each take, and are its weights here" -- it replaces
 * the mirror table in reference_picker.ts, so the greying-out of the
 * reference picker follows the backend rather than a second copy of the
 * cardinality rules.
 */
function handleModelList(payload: ModelListPayload): void {
  adoptModelCapabilities(
    payload.models.map(entry => ({
      id: entry.model_id,
      displayName: entry.display_name,
      minReferences: entry.min_references,
      maxReferences: entry.max_references,
      available: entry.available,
    })),
  );
  renderEditingControls();
}

// Message Handler with Type Dispatch
function handleMessage(msg: SidecarMessage): void {
  if (!msg || !msg.type) {
    console.warn('Invalid message format:', msg);
    return;
  }

  switch (msg.type) {
    case 'state_changed':
      handleStateChanged(msg.payload as StateChangedPayload);
      break;

    case 'image_ready':
      imageReadyQueue = imageReadyQueue
        .then(() => handleImageReady(msg.payload as ImagePayload))
        .catch(err => {
          console.error('Failed to handle image_ready event:', err);
        });
      break;

    case 'image_list':
      void handleImageList(msg.payload as ImageListPayload);
      break;

    case 'accepted':
      void handleAccepted(msg.payload as AcceptedPayload);
      break;

    case 'aborted':
      handleAborted();
      break;

    case 'delete_ack':
      handleDeleteAck(msg.payload as DeleteAckPayload);
      break;

    case 'error':
      handleErrorMessage(msg.payload as ErrorPayload);
      break;

    case 'config_ack':
      handleConfigAck(msg.payload as ConfigAckPayload);
      break;

    case 'model_list':
      handleModelList(msg.payload as ModelListPayload);
      break;

    default: {
      // Exhaustive check: all SidecarMessage union variants are handled above.
      // If this branch is reached at runtime, the message type is unknown.
      const unknownMsg = msg as { type?: unknown };
      console.warn('Unknown message type:', unknownMsg.type);
    }
  }
}

// Message Handlers
function handleStateChanged(payload: StateChangedPayload): void {
  state.backendState = payload;
  state.settled = payload.state === 'paused' && payload.settled === true;
  renderEditingControls();
  const backendPaused = isBackendStatePaused(payload.state);
  if (desiredPausedState !== null && backendPaused !== null && backendPaused === desiredPausedState) {
    pauseCommandInFlight = false;
    desiredPausedState = null;
  } else if (payload.state === 'error') {
    pauseCommandInFlight = false;
    desiredPausedState = null;
  }
  if (payload.state === 'error') {
    // Whatever was waiting for a settled worker will not get one.
    state.deferredConfigChange = null;
    resumeAfterConfigAck = false;
  } else {
    pumpDeferredConfigChange();
  }

  // Update deprecated isPaused flag for compatibility
  state.isPaused = payload.state === "paused";

  // Update generationPrompt when entering generating state
  if (payload.state === "generating" && 'prompt' in payload) {
    state.generationPrompt = payload.prompt;
  }

  // Handle fatal errors immediately - disable all operations before anything else
  if (payload.state === "error" && 'fatal' in payload && payload.fatal) {
    handleFatalError(payload.message);
    return; // Don't process any further state updates
  }

  // Update spinner/loading display
  updateLoadingOverlayForState();

  // Update pause button if paused state changes
  updatePauseButton();

  // Recovery invocation: after first non-loading state, sync any pre-existing backend state.
  // Guard prevents duplicate calls. Only trigger when imageList is empty to avoid
  // interfering with in-progress image_ready events during normal startup.
  if (
    !recoveryAttempted &&
    payload.state !== 'loading' &&
    state.imageList.length === 0
  ) {
    recoveryAttempted = true;
    invoke('get_image_list').catch(err => {
      console.warn('get_image_list recovery call failed (non-fatal):', err);
    });
  }

  console.log('Backend state changed:', payload.state, payload);
}

/**
 * Handle fatal error: immediately disable all controls and schedule window close.
 * This ensures no further operations can be initiated after a fatal error.
 */
function handleFatalError(message: string): void {
  console.error('Fatal error received:', message);
  state.isTransitioning = true;
  state.deferredConfigChange = null;
  resumeAfterConfigAck = false;

  // Immediately disable all interactive buttons
  const buttons = [
    elements.prevButton,
    elements.nextButton,
    elements.acceptButton,
    elements.deleteButton,
    elements.abortButton,
    elements.pauseButton,
    elements.themeToggle,
    elements.resolutionDecrease,
    elements.resolutionIncrease,
    elements.copyPathBtn,
  ];

  buttons.forEach(btn => {
    if (btn) btn.disabled = true;
  });

  // Disable prompt input
  if (elements.promptInput) {
    elements.promptInput.disabled = true;
  }

  // Disable aspect ratio radios
  if (elements.aspectRatioRadios) {
    elements.aspectRatioRadios.forEach(radio => {
      radio.disabled = true;
    });
  }

  // Show error prominently in loading overlay
  showLoading(true);
  if (elements.loadingSpinner) {
    elements.loadingSpinner.classList.add('hidden');
  }
  if (elements.loadingLabel) {
    elements.loadingLabel.textContent = `Fatal Error: ${message}`;
    elements.loadingLabel.classList.add('error');
  }
  if (elements.loadingPrompt) {
    elements.loadingPrompt.textContent = 'Application will close shortly...';
    elements.loadingPrompt.classList.remove('hidden');
  }

  // Schedule window close after showing error
  setTimeout(() => {
    void appWindow.close();
  }, 3000);
}

/**
 * Handle legacy error message type from backend.
 * Fatal errors delegate to handleFatalError for full UI lockdown and auto-close.
 * Non-fatal errors display a transient notification in the loading prompt area.
 */
function handleErrorMessage(payload: ErrorPayload): void {
  if (payload.operation === 'accept') {
    showAcceptanceError(payload.message);
  }
  if (state.configUpdateInFlight) {
    state.configUpdateInFlight = false;
    state.pendingReferences = null;
    state.pendingModelId = null;
    // The worker stays paused with the message in view rather than
    // resuming as if the change had gone through.
    resumeAfterConfigAck = false;
    renderEditingControls();
    if (elements.referenceError) elements.referenceError.textContent = payload.message;
  }
  if (payload.fatal) {
    handleFatalError(payload.message);
  } else {
    console.warn('Non-fatal backend error:', payload.message);
    // Display brief notification in loading prompt area if visible
    if (elements.loadingPrompt) {
      const original = elements.loadingPrompt.textContent;
      elements.loadingPrompt.textContent = `Error: ${payload.message}`;
      elements.loadingPrompt.classList.remove('hidden');
      setTimeout(() => {
        if (elements.loadingPrompt) {
          elements.loadingPrompt.textContent = original;
        }
      }, 3000);
    }
  }
}

async function handleImageReady(payload: ImagePayload): Promise<void> {
  state.currentImage = payload;

  // Convert file path to asset URL for display
  const assetUrl = convertFileSrc(payload.path);
  console.log('Loading image from:', payload.path, '-> asset URL:', assetUrl);

  // Parse PNG metadata from file (includes seed)
  const metadata = await fetchAndParsePngMetadata(assetUrl);
  console.log('Parsed metadata:', metadata);

  // Create image record with parsed metadata
  const record: ImageRecord = {
    index: payload.index,  // NEW: Store backend index for deletion
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

  // Immediately update nav dots so new image appears in indicator
  updateNavDots();

  void displayImageRecord(record);
  showLoading(false);
  enableAcceptButton();
}

async function handleImageList(payload: ImageListPayload): Promise<void> {
  const entries = payload.images ?? [];
  console.log('Received image_list event with', entries.length, 'entries');

  // Filter out deleted entries per spec: frontend only displays non-deleted images
  const activeEntries = entries.filter(entry => !entry.deleted);

  if (activeEntries.length === 0) {
    // Recovery is authoritative, including when the last retained image was deleted.
    state.imageList = [];
    state.currentIndex = -1;
    state.currentImage = null;
    showLoadingPlaceholder();
    return;
  }

  // Rebuild image list from active entries, preserving order by index
  const newImageList: ImageRecord[] = [];
  for (const entry of activeEntries) {
    const assetUrl = convertFileSrc(entry.path);
    // Attempt to parse metadata from PNG; fall back to empty values if unavailable
    let metadata: Awaited<ReturnType<typeof fetchAndParsePngMetadata>>;
    try {
      metadata = await fetchAndParsePngMetadata(assetUrl);
    } catch (err) {
      console.warn('image_list: failed to parse metadata for', entry.path, err);
      metadata = {};
    }

    const record: ImageRecord = {
      index: entry.index,
      path: entry.path,
      displayPath: entry.display_path,
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
    newImageList.push(record);
  }

  // Replace the frontend image list entirely
  state.imageList = newImageList;
  state.currentIndex = newImageList.length - 1;

  // Show the last (most recent) image and update UI
  const currentRecord = state.imageList[state.currentIndex];
  if (currentRecord) {
    void displayImageRecord(currentRecord, state.currentIndex);
    showLoading(false);
    enableAcceptButton();
  }
  updateNavDots();

  console.log('image_list: rebuilt imageList with', newImageList.length, 'images, currentIndex=', state.currentIndex);
}

async function handleAccepted(payload: AcceptedPayload): Promise<void> {
  // Backend now provides the list of retained paths directly
  const retainedPaths = payload.paths || [];

  visualSuccessFeedback();
  setTimeout(() => {
    void (async () => {
      try {
        // Note: asset URLs from convertFileSrc don't need revoking like blob URLs

        if (retainedPaths.length === 0) {
          await invoke('abort_exit');
        } else {
          await invoke('print_paths_and_exit', { paths: retainedPaths });
        }
      } catch (err) {
        console.error('Failed to call exit handler:', err);
        await appWindow.close();
      }
    })();
  }, 500);
}

function handleAborted(): void {
  if (abortExitScheduled) return;
  abortExitScheduled = true;
  state.isTransitioning = true;
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

function handleDeleteAck(payload: DeleteAckPayload): void {
  const index = payload.index;
  console.log('Image deleted from backend, index:', index);

  // Remove image from imageList by matching backend index
  const imageIndex = state.imageList.findIndex(img => img.index === index);
  if (imageIndex !== -1) {
    state.imageList.splice(imageIndex, 1);

    // Adjust currentIndex to keep pointing at the same image after splice
    if (state.imageList.length === 0) {
      // No images left
      state.currentIndex = -1;
    } else if (imageIndex < state.currentIndex) {
      // Deleted image was before current position - decrement to follow the shift
      state.currentIndex--;
    } else if (imageIndex === state.currentIndex) {
      // Deleted the current image - stay at same index (now shows next image)
      // But clamp to valid range if we were at the end
      if (state.currentIndex >= state.imageList.length) {
        state.currentIndex = state.imageList.length - 1;
      }
    }
    // If imageIndex > currentIndex, no adjustment needed

    // Update UI
    if (state.imageList.length === 0) {
      showLoadingPlaceholder();
    } else {
      const currentRecord = state.imageList[state.currentIndex];
      if (currentRecord) {
        void displayImageRecord(currentRecord);
      }
    }
    updateNavDots();
  }
}

function updateLoadingOverlayForState(): void {
  if (!state.backendState) {
    return;
  }
  const backendStateValue = state.backendState.state;

  // Determine if spinner should be visible
  const spinnerVisible = backendStateValue === "loading" || backendStateValue === "generating";
  if (elements.loadingSpinner) {
    if (spinnerVisible) {
      elements.loadingSpinner.classList.remove('hidden');
    } else {
      elements.loadingSpinner.classList.add('hidden');
    }
  }

  // Update label text based on state (use type narrowing for state-specific fields)
  if (elements.loadingLabel && !elements.loadingOverlay?.classList.contains('hidden')) {
    let labelText: string;
    switch (state.backendState.state) {
      case "awaiting_model":
        labelText = "select a model to begin";
        break;
      case "loading": {
        const pending = modelCapability(state.pendingModelId);
        labelText = pending ? `loading ${pending.displayName}` : "loading model";
        break;
      }
      case "idle":
        labelText = "ready";
        break;
      case "generating":
        labelText = state.deferredConfigChange
          ? "finishing the current image before applying changes"
          : "generating";
        break;
      case "paused":
        labelText = state.deferredConfigChange
          ? "finishing the current image before applying changes"
          : "generation paused";
        break;
      case "error":
        labelText = state.backendState.message || "error";
        break;
      default:
        labelText = backendStateValue;
    }
    elements.loadingLabel.textContent = labelText;
  }

  // Show/hide prompt based on state (use type narrowing for prompt field)
  if (elements.loadingPrompt) {
    if (state.backendState.state === "generating") {
      elements.loadingPrompt.textContent = state.backendState.prompt;
      elements.loadingPrompt.classList.remove('hidden');
    } else {
      elements.loadingPrompt.classList.add('hidden');
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

  if (elements.pauseButton) {
    const backendStateValue = state.backendState?.state ?? null;
    const backendAllowsPause =
      backendStateValue === 'idle' ||
      backendStateValue === 'generating' ||
      backendStateValue === 'paused';
    elements.pauseButton.disabled =
      !backendAllowsPause || pauseCommandInFlight || state.configUpdateInFlight ||
      state.deferredConfigChange !== null;
  }
}

// Display ImageRecord with Transitions
async function displayImageRecord(record: ImageRecord, listIdx: number | null = null): Promise<void> {
  console.log('displayImageRecord called, seed:', record.seed, 'path:', record.path);
  if (state.isTransitioning) {
    pendingDisplayRequest = { record, listIdx };
    console.log('Queued display request - transition in progress');
    return;
  }

  state.isTransitioning = true;

  try {
    // Always use animations (buffer concept removed)
    const fadeOutDuration = 100;
    const fadeInDuration = 200;

    if (elements.currentImage && elements.currentImage.src) {
      elements.currentImage.classList.add('image-exit');
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
      elements.currentImage.classList.add('image-enter');
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
    if (pendingDisplayRequest) {
      const nextRequest = pendingDisplayRequest;
      pendingDisplayRequest = null;
      void displayImageRecord(nextRequest.record, nextRequest.listIdx);
    }
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

    // Update path display in status bar - show preview path
    // Use display paths (with ~ for home dir) for UI, keep absolute paths for copy
    const displayPathStr = record.displayPath || '—';
    const absolutePath = record.path || '';
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

// Navigation dots configuration
// Fixed maximum provides consistent behavior across all screen sizes
const MAX_VISIBLE_DOTS = 25;  // Maximum dots before using gap indicators

/**
 * Update navigation dots display.
 *
 * The navigation model:
 * - Total positions = imageList.length + 1 (images + spinner)
 * - Position 0 to imageList.length-1 are images
 * - Position imageList.length is always the "loading/spinner" position
 * - Minimum 1 dot (spinner when no images)
 * - Active position: viewing spinner (loading overlay visible) → spinner; otherwise → currentIndex
 */
function updateNavDots(): void {
  if (!elements.navDots) {
    return;
  }

  const imageCount = state.imageList.length;
  // Total positions = images + 1 (spinner is always the last position)
  const totalPositions = imageCount + 1;

  // Determine active position based on what user is actually viewing
  // Check if loading overlay is visible (user is viewing spinner)
  const isViewingSpinner = elements.loadingOverlay && !elements.loadingOverlay.classList.contains('hidden');
  let activePosition: number;
  if (imageCount === 0 || isViewingSpinner) {
    activePosition = imageCount; // Last position = spinner
  } else {
    activePosition = state.currentIndex;
  }

  // Clear existing dots
  elements.navDots.innerHTML = '';

  // If all positions fit within max, show them all (simple case)
  if (totalPositions <= MAX_VISIBLE_DOTS) {
    for (let i = 0; i < totalPositions; i++) {
      const isSpinner = i === imageCount;
      const dot = createNavDot(i, i === activePosition, isSpinner);
      elements.navDots.appendChild(dot);
    }
    announceNavigation(activePosition, totalPositions);
    return;
  }

  // Need gap indicators - show subset of dots with gaps
  // Strategy: collect indices to show, sort them, then add gaps where needed
  const edgeDots = 3;  // Show first 3 and last 3 image dots
  const activeRadius = 2;  // Show 2 dots on each side of active

  // Collect all image indices to show (use Set to avoid duplicates)
  const indicesToShow = new Set<number>();

  // Add first edge dots (0, 1, 2)
  for (let i = 0; i < Math.min(edgeDots, imageCount); i++) {
    indicesToShow.add(i);
  }

  // Add active region (if active is an image, not spinner)
  if (activePosition < imageCount) {
    const activeStart = Math.max(0, activePosition - activeRadius);
    const activeEnd = Math.min(imageCount - 1, activePosition + activeRadius);
    for (let i = activeStart; i <= activeEnd; i++) {
      indicesToShow.add(i);
    }
  }

  // Add last edge dots
  const lastEdgeStart = Math.max(0, imageCount - edgeDots);
  for (let i = lastEdgeStart; i < imageCount; i++) {
    indicesToShow.add(i);
  }

  // Sort indices and build final array with gaps
  const sortedIndices = Array.from(indicesToShow).sort((a, b) => a - b);
  const dotsToShow: Array<number | 'gap'> = [];

  for (let i = 0; i < sortedIndices.length; i++) {
    const idx = sortedIndices[i]!;
    const prevIdx = sortedIndices[i - 1];
    // Add gap if there's a jump from previous index
    if (i > 0 && prevIdx !== undefined && idx > prevIdx + 1) {
      dotsToShow.push('gap');
    }
    dotsToShow.push(idx);
  }

  // Add gap before spinner if needed (last image index + 1 < imageCount means gap)
  const lastImageIdx = sortedIndices[sortedIndices.length - 1];
  if (lastImageIdx !== undefined && lastImageIdx < imageCount - 1) {
    dotsToShow.push('gap');
  }

  // Always add spinner dot at the end
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

  // Check if currently viewing spinner (loading overlay visible)
  const isViewingSpinner = elements.loadingOverlay && !elements.loadingOverlay.classList.contains('hidden');

  // Handle spinner dot click - show loading placeholder
  if (isSpinner) {
    if (isViewingSpinner) {
      return; // Already on spinner
    }
    showLoadingPlaceholder();
    return;
  }

  // Handle image dot click
  if (index < 0 || index >= state.imageList.length) {
    return;
  }

  if (index === state.currentIndex && !isViewingSpinner) {
    return; // Already on this image
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

  // If currently showing spinner but we have images, navigate to last image
  const isViewingSpinner = elements.loadingOverlay && !elements.loadingOverlay.classList.contains('hidden');
  if (isViewingSpinner && state.imageList.length > 0) {
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

  const isAlreadyGenerating = state.backendState !== null &&
    (state.backendState.state === "generating" || state.backendState.state === "loading");
  if (isAlreadyGenerating && state.currentIndex >= state.imageList.length - 1) {
    console.log('Already waiting for next image');
    return;
  }

  const requestNextImage = () => {
    showLoadingPlaceholder();

    state.actionQueue = state.actionQueue
      .then(async () => {
        await invoke('skip_image');
      })
      .catch(err => {
        console.error('Next failed:', err);
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

function showAcceptanceError(message: string): void {
  state.acceptInFlight = false;
  enableAcceptButton();
  if (elements.validationError) {
    elements.validationError.textContent = `Save failed: ${message}`;
    elements.validationError.classList.remove('hidden');
    elements.validationError.style.display = 'block';
  }
}

function accept(): void {
  if (elements.acceptButton && !state.isTransitioning && !state.acceptInFlight) {
    state.acceptInFlight = true;
    elements.acceptButton.disabled = true;
    if (elements.validationError) elements.validationError.textContent = '';
    invoke('accept_image').catch((err: unknown) => {
      console.error('Accept failed:', err);
      showAcceptanceError(err instanceof Error ? err.message : String(err));
    });
  }
}

function abort(): void {
  if (state.isTransitioning) {
    return;
  }

  state.isTransitioning = true;
  invoke('abort_generation').catch(err => {
    console.error('Abort failed:', err);
  }).finally(handleAborted);
}

/**
 * The user's pause/resume. Withheld while a parked configuration change
 * owns the pause: resuming under it would race the change it waits for.
 */
function togglePause(): void {
  if (state.deferredConfigChange) return;
  requestPauseToggle();
}

function requestPauseToggle(): void {
  const backendStateValue = state.backendState?.state ?? null;
  const backendAllowsPause =
    backendStateValue === 'idle' ||
    backendStateValue === 'generating' ||
    backendStateValue === 'paused';
  if (!backendAllowsPause || pauseCommandInFlight) {
    return;
  }

  const currentPaused = state.backendState?.state === 'paused';
  desiredPausedState = !currentPaused;
  pauseCommandInFlight = true;
  updatePauseButton();
  invoke('pause_generation').catch(err => {
    pauseCommandInFlight = false;
    desiredPausedState = null;
    updatePauseButton();
    console.error('Pause toggle failed:', err);
  });
}

function deleteCurrentImage(): void {
  if (state.isTransitioning) {
    return;
  }

  if (state.currentIndex < 0 || state.currentIndex >= state.imageList.length) {
    return;
  }

  const imageToDelete = state.imageList[state.currentIndex];
  if (!imageToDelete) {
    return;
  }

  // Send DELETE command to backend with index (not path)
  state.actionQueue = state.actionQueue
    .then(async () => {
      try {
        await invoke('delete_image', { index: imageToDelete.index });
        // Wait for delete_ack event - no optimistic removal
        // The handleDeleteAck function will handle UI updates
        console.log('Delete command sent, waiting for backend acknowledgment');
      } catch (err) {
        console.error('Delete failed:', err);
        // Show error message to user
        if (elements.loadingPrompt) {
          elements.loadingPrompt.textContent = `Delete failed: ${err instanceof Error ? err.message : String(err)}`;
          setTimeout(() => {
            // Restore prompt if still in generating state (use type narrowing)
            if (elements.loadingPrompt && state.backendState !== null &&
                state.backendState.state === "generating") {
              elements.loadingPrompt.textContent = state.backendState.prompt;
            }
          }, 2000);
        }
      }
    })
    .catch((err: unknown) => {
      console.error('Delete action queue error:', err);
    });
}

function enableAcceptButton(): void {
  if (elements.acceptButton && !state.acceptInFlight) {
    elements.acceptButton.disabled = false;
  }
}

function setupButtonListeners(): void {
  if (buttonListenersInitialized) {
    return;
  }
  buttonListenersInitialized = true;

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
      // Copy preview path to clipboard
      const path = entry?.path;
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
  if (keyboardListenersInitialized) {
    return;
  }
  keyboardListenersInitialized = true;

  document.addEventListener('keydown', (e: KeyboardEvent) => {
    const eventTarget = e.target;
    const target = eventTarget instanceof HTMLElement ? eventTarget : null;
    const isTextInput =
      target?.tagName === 'INPUT' && (target as HTMLInputElement).type === 'text';
    const isInteractiveControl =
      target?.tagName === 'BUTTON' ||
      target?.tagName === 'SELECT' ||
      target?.tagName === 'TEXTAREA' ||
      (target?.tagName === 'INPUT' && !isTextInput) ||
      target?.getAttribute('role') === 'button' ||
      target?.isContentEditable === true;

    if (isTextInput || isInteractiveControl) {
      return;
    }

    if (e.repeat) {
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

// Expose for testing
declare global {
  interface Window {
    textbrushApp?: {
      state: AppState;
      elements: Elements;
      init: typeof init;
      handleMessage: typeof handleMessage;
      handleImageList: typeof handleImageList;
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
    handleImageList,
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
