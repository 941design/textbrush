// Image History Navigation and Management
// Extends main.js navigation to support bidirectional navigation and deletion

import type { ImageRecord, AppState } from './types';

type DisplayImageCallback = (record: ImageRecord) => void;
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
  const record = state.imageHistory[state.historyIndex];
  if (record) {
    displayImage(record);
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
    const record = state.imageHistory[state.historyIndex];
    if (record) {
      displayImage(record);
    }
    return true;
  }

  // At end of history - always request next image (let backend decide from buffer or generate)
  requestNextImage();
  return true;
}

/**
 * Delete current image from history and navigate away.
 * Note: Asset URLs from convertFileSrc don't need revoking.
 */
export function deleteCurrentImage(
  state: AppState,
  displayImage: DisplayImageCallback,
  showEmptyState: ShowEmptyStateCallback
): ImageRecord | null {
  if (state.historyIndex < 0 || state.historyIndex >= state.imageHistory.length) {
    return null;
  }

  const deletedRecord = state.imageHistory.splice(state.historyIndex, 1)[0];
  if (!deletedRecord) {
    return null;
  }

  // Note: Asset URLs from convertFileSrc don't need revoking like blob URLs

  if (state.imageHistory.length === 0) {
    state.historyIndex = -1;
    showEmptyState();
    return deletedRecord;
  }

  if (state.historyIndex >= state.imageHistory.length) {
    state.historyIndex = state.imageHistory.length - 1;
  }

  const record = state.imageHistory[state.historyIndex];
  if (record) {
    displayImage(record);
  }
  return deletedRecord;
}

/**
 * Get all accepted image output paths for multi-path exit.
 * Only returns paths for images that have been accepted (have outputPath set).
 */
export function getAllRetainedPaths(state: AppState): string[] {
  return state.imageHistory
    .map(record => record.outputPath)
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
