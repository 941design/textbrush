// Pure selection rules. The Python references and model registry remain authoritative.
export const MAX_REFERENCES = 4;
export const SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg'] as const;

export interface ModelCapability {
  id: string;
  displayName: string;
  minReferences: number;
  maxReferences: number;
  available?: boolean;
}

// Mirrors textbrush/model/registry.py. Used before the backend's
// `model_list` event arrives; `adoptModelCapabilities` replaces it with
// the registry's own answer as soon as that event lands, so a model
// whose cardinality changes in the registry does not need this table
// edited to behave correctly at runtime.
//
// `minReferences: 0` with `maxReferences > 0` is the references-optional
// case: FLUX.2 klein generates from a prompt alone and ALSO accepts up
// to four references.
const DEFAULT_MODELS: ModelCapability[] = [
  { id: 'flux1-schnell', displayName: 'FLUX.1 [schnell]', minReferences: 0, maxReferences: 0 },
  { id: 'flux1-kontext-dev', displayName: 'FLUX.1 Kontext [dev]', minReferences: 1, maxReferences: 1 },
  { id: 'flux2-klein-4b', displayName: 'FLUX.2 [klein] 4B', minReferences: 0, maxReferences: 4 },
];

let models: ModelCapability[] = [...DEFAULT_MODELS];

/** Replace the mirror table with the backend's own model catalogue. */
export function adoptModelCapabilities(catalogue: ModelCapability[]): void {
  if (catalogue.length) {
    models = catalogue.map(entry => ({ ...entry }));
  }
}

export function modelCapabilities(): ModelCapability[] {
  return models;
}

export function modelCapability(modelId: string | null): ModelCapability | null {
  return models.find(entry => entry.id === modelId) ?? null;
}

/** How many reference images this model accepts at most; 0 means none. */
export function maxReferencesFor(modelId: string | null): number {
  return modelCapability(modelId)?.maxReferences ?? 0;
}

function basename(path: string): string {
  return path.split(/[\\/]/).at(-1) || path;
}

function supported(path: string): boolean {
  const lower = path.toLowerCase();
  return SUPPORTED_EXTENSIONS.some(extension => lower.endsWith(extension));
}

export function applyPickedPaths(
  current: string[],
  picked: string[],
  limit: number = MAX_REFERENCES,
): { references: string[]; errors: string[] } {
  const references = [...current];
  const errors: string[] = [];
  for (const path of picked) {
    if (!supported(path)) {
      errors.push(`${basename(path)}: supported formats are PNG, JPG, and JPEG`);
    } else if (references.length >= limit) {
      errors.push(`${basename(path)}: limit of ${limit} reference images`);
    } else {
      references.push(path);
    }
  }
  return { references, errors };
}

export function removeReference(current: string[], index: number): string[] {
  return current.filter((_, position) => position !== index);
}

export function replaceReference(current: string[], index: number, path: string): { references: string[]; errors: string[] } {
  if (index < 0 || index >= current.length) {
    return { references: [...current], errors: [`Reference ${index + 1} does not exist`] };
  }
  if (!supported(path)) {
    return { references: [...current], errors: [`${basename(path)}: supported formats are PNG, JPG, and JPEG`] };
  }
  const references = [...current];
  references[index] = path;
  return { references, errors: [] };
}

export function previewLabel(path: string, position: number, total = MAX_REFERENCES): string {
  return `Reference ${position + 1} of ${total}: ${basename(path)}`;
}

/**
 * True when the model ACCEPTS reference images.
 *
 * Accepting is not requiring: FLUX.2 klein answers true here and still
 * generates happily from a prompt alone. Code that needs "does this
 * model insist on a reference" must read `minReferences`.
 */
export function isEditingModel(modelId: string | null): boolean {
  return maxReferencesFor(modelId) > 0;
}

export function compatibilityMessage(modelId: string | null, referenceCount: number): string | null {
  const model = modelCapability(modelId);
  if (!model) return modelId ? `unknown model: ${modelId}` : null;
  if (referenceCount >= model.minReferences && referenceCount <= model.maxReferences) return null;
  const rule = model.minReferences === model.maxReferences
    ? model.minReferences === 0 ? 'accepts no reference images' : `requires exactly ${model.minReferences} reference image`
    : model.minReferences === 0
      ? `accepts up to ${model.maxReferences} reference images`
      : `requires between ${model.minReferences} and ${model.maxReferences} reference images`;
  const noModel = referenceCount > MAX_REFERENCES ? `; no supported model accepts more than ${MAX_REFERENCES}` : '';
  return `${model.id} (${model.displayName}) ${rule}; got ${referenceCount}${noModel}`;
}
