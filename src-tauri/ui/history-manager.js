// Image History Navigation and Management
// Extends main.js navigation to support bidirectional navigation and deletion

/**
 * Navigate to previous image in history.
 *
 * CONTRACT:
 *   Inputs:
 *     - state: Application state object with imageHistory and historyIndex
 *       {
 *         imageHistory: Array<{image_data: string, seed: number, blobUrl: string}>,
 *         historyIndex: number (current position, -1 if empty)
 *       }
 *     - displayImage: Function to display image from history entry
 *
 *   Outputs: Boolean (true if navigated, false if at beginning)
 *
 *   Invariants:
 *     - If historyIndex > 0: decrements index and displays previous image
 *     - If historyIndex <= 0: no-op, returns false (at beginning)
 *     - Never modifies history array (read-only navigation)
 *     - Updates state.historyIndex on successful navigation
 *
 *   Properties:
 *     - Boundary safe: handles historyIndex = 0 gracefully
 *     - Idempotent at boundary: calling at index 0 repeatedly is safe
 *     - Display coordination: calls displayImage with history entry
 *     - Index integrity: historyIndex always valid for imageHistory array
 *
 *   Algorithm:
 *     1. Check if state.historyIndex <= 0
 *     2. If yes: return false (cannot go back further)
 *     3. Decrement state.historyIndex by 1
 *     4. Get entry at imageHistory[historyIndex]
 *     5. Call displayImage(entry)
 *     6. Return true
 */
export function navigateToPrevious(state, displayImage) {
  if (state.historyIndex <= 0) {
    return false;
  }

  state.historyIndex--;
  const entry = state.imageHistory[state.historyIndex];
  displayImage(entry);
  return true;
}

/**
 * Navigate to next image in history or request from buffer.
 *
 * CONTRACT:
 *   Inputs:
 *     - state: Application state object with imageHistory, historyIndex, bufferCount
 *     - displayImage: Function to display image from history entry
 *     - requestNextImage: Function to request new image from backend buffer
 *
 *   Outputs: Boolean (true if navigated/requested, false if error)
 *
 *   Invariants:
 *     - If historyIndex < (historyLength - 1): navigates forward in history
 *     - If at end of history AND bufferCount > 0: requests new image from buffer
 *     - If at end and no buffer: no-op, returns false
 *     - Never modifies history array during navigation
 *     - Updates state.historyIndex on forward navigation
 *
 *   Properties:
 *     - Dual mode: history navigation OR buffer request
 *     - Boundary handling: gracefully handles end of history
 *     - Buffer awareness: checks bufferCount before requesting
 *     - Forward-only from buffer: new images always append to history
 *
 *   Algorithm:
 *     1. Check if historyIndex < (imageHistory.length - 1)
 *     2. If yes:
 *        a. Increment historyIndex
 *        b. Get entry at imageHistory[historyIndex]
 *        c. Call displayImage(entry)
 *        d. Return true
 *     3. If no (at end of history):
 *        a. Call requestNextImage() to get more images (backend decides buffer vs generate)
 *        b. Return true
 */
export function navigateToNext(state, displayImage, requestNextImage) {
  if (state.historyIndex < state.imageHistory.length - 1) {
    state.historyIndex++;
    const entry = state.imageHistory[state.historyIndex];
    displayImage(entry);
    return true;
  }

  // At end of history - always request next image (let backend decide from buffer or generate)
  requestNextImage();
  return true;
}

/**
 * Delete current image from history and navigate away.
 *
 * CONTRACT:
 *   Inputs:
 *     - state: Application state object with imageHistory, historyIndex
 *     - displayImage: Function to display image after deletion
 *     - showEmptyState: Function to show empty viewer state
 *
 *   Outputs:
 *     - deletedEntry: Object {image_data, seed, blobUrl} that was removed, or null if nothing to delete
 *
 *   Invariants:
 *     - If historyIndex >= 0 and < historyLength:
 *       * Removes entry at historyIndex from imageHistory array
 *       * Revokes Blob URL to free memory
 *       * Navigates to next logical position
 *     - If all images deleted: calls showEmptyState()
 *     - Updates state.historyIndex to valid position after deletion
 *
 *   Properties:
 *     - Memory safe: revokes Blob URLs via URL.revokeObjectURL()
 *     - Navigation priority: tries next image, falls back to previous, then empty
 *     - Array mutation: removes exactly one element via splice
 *     - Index correction: adjusts historyIndex after splice operation
 *
 *   Algorithm:
 *     1. Check if historyIndex valid (>= 0 and < historyLength)
 *     2. If invalid: return null
 *     3. Get entry at imageHistory[historyIndex]
 *     4. Remove entry via imageHistory.splice(historyIndex, 1)
 *     5. If entry.blobUrl exists: call URL.revokeObjectURL(entry.blobUrl)
 *     6. Determine new position:
 *        a. If imageHistory now empty: call showEmptyState(), set historyIndex = -1
 *        b. If deleted from middle/beginning and images remain:
 *           - Keep same index (now points to next image)
 *           - Call displayImage(imageHistory[historyIndex])
 *        c. If deleted last image:
 *           - Set historyIndex = imageHistory.length - 1
 *           - Call displayImage(imageHistory[historyIndex])
 *     7. Return deleted entry
 */
export function deleteCurrentImage(state, displayImage, showEmptyState) {
  if (state.historyIndex < 0 || state.historyIndex >= state.imageHistory.length) {
    return null;
  }

  const deletedEntry = state.imageHistory.splice(state.historyIndex, 1)[0];

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

  displayImage(state.imageHistory[state.historyIndex]);
  return deletedEntry;
}

/**
 * Get all retained image paths for multi-path exit.
 *
 * CONTRACT:
 *   Inputs:
 *     - state: Application state object with imageHistory
 *
 *   Outputs: Array<string> of image paths (may be empty)
 *
 *   Invariants:
 *     - Returns paths for all images currently in history
 *     - Paths are absolute file system paths (from backend ACCEPTED events)
 *     - Order matches history order
 *     - Empty array if no images in history
 *
 *   Properties:
 *     - Read-only: does not modify state
 *     - Path extraction: gets path from each history entry
 *     - Filter valid: only includes entries with non-null paths
 *
 *   Algorithm:
 *     1. Map over imageHistory array
 *     2. For each entry: extract entry.path (if exists)
 *     3. Filter out null/undefined paths
 *     4. Return array of paths
 *
 *   NOTE: This requires tracking paths in history entries.
 *         History entries must be extended to include path field when image is saved.
 */
export function getAllRetainedPaths(state) {
  return state.imageHistory
    .map(entry => entry.path)
    .filter(path => path !== null && path !== undefined);
}

/**
 * Get formatted position indicator string.
 *
 * CONTRACT:
 *   Inputs:
 *     - state: Application state object with imageHistory, historyIndex
 *
 *   Outputs: String in format "[current]/[total]" or "" if no history
 *
 *   Invariants:
 *     - If history empty: returns empty string
 *     - current = historyIndex + 1 (1-indexed for display)
 *     - total = imageHistory.length
 *     - Format: "[N]/[M]" where N ≤ M
 *
 *   Properties:
 *     - 1-indexed: user-facing indices start at 1, not 0
 *     - Empty safe: returns "" if historyIndex < 0
 *     - Consistent format: always "[N]/[M]" when history exists
 *
 *   Algorithm:
 *     1. If historyIndex < 0: return ""
 *     2. Calculate current = historyIndex + 1
 *     3. Calculate total = imageHistory.length
 *     4. Return `[${current}]/${total}]`
 */
export function getPositionIndicator(state) {
  if (state.historyIndex < 0) {
    return '';
  }

  const current = state.historyIndex + 1;
  const total = state.imageHistory.length;
  return `[${current}]/${total}]`;
}
