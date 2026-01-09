// Type definitions for Textbrush UI

// IPC Message types from Python backend
export interface ImagePayload {
  image_data: string;
  seed: number;
  buffer_count: number;
  buffer_max: number;
  prompt?: string;
  model_name?: string;
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
}

// History entry for image navigation
export interface HistoryEntry {
  image_data: string;
  seed: number;
  blobUrl: string | null;
  prompt: string;
  model_name: string;
  path?: string;
}

// Application state
export interface AppState {
  currentImage: ImagePayload | null;
  currentSeed: number | null;
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
  imageHistory: HistoryEntry[];
  historyIndex: number;
  waitingForNext: boolean;
}

// DOM element cache
export interface Elements {
  app: HTMLElement | null;
  viewer: HTMLElement | null;
  imageContainer: HTMLElement | null;
  currentImage: HTMLImageElement | null;
  loadingOverlay: HTMLElement | null;
  loadingSpinner: HTMLElement | null;
  loadingPrompt: HTMLElement | null;
  statusBar: HTMLElement | null;
  promptDisplay: HTMLElement | null;
  promptInput: HTMLInputElement | null;
  aspectRatioRadios: NodeListOf<HTMLInputElement> | null;
  aspectRatioControls: HTMLElement | null;
  dimensionControls: HTMLElement | null;
  widthInput: HTMLInputElement | null;
  heightInput: HTMLInputElement | null;
  validationError: HTMLElement | null;
  bufferIndicator: HTMLElement | null;
  bufferDots: HTMLElement | null;
  bufferText: HTMLElement | null;
  outputPathDisplay: HTMLElement | null;
  controls: HTMLElement | null;
  skipButton: HTMLButtonElement | null;
  acceptButton: HTMLButtonElement | null;
  abortButton: HTMLButtonElement | null;
  pauseButton: HTMLButtonElement | null;
  pauseIcon: HTMLElement | null;
  pauseLabel: HTMLElement | null;
  themeToggle: HTMLButtonElement | null;
}
