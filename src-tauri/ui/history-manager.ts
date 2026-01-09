// Image History Navigation and Management
// Extends main.js navigation to support bidirectional navigation and deletion

import type { HistoryEntry, AppState } from './types';

type DisplayImageCallback = (entry: HistoryEntry) => void;
type ShowEmptyStateCallback = () => void;
type RequestNextImageCallback = () => void;

/**
 * Navigate to previous image in history.
 */
export function navigateToPrevious(
  state: AppState,
  displayImage: DisplayImageCallback
): boolean {
  if (state.historyIndex <= 0) {
    return false;
  }

  state.historyIndex--;
  const entry = state.imageHistory[state.historyIndex];
  if (entry) {
    displayImage(entry);
  }
  return true;
}

/**
 * Navigate to next image in history or request from buffer.
 */
export function navigateToNext(
  state: AppState,
  displayImage: DisplayImageCallback,
  requestNextImage: RequestNextImageCallback
): boolean {
  if (state.historyIndex < state.imageHistory.length - 1) {
    state.historyIndex++;
    const entry = state.imageHistory[state.historyIndex];
    if (entry) {
      displayImage(entry);
    }
    return true;
  }

  // At end of history - always request next image (let backend decide from buffer or generate)
  requestNextImage();
  return true;
}

/**
 * Delete current image from history and navigate away.
 */
export function deleteCurrentImage(
  state: AppState,
  displayImage: DisplayImageCallback,
  showEmptyState: ShowEmptyStateCallback
): HistoryEntry | null {
  if (state.historyIndex < 0 || state.historyIndex >= state.imageHistory.length) {
    return null;
  }

  const deletedEntry = state.imageHistory.splice(state.historyIndex, 1)[0];
  if (!deletedEntry) {
    return null;
  }

  if (deletedEntry.blobUrl) {
    URL.revokeObjectURL(deletedEntry.blobUrl);
  }

  if (state.imageHistory.length === 0) {
    state.historyIndex = -1;
    showEmptyState();
    return deletedEntry;
  }

  if (state.historyIndex >= state.imageHistory.length) {
    state.historyIndex = state.imageHistory.length - 1;
  }

  const entry = state.imageHistory[state.historyIndex];
  if (entry) {
    displayImage(entry);
  }
  return deletedEntry;
}

/**
 * Get all retained image paths for multi-path exit.
 */
export function getAllRetainedPaths(state: AppState): string[] {
  return state.imageHistory
    .map(entry => entry.path)
    .filter((path): path is string => path !== null && path !== undefined);
}

/**
 * Get formatted position indicator string.
 */
export function getPositionIndicator(state: AppState): string {
  if (state.historyIndex < 0) {
    return '';
  }

  const current = state.historyIndex + 1;
  const total = state.imageHistory.length;
  return `[${current}]/${total}]`;
}
