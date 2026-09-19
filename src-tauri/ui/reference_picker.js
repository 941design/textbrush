// Pure selection rules. The Python references and model registry remain authoritative.
export const MAX_REFERENCES = 4;
export const SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg'];
// Mirrors textbrush/validation.py; the backend validates every update.
export const EDITING_PRESETS = [
    { id: 'landscape-small', width: 512, height: 384 },
    { id: 'landscape-medium', width: 768, height: 576 },
    { id: 'landscape-large', width: 1024, height: 768 },
    { id: 'portrait-small', width: 384, height: 512 },
    { id: 'portrait-medium', width: 576, height: 768 },
    { id: 'portrait-large', width: 768, height: 1024 },
];
// Mirrors textbrush/model/registry.py for pre-highlighting only.
export const MODELS = [
    { id: 'flux1-schnell', displayName: 'FLUX.1 [schnell]', minReferences: 0, maxReferences: 0 },
    { id: 'flux1-kontext-dev', displayName: 'FLUX.1 Kontext [dev]', minReferences: 1, maxReferences: 1 },
    { id: 'flux2-klein-4b', displayName: 'FLUX.2 [klein] 4B', minReferences: 1, maxReferences: 4 },
];
function basename(path) {
    return path.split(/[\\/]/).at(-1) || path;
}
function supported(path) {
    const lower = path.toLowerCase();
    return SUPPORTED_EXTENSIONS.some(extension => lower.endsWith(extension));
}
export function applyPickedPaths(current, picked) {
    const references = [...current];
    const errors = [];
    for (const path of picked) {
        if (!supported(path)) {
            errors.push(`${basename(path)}: supported formats are PNG, JPG, and JPEG`);
        }
        else if (references.length >= MAX_REFERENCES) {
            errors.push(`${basename(path)}: limit of ${MAX_REFERENCES} reference images`);
        }
        else {
            references.push(path);
        }
    }
    return { references, errors };
}
export function removeReference(current, index) {
    return current.filter((_, position) => position !== index);
}
export function replaceReference(current, index, path) {
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
export function previewLabel(path, position, total = MAX_REFERENCES) {
    return `Reference ${position + 1} of ${total}: ${basename(path)}`;
}
export function isEditingModel(modelId) {
    return (MODELS.find(model => model.id === modelId)?.maxReferences ?? 0) > 0;
}
export function compatibilityMessage(modelId, referenceCount) {
    const model = MODELS.find(entry => entry.id === modelId);
    if (!model)
        return modelId ? `unknown model: ${modelId}` : null;
    if (referenceCount >= model.minReferences && referenceCount <= model.maxReferences)
        return null;
    const rule = model.minReferences === model.maxReferences
        ? model.minReferences === 0 ? 'accepts no reference images' : `requires exactly ${model.minReferences} reference image`
        : `requires between ${model.minReferences} and ${model.maxReferences} reference images`;
    const noModel = referenceCount > MAX_REFERENCES ? `; no supported model accepts more than ${MAX_REFERENCES}` : '';
    return `${model.id} (${model.displayName}) ${rule}; got ${referenceCount}${noModel}`;
}
