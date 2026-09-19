// Tauri bridge stub for the headless-browser accessibility harness.
//
// The desktop UI imports invoke / listen / convertFileSrc from
// @tauri-apps/api/* (core and event). The harness aliases those modules to
// this file so the production bundle can run unmodified in a real browser
// without a Tauri sidecar.
//
// Stub contract:
//   - invoke records calls and returns canned results. pick_reference_files
//     reads the path list the test injected via window.__a11yPaths.
//   - listen stores handlers on window.__a11yEmit(type, payload) so tests
//     can dispatch state_changed and config_ack.
//   - convertFileSrc returns a data URL of a 1x1 PNG.

declare global {
  interface Window {
    __a11yPaths?: string[];
    __a11yEmit?: (type: string, payload: unknown) => void;
    __a11yInvokeCalls?: string[];
  }
}

const TRANSPARENT_PNG_DATA_URL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

const handlers: Map<string, (event: { payload: unknown }) => void> = new Map();

export function convertFileSrc(path: string): string {
  return TRANSPARENT_PNG_DATA_URL;
}

export async function invoke<T = unknown>(
  command: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  if (window.__a11yInvokeCalls) {
    window.__a11yInvokeCalls.push(command);
  }
  if (command === 'pick_reference_files') {
    const paths = window.__a11yPaths ?? [];
    return paths as unknown as T;
  }
  if (command === 'get_launch_args') {
    return {
      prompt: '',
      aspect_ratio: '1:1',
      buffer_max: 8,
      output_path: null,
      seed: null,
      width: 1024,
      height: 1024,
      model_id: null,
      references: null,
      preset: null,
    } as unknown as T;
  }
  return null as unknown as T;
}

export async function listen<T = unknown>(
  event: string,
  callback: (event: { payload: T }) => void,
): Promise<() => void> {
  handlers.set(event, callback as (event: { payload: unknown }) => void);
  if (!window.__a11yEmit) {
    window.__a11yEmit = (type: string, payload: unknown) => {
      const handler = handlers.get('sidecar-message');
      if (handler) {
        handler({ payload: { type, payload } });
      }
    };
  }
  return () => {
    handlers.delete(event);
  };
}

export function getCurrentWindow(): { close: () => Promise<void> } {
  return {
    close: async () => {
      // no-op in headless harness
    },
  };
}
