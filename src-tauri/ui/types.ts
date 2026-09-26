// Type definitions for Textbrush UI

// IPC Message types from Python backend
// ImagePayload is path-based; all metadata (including seed) is parsed from PNG tEXt chunks
export interface ImagePayload {
  index: number;             // NEW: Stable backend index for deletion
  path: string;              // Absolute path to preview PNG file
  display_path: string;      // Path with home dir replaced by ~
}

// Discriminated union for StateChangedPayload - provides type safety for state-specific fields
// No model has been selected yet, so nothing is loaded and nothing is
// generating. Deferred loading parks here at launch: the model selector
// is live immediately instead of waiting out a load nobody asked for.
export interface StateChangedAwaitingModel {
  state: "awaiting_model";
}

export interface StateChangedLoading {
  state: "loading";
}

export interface StateChangedIdle {
  state: "idle";
}

export interface StateChangedGenerating {
  state: "generating";
  prompt: string;            // Required when state = "generating"
}

export interface StateChangedPaused {
  state: "paused";
  settled?: boolean;
}

export interface StateChangedError {
  state: "error";
  message: string;           // Required when state = "error"
  fatal: boolean;            // Required when state = "error"
}

export type StateChangedPayload =
  | StateChangedAwaitingModel
  | StateChangedLoading
  | StateChangedIdle
  | StateChangedGenerating
  | StateChangedPaused
  | StateChangedError;

export interface ImageListPayload {
  images: Array<{
    index: number;
    path: string;
    display_path: string;
    deleted: boolean;
  }>;
}

export interface AcceptedPayload {
  paths?: string[];          // Array of retained output paths from backend
  display_paths?: string[];  // Display paths for retained outputs
  path?: string;             // Legacy: absolute path to saved file
  display_path?: string;     // Legacy: path with home dir replaced by ~
}

export interface DeleteAckPayload {
  index: number;             // Changed from image_id: string to match new protocol
}

// Discriminated union for SidecarMessage - provides type safety for message-specific payloads
export interface StateChangedMessage {
  type: 'state_changed';
  payload: StateChangedPayload;
}

export interface ImageReadyMessage {
  type: 'image_ready';
  payload: ImagePayload;
}

export interface ImageListMessage {
  type: 'image_list';
  payload: ImageListPayload;
}

export interface AcceptedMessage {
  type: 'accepted';
  payload: AcceptedPayload;
}

export interface AbortedMessage {
  type: 'aborted';
  payload: Record<string, unknown>;
}

export interface DeleteAckMessage {
  type: 'delete_ack';
  payload: DeleteAckPayload;
}

// Legacy error event payload - used for non-fatal operational errors from backend
// (e.g. "No images to accept", "Backend not initialized", "Prompt cannot be empty")
// Fatal errors are delivered via state_changed with state="error" instead.
export interface ErrorPayload {
  operation?: string;
  saved_paths?: string[];
  message: string;
  fatal: boolean;
  cause?: string | null;
  required_model?: string | null;
}

export interface ConfigAckPayload {
  model_id: string;
  reference_count: number;
  reference_paths: string[];
  preset: string | null;
  compatible: boolean;
  incompatibility_reason: string | null;
  required_model: string | null;
  // Optional: the backend stamps this on every config_ack, but an omitted value
  // must leave the settled gate as state_changed last reported it rather than
  // silently disabling every editing control.
  settled?: boolean;
  // The acknowledged output canvas in pixels; null before the first
  // generation has been configured. The output-size group reconciles to
  // this rather than to `preset`, which names only some of the sizes.
  width?: number | null;
  height?: number | null;
}

export interface ConfigAckMessage {
  type: 'config_ack';
  payload: ConfigAckPayload;
}

// One registered model as the backend's registry describes it, including
// whether its weights are present locally. Emitted once per session,
// before anything is loaded, so the selector can be rendered and offered
// while no model is loading.
export interface ModelListEntry {
  model_id: string;
  display_name: string;
  min_references: number;
  max_references: number;
  available: boolean;
  cause: string | null;
  detail: string;
}

export interface ModelListPayload {
  models: ModelListEntry[];
}

export interface ModelListMessage {
  type: 'model_list';
  payload: ModelListPayload;
}

export interface ErrorMessage {
  type: 'error';
  payload: ErrorPayload;
}

export type SidecarMessage =
  | StateChangedMessage
  | ImageReadyMessage
  | ImageListMessage
  | AcceptedMessage
  | AbortedMessage
  | DeleteAckMessage
  | ConfigAckMessage
  | ModelListMessage
  | ErrorMessage;

// Launch args from Rust backend
export interface LaunchArgs {
  prompt: string;
  aspect_ratio: string;
  buffer_max: number;
  output_path: string | null;
  seed: number | null;
  width: number;
  height: number;
  model_id?: string | null;
  references?: string[] | null;
  preset?: string | null;
}

// Image record for list navigation
// Metadata parsed from PNG tEXt chunks on arrival, stored for navigation
// File state (outputPath) is backend-owned; frontend only tracks display/preview state
export interface ImageRecord {
  index: number;                   // NEW: Stable backend index for deletion
  path: string;                    // Absolute path to preview PNG file
  displayPath: string;             // Path with home dir replaced by ~ (for display)
  seed: number;
  blobUrl: string | null;          // Object URL for display (from asset protocol)
  prompt: string;
  model: string;
  aspectRatio: string;
  width: number;                   // Final image width (after cropping)
  height: number;                  // Final image height (after cropping)
  generatedWidth?: number;         // Width passed to model (multiple of 16)
  generatedHeight?: number;        // Height passed to model (multiple of 16)
}

// Backend state object (replaces multiple boolean flags)
// Uses discriminated union for type-safe state-specific field access
export interface BackendStateAwaitingModel {
  state: "awaiting_model";
}

export interface BackendStateLoading {
  state: "loading";
}

export interface BackendStateIdle {
  state: "idle";
}

export interface BackendStateGenerating {
  state: "generating";
  prompt: string;         // Required when state = "generating"
}

export interface BackendStatePaused {
  state: "paused";
}

export interface BackendStateError {
  state: "error";
  message: string;        // Required when state = "error"
  fatal: boolean;         // Required when state = "error"
}

export type BackendState =
  | BackendStateAwaitingModel
  | BackendStateLoading
  | BackendStateIdle
  | BackendStateGenerating
  | BackendStatePaused
  | BackendStateError;

// Application state
export interface AppState {
  currentImage: ImagePayload | null;
  backendState: BackendState | null;  // null until first state_changed event received from backend
  isPaused: boolean;           // DEPRECATED: Will be removed, use backendState.state === "paused"
  isTransitioning: boolean;
  acceptInFlight: boolean;
  prompt: string;
  generationPrompt: string;    // Prompt currently being used for generation (from backendState.prompt)
  aspectRatio: string;
  width: number;
  height: number;
  outputPath: string | null;
  actionQueue: Promise<void>;
  currentBlobUrl: string | null;
  imageList: ImageRecord[];
  currentIndex: number;
  modelId: string | null;
  // The model the user just clicked, until the backend acknowledges or
  // rejects it. It never checks a radio -- selection stays backend truth
  // (FR9) -- it only lets the viewer name the model being loaded, which
  // is the one action slow enough that silence reads as a hang.
  pendingModelId: string | null;
  references: string[];
  pendingReferences: string[] | null;
  preset: string | null;
  settled: boolean;
  compatibility: { compatible: boolean; reason: string | null; requiredModel: string | null } | null;
  configUpdateInFlight: boolean;
}

// DOM element cache
export interface Elements {
  app: HTMLElement | null;
  headerBar: HTMLElement | null;
  viewer: HTMLElement | null;
  imageContainer: HTMLElement | null;
  currentImage: HTMLImageElement | null;
  loadingOverlay: HTMLElement | null;
  loadingSpinner: HTMLElement | null;
  loadingLabel: HTMLElement | null;
  loadingPrompt: HTMLElement | null;
  navIndicator: HTMLElement | null;
  navDots: HTMLElement | null;
  statusBar: HTMLElement | null;
  promptDisplay: HTMLElement | null;
  promptInput: HTMLInputElement | null;
  aspectRatioRadios: NodeListOf<HTMLInputElement> | null;
  dimensionDisplay: HTMLElement | null;
  resolutionDecrease: HTMLButtonElement | null;
  resolutionIncrease: HTMLButtonElement | null;
  validationError: HTMLElement | null;
  fontSizeRadios: NodeListOf<HTMLInputElement> | null;
  imagePathDisplay: HTMLElement | null;
  pathText: HTMLElement | null;
  copyPathBtn: HTMLButtonElement | null;
  controls: HTMLElement | null;
  prevButton: HTMLButtonElement | null;
  nextButton: HTMLButtonElement | null;
  acceptButton: HTMLButtonElement | null;
  deleteButton: HTMLButtonElement | null;
  abortButton: HTMLButtonElement | null;
  pauseButton: HTMLButtonElement | null;
  pauseIcon: HTMLElement | null;
  pauseLabel: HTMLElement | null;
  themeToggle: HTMLButtonElement | null;
  magnifierLens: HTMLElement | null;
  modelSelector: HTMLFieldSetElement | null;
  modelRadios: NodeListOf<HTMLInputElement> | null;
  referencePicker: HTMLElement | null;
  referenceAdd: HTMLButtonElement | null;
  referenceList: HTMLUListElement | null;
  referenceError: HTMLElement | null;
  outputSize: HTMLFieldSetElement | null;
  referenceLegend: HTMLElement | null;
}
