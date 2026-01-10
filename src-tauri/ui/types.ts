// Type definitions for Textbrush UI

// IPC Message types from Python backend
// ImagePayload is path-based; all metadata (including seed) is parsed from PNG tEXt chunks
export interface ImagePayload {
  path: string;              // Absolute path to preview PNG file
  display_path: string;      // Path with home dir replaced by ~
  buffer_count: number;
  buffer_max: number;
}

export interface BufferStatusPayload {
  count: number;
  generating: boolean;
}

export interface AcceptedPayload {
  path?: string;             // Absolute path to saved file
  display_path?: string;     // Path with home dir replaced by ~
}

export interface ErrorPayload {
  message: string;
  fatal: boolean;
}

export interface PausedPayload {
  paused: boolean;
}

export interface ReadyPayload {
  buffer_count?: number;
}

export interface GenerationStartedPayload {
  seed: number;
  queue_position: number;
}

export type MessagePayload =
  | ImagePayload
  | BufferStatusPayload
  | AcceptedPayload
  | ErrorPayload
  | PausedPayload
  | ReadyPayload
  | GenerationStartedPayload
  | Record<string, unknown>;

export interface SidecarMessage {
  type: 'ready' | 'image_ready' | 'generation_started' | 'buffer_status' | 'accepted' | 'aborted' | 'error' | 'paused';
  payload: MessagePayload;
}

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
export interface ImageRecord {
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
  outputPath?: string;             // Final output path after accept (moved from preview)
  outputDisplayPath?: string;      // Output path with home dir replaced by ~ (for display)
}

// Application state
export interface AppState {
  currentImage: ImagePayload | null;
  bufferCount: number;
  bufferMax: number;
  isGenerating: boolean;
  isPaused: boolean;
  isTransitioning: boolean;
  backendReady: boolean;  // True when backend has sent 'ready' message
  prompt: string;
  generationPrompt: string;  // Prompt currently being used for generation (confirmed by backend)
  aspectRatio: string;
  width: number;
  height: number;
  outputPath: string | null;
  actionQueue: Promise<void>;
  currentBlobUrl: string | null;
  imageList: ImageRecord[];
  currentIndex: number;
  waitingForNext: boolean;
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
