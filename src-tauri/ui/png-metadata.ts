// PNG Metadata Parser Module
// Extracts metadata from PNG tEXt chunks using ExifReader

import ExifReader from 'exifreader';

/**
 * Parsed PNG metadata from Textbrush-generated images.
 *
 * CONTRACT:
 *   - All fields optional for backward compatibility with legacy images
 *   - generatedWidth/generatedHeight: dimensions passed to model (multiples of 16)
 *   - width/height: final image dimensions after cropping
 *   - If generatedWidth equals width, no cropping occurred
 */
export interface PngMetadata {
  prompt?: string;
  model?: string;
  seed?: number;
  aspectRatio?: string;
  width?: number;
  height?: number;
  generatedWidth?: number;
  generatedHeight?: number;
}

/**
 * Parse PNG metadata from an ArrayBuffer.
 *
 * CONTRACT:
 *   Inputs:
 *     - buffer: ArrayBuffer containing PNG file data
 *
 *   Outputs:
 *     - PngMetadata object with extracted fields (missing fields omitted)
 *
 *   Properties:
 *     - Safe: returns empty object if no metadata found
 *     - Non-throwing: catches errors and returns partial results
 *     - Parses tEXt chunks: Prompt, Model, Seed, AspectRatio, Width, Height,
 *       GeneratedWidth, GeneratedHeight
 */
export function parsePngMetadata(buffer: ArrayBuffer): PngMetadata {
  try {
    const tags = ExifReader.load(buffer);
    const result: PngMetadata = {};

    // Extract text chunks (stored as { value: string, description: string })
    const getText = (key: string): string | undefined => {
      const tag = tags[key];
      if (tag && typeof tag === 'object' && 'value' in tag) {
        return String(tag.value);
      }
      return undefined;
    };

    const getInt = (key: string): number | undefined => {
      const text = getText(key);
      if (text !== undefined) {
        const num = parseInt(text, 10);
        if (!isNaN(num)) {
          return num;
        }
      }
      return undefined;
    };

    // Map PNG tEXt chunk keys to metadata fields
    const prompt = getText('Prompt');
    if (prompt !== undefined) result.prompt = prompt;

    const model = getText('Model');
    if (model !== undefined) result.model = model;

    const seed = getInt('Seed');
    if (seed !== undefined) result.seed = seed;

    const aspectRatio = getText('AspectRatio');
    if (aspectRatio !== undefined) result.aspectRatio = aspectRatio;

    const width = getInt('Width');
    if (width !== undefined) result.width = width;

    const height = getInt('Height');
    if (height !== undefined) result.height = height;

    const generatedWidth = getInt('GeneratedWidth');
    if (generatedWidth !== undefined) result.generatedWidth = generatedWidth;

    const generatedHeight = getInt('GeneratedHeight');
    if (generatedHeight !== undefined) result.generatedHeight = generatedHeight;

    return result;
  } catch (error) {
    console.warn('Failed to parse PNG metadata:', error);
    return {};
  }
}

/**
 * Fetch a file and parse its PNG metadata.
 *
 * CONTRACT:
 *   Inputs:
 *     - url: URL to fetch (can be asset:// protocol or blob URL)
 *
 *   Outputs:
 *     - Promise<PngMetadata> with extracted fields
 *
 *   Properties:
 *     - Async: fetches file over network/filesystem
 *     - Non-throwing: catches fetch errors and returns empty object
 */
export async function fetchAndParsePngMetadata(url: string): Promise<PngMetadata> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.warn(`Failed to fetch PNG: ${response.status} ${response.statusText}`);
      return {};
    }
    const buffer = await response.arrayBuffer();
    return parsePngMetadata(buffer);
  } catch (error) {
    console.warn('Failed to fetch and parse PNG metadata:', error);
    return {};
  }
}
