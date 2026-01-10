// Image List Navigation and Management
// Extends main.js navigation to support bidirectional navigation and deletion

import type { ImageRecord, AppState } from './types';

type DisplayImageCallback = (record: ImageRecord) => void;
type ShowEmptyStateCallback = () => void;
type RequestNextImageCallback = () => void;

/**
 * Navigate to previous image in list.
 */
export function navigateToPrevious(
  state: AppState,
  displayImage: DisplayImageCallback
): boolean {
  if (state.currentIndex <= 0) {
    return false;
  }

  state.currentIndex--;
  const record = state.imageList[state.currentIndex];
  if (record) {
    displayImage(record);
  }
  return true;
}

/**
 * Navigate to next image in list or request from buffer.
 */
export function navigateToNext(
  state: AppState,
  displayImage: DisplayImageCallback,
  requestNextImage: RequestNextImageCallback
): boolean {
  if (state.currentIndex < state.imageList.length - 1) {
    state.currentIndex++;
    const record = state.imageList[state.currentIndex];
    if (record) {
      displayImage(record);
    }
    return true;
  }

  // At end of list - always request next image (let backend decide from buffer or generate)
  requestNextImage();
  return true;
}

/**
 * Delete current image from list and navigate away.
 * Note: Asset URLs from convertFileSrc don't need revoking.
 */
export function deleteCurrentImage(
  state: AppState,
  displayImage: DisplayImageCallback,
  showEmptyState: ShowEmptyStateCallback
): ImageRecord | null {
  if (state.currentIndex < 0 || state.currentIndex >= state.imageList.length) {
    return null;
  }

  const deletedRecord = state.imageList.splice(state.currentIndex, 1)[0];
  if (!deletedRecord) {
    return null;
  }

  // Note: Asset URLs from convertFileSrc don't need revoking like blob URLs

  if (state.imageList.length === 0) {
    state.currentIndex = -1;
    showEmptyState();
    return deletedRecord;
  }

  if (state.currentIndex >= state.imageList.length) {
    state.currentIndex = state.imageList.length - 1;
  }

  const record = state.imageList[state.currentIndex];
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
  return state.imageList
    .map(record => record.outputPath)
    .filter((path): path is string => path !== null && path !== undefined);
}

/**
 * Get formatted position indicator string.
 */
export function getPositionIndicator(state: AppState): string {
  if (state.currentIndex < 0) {
    return '';
  }

  const current = state.currentIndex + 1;
  const total = state.imageList.length;
  return `[${current}]/${total}]`;
}
