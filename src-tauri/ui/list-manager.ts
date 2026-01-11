// Image List Navigation and Management
// Extends main.js navigation to support bidirectional navigation and deletion

import type { ImageRecord, AppState } from './types';

type DisplayImageCallback = (record: ImageRecord) => void;
type RequestNextImageCallback = () => void;

/**
 * Navigate to previous image in list.
 */
export function navigateToPrev(
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
 * Get formatted position indicator string.
 */
export function getPositionIndicator(state: AppState): string {
  if (state.currentIndex < 0) {
    return '';
  }

  const current = state.currentIndex + 1;
  const total = state.imageList.length;
  return `[${current}/${total}]`;
}
