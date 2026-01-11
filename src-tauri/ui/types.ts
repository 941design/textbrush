// Type definitions for Textbrush UI

// IPC Message types from Python backend
// ImagePayload is path-based; all metadata (including seed) is parsed from PNG tEXt chunks
export interface ImagePayload {
  index: number;             // NEW: Stable backend index for deletion
  path: string;              // Absolute path to preview PNG file
  display_path: string;      // Path with home dir replaced by ~
}

// Discriminated union for StateChangedPayload - provides type safety for state-specific fields
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
}

export interface StateChangedError {
  state: "error";
  message: string;           // Required when state = "error"
  fatal: boolean;            // Required when state = "error"
}

export type StateChangedPayload =
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

export type SidecarMessage =
  | StateChangedMessage
  | ImageReadyMessage
  | ImageListMessage
  | AcceptedMessage
  | AbortedMessage
  | DeleteAckMessage;

// Launch args from Rust backend
export interface LaunchArgs {
  prompt: string;
  aspect_ratio: string;
  buffer_max: number;
  output_path: string | null;
  seed: number | null;
  width: number;
  height: number;
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
  | BackendStateLoading
  | BackendStateIdle
  | BackendStateGenerating
  | BackendStatePaused
  | BackendStateError;

// Application state
export interface AppState {
  currentImage: ImagePayload | null;
  backendState: BackendState;  // NEW: Unified state from backend (replaces isGenerating, backendReady, waitingForNext)
  isPaused: boolean;           // DEPRECATED: Will be removed, use backendState.state === "paused"
  isTransitioning: boolean;
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
  aspectRatioControls: HTMLElement | null;
  resolutionControls: HTMLElement | null;
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
}
