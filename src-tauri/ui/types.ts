// Type definitions for Textbrush UI

// IPC Message types from Python backend
// ImagePayload is path-based; all metadata (including seed) is parsed from PNG tEXt chunks
export interface ImagePayload {
  path: string;              // Absolute path to preview PNG file
  buffer_count: number;
  buffer_max: number;
}

export interface BufferStatusPayload {
  count: number;
  generating: boolean;
}

export interface AcceptedPayload {
  path?: string;
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

export type MessagePayload =
  | ImagePayload
  | BufferStatusPayload
  | AcceptedPayload
  | ErrorPayload
  | PausedPayload
  | ReadyPayload
  | Record<string, unknown>;

export interface SidecarMessage {
  type: 'ready' | 'image_ready' | 'buffer_status' | 'accepted' | 'aborted' | 'error' | 'paused';
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

// Image record for navigation history
// Metadata parsed from PNG tEXt chunks on arrival, stored for navigation
export interface ImageRecord {
  path: string;                    // Absolute path to preview PNG file
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
}

// Application state
export interface AppState {
  currentImage: ImagePayload | null;
  bufferCount: number;
  bufferMax: number;
  isGenerating: boolean;
  isPaused: boolean;
  isTransitioning: boolean;
  prompt: string;
  aspectRatio: string;
  width: number;
  height: number;
  outputPath: string | null;
  actionQueue: Promise<void>;
  currentBlobUrl: string | null;
  imageHistory: ImageRecord[];
  historyIndex: number;
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
  bufferIndicator: HTMLElement | null;
  bufferDots: HTMLElement | null;
  bufferText: HTMLElement | null;
  outputPathDisplay: HTMLElement | null;
  metadataPath: HTMLElement | null;
  controls: HTMLElement | null;
  skipButton: HTMLButtonElement | null;
  acceptButton: HTMLButtonElement | null;
  abortButton: HTMLButtonElement | null;
  pauseButton: HTMLButtonElement | null;
  pauseIcon: HTMLElement | null;
  pauseLabel: HTMLElement | null;
  themeToggle: HTMLButtonElement | null;
}
