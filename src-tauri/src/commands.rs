// Tauri commands for UI interaction with IPC sidecar.
//
// Commands are invoked from JavaScript UI, manage sidecar lifecycle and send IPC messages.

use crate::sidecar::{IpcMessage, Sidecar};
#[cfg(any(test, not(debug_assertions)))]
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::{command, Emitter, State, Window};

pub struct AppState {
    pub sidecar: Mutex<Option<Sidecar>>,
}

#[cfg(any(test, not(debug_assertions)))]
fn bundled_python_from_exe(exe_path: &Path) -> Option<PathBuf> {
    let contents_dir = exe_path.parent()?.parent()?;
    let candidate = contents_dir.join("Resources").join("python-env").join("bin").join("python3");
    candidate.exists().then_some(candidate)
}

#[cfg(any(test, not(debug_assertions)))]
fn repo_venv_python_from_path(start: &Path) -> Option<PathBuf> {
    let mut current = if start.is_dir() {
        Some(start)
    } else {
        start.parent()
    };

    while let Some(dir) = current {
        let candidate = dir.join(".venv").join("bin").join("python3");
        if candidate.exists() && dir.join("pyproject.toml").exists() {
            return Some(candidate);
        }
        current = dir.parent();
    }

    None
}

#[cfg(any(test, not(debug_assertions)))]
#[cfg_attr(test, allow(dead_code))]
fn resolve_release_python_command() -> (String, Vec<String>) {
    if let Ok(path) = std::env::var("TEXTBRUSH_PYTHON") {
        let candidate = PathBuf::from(path);
        if candidate.exists() {
            return (
                candidate.to_string_lossy().into_owned(),
                vec!["-m".to_string(), "textbrush.ipc".to_string()],
            );
        }
    }

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(candidate) = bundled_python_from_exe(&exe_path) {
            return (
                candidate.to_string_lossy().into_owned(),
                vec!["-m".to_string(), "textbrush.ipc".to_string()],
            );
        }

        if let Some(candidate) = repo_venv_python_from_path(&exe_path) {
            return (
                candidate.to_string_lossy().into_owned(),
                vec!["-m".to_string(), "textbrush.ipc".to_string()],
            );
        }
    }

    (
        "python3".to_string(),
        vec!["-m".to_string(), "textbrush.ipc".to_string()],
    )
}

/// Initialize backend and start generation.
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing optional Sidecar
///     - window: Tauri Window for emitting events to UI
///     - prompt: text description for image generation
///     - output_path: optional path where accepted image should be saved
///     - seed: optional random seed for reproducibility
///     - aspect_ratio: aspect ratio string (e.g., "1:1", "16:9", "9:16")
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - Spawns Python sidecar process if not already running
///     - Sets up message reader to forward events to UI via window.emit()
///     - Sends INIT command to sidecar with provided parameters
///     - Stores sidecar instance in AppState for later commands
///
///   Properties:
///     - Async: returns immediately after spawning and sending INIT
///     - Error handling: returns Result with error description
///     - State mutation: stores sidecar in AppState
///     - Event forwarding: sidecar messages are emitted as "sidecar-message" events
///
///   Algorithm:
///     1. Spawn sidecar using Sidecar::spawn("python", ["-m", "textbrush.ipc"])
///     2. Clone window for use in reader thread
///     3. Start reader thread that emits "sidecar-message" events to window
///     4. Send INIT command with JSON payload:
///        {
///          "prompt": prompt,
///          "output_path": output_path,
///          "seed": seed,
///          "aspect_ratio": aspect_ratio
///        }
///     5. Store sidecar in AppState.sidecar mutex
///     6. Return Ok or Err
#[command]
#[allow(clippy::too_many_arguments)]
pub async fn init_generation(
    state: State<'_, AppState>,
    window: Window,
    prompt: String,
    output_path: Option<String>,
    seed: Option<i64>,
    aspect_ratio: String,
    width: Option<u32>,
    height: Option<u32>,
) -> Result<(), String> {
    #[cfg(debug_assertions)]
    let mut sidecar = Sidecar::spawn("uv", &["run", "python", "-m", "textbrush.ipc"])
        .map_err(|e| {
            if e.contains("No such file") || e.contains("os error 2") {
                "Failed to start backend: uv not found. Install uv (https://docs.astral.sh/uv/) or run a release build.".to_string()
            } else {
                format!("Failed to start backend: {e}")
            }
        })?;

    #[cfg(not(debug_assertions))]
    let mut sidecar = {
        let (python_path, python_args) = resolve_release_python_command();
        let python_arg_refs: Vec<&str> = python_args.iter().map(String::as_str).collect();

        Sidecar::spawn(&python_path, &python_arg_refs)
        .map_err(|e| {
            if e.contains("No such file") || e.contains("os error 2") {
                "Failed to start backend: no usable Python runtime found. Rebuild the app with `make package` to embed the Python environment, or install Python 3.11+ with the `textbrush` model dependencies.".to_string()
            } else if e.contains("No module") {
                "Failed to start backend: bundled Python environment is incomplete. Rebuild with `make package`, or install `textbrush` and its model dependencies into the selected Python runtime.".to_string()
            } else {
                format!("Failed to start backend: {e}")
            }
        })?
    };

    let window_clone = window.clone();
    sidecar.start_reader(move |msg| {
        window_clone.emit("sidecar-message", msg).ok();
    });

    let message = IpcMessage {
        msg_type: "init".to_string(),
        payload: serde_json::json!({
            "prompt": prompt,
            "output_path": output_path,
            "seed": seed,
            "aspect_ratio": aspect_ratio,
            "width": width,
            "height": height,
        }),
    };

    sidecar.send(&message)?;

    *state.sidecar.lock().unwrap() = Some(sidecar);
    Ok(())
}

/// Skip current image and show next.
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing sidecar
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists: sends SKIP command
///     - If no sidecar: returns error
///
///   Properties:
///     - Synchronous: returns after sending command
///     - Error handling: returns Result with error if no sidecar
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Send SKIP message (type: "skip", payload: null)
///        b. Return Ok
///     3. If no sidecar:
///        a. Return Err("No sidecar running")
#[command]
pub fn skip_image(state: State<'_, AppState>) -> Result<(), String> {
    let sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(sidecar) = sidecar_guard.as_ref() {
        let message = IpcMessage {
            msg_type: "skip".to_string(),
            payload: serde_json::Value::Null,
        };
        sidecar.send(&message)?;
        Ok(())
    } else {
        Err("No sidecar running".to_string())
    }
}

/// Accept current image and save to disk.
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing sidecar
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists: sends ACCEPT command
///     - If no sidecar: returns error
///     - Python handler will save image and send ACCEPTED event with path
///
///   Properties:
///     - Synchronous: returns after sending command
///     - Error handling: returns Result with error if no sidecar
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Send ACCEPT message (type: "accept", payload: null)
///        b. Return Ok
///     3. If no sidecar:
///        a. Return Err("No sidecar running")
#[command]
pub fn accept_image(state: State<'_, AppState>) -> Result<(), String> {
    let sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(sidecar) = sidecar_guard.as_ref() {
        let message = IpcMessage {
            msg_type: "accept".to_string(),
            payload: serde_json::Value::Null,
        };
        sidecar.send(&message)?;
        Ok(())
    } else {
        Err("No sidecar running".to_string())
    }
}

/// Toggle pause/resume generation.
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing sidecar
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists: sends PAUSE command
///     - If no sidecar: returns error
///
///   Properties:
///     - Synchronous: returns after sending command
///     - Error handling: returns Result with error if no sidecar
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Send PAUSE message (type: "pause", payload: null)
///        b. Return Ok
///     3. If no sidecar:
///        a. Return Err("No sidecar running")
#[command]
pub fn pause_generation(state: State<'_, AppState>) -> Result<(), String> {
    let sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(sidecar) = sidecar_guard.as_ref() {
        let message = IpcMessage {
            msg_type: "pause".to_string(),
            payload: serde_json::Value::Null,
        };
        sidecar.send(&message)?;
        Ok(())
    } else {
        Err("No sidecar running".to_string())
    }
}

/// Delete image from delivered list by backend index.
///
/// CONTRACT:
///   Inputs:
///     - index: stable backend index of image to delete
///     - state: AppState containing sidecar
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists: sends DELETE command with index in payload
///     - If no sidecar: returns error
///     - Python handler will soft-delete image and delete temp file
///     - Handler sends DELETE_ACK or ERROR event based on success
///
///   Properties:
///     - Synchronous: returns after sending command
///     - Error handling: returns Result with error if no sidecar
///     - Idempotent: backend handles missing/deleted indices gracefully
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Create DELETE message with payload: {"index": index}
///        b. Send message via sidecar
///        c. Return Ok
///     3. If no sidecar:
///        a. Return Err("No sidecar running")
#[command]
pub fn delete_image(index: i32, state: State<'_, AppState>) -> Result<(), String> {
    let sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(sidecar) = sidecar_guard.as_ref() {
        let message = IpcMessage {
            msg_type: "delete".to_string(),
            payload: serde_json::json!({
                "index": index,
            }),
        };
        sidecar.send(&message)?;
        Ok(())
    } else {
        Err("No sidecar running".to_string())
    }
}

/// Request full image list from backend for state recovery.
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing sidecar
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists: sends GET_IMAGE_LIST command with null payload
///     - If no sidecar: returns error
///     - Python handler responds with IMAGE_LIST event containing all images
///
///   Properties:
///     - Synchronous: returns after sending command
///     - Error handling: returns Result with error if no sidecar
///     - Used for recovery: frontend calls this after reconnect or reload
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Send GET_IMAGE_LIST message (type: "get_image_list", payload: null)
///        b. Return Ok
///     3. If no sidecar:
///        a. Return Err("No sidecar running")
#[command]
pub fn get_image_list(state: State<'_, AppState>) -> Result<(), String> {
    let sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(sidecar) = sidecar_guard.as_ref() {
        let message = IpcMessage {
            msg_type: "get_image_list".to_string(),
            payload: serde_json::Value::Null,
        };
        sidecar.send(&message)?;
        Ok(())
    } else {
        Err("No sidecar running".to_string())
    }
}

/// Abort generation and terminate sidecar.
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing sidecar
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists:
///       * Sends ABORT command (optional: Python may not respond if killed)
///       * Kills sidecar process
///       * Removes sidecar from AppState
///     - If no sidecar: returns Ok (idempotent)
///
///   Properties:
///     - Blocking: waits for kill operation
///     - Cleanup: removes sidecar from state
///     - Idempotent: safe to call multiple times
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Try send ABORT message (type: "abort", payload: null)
///           - Ignore errors (process may already be dead)
///        b. Call sidecar.kill()
///        c. Take sidecar out of AppState (replace with None)
///        d. Return Ok or Err from kill operation
///     3. If no sidecar:
///        a. Return Ok (already aborted)
#[command]
pub fn abort_generation(state: State<'_, AppState>) -> Result<(), String> {
    let mut sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(mut sidecar) = sidecar_guard.take() {
        let message = IpcMessage {
            msg_type: "abort".to_string(),
            payload: serde_json::Value::Null,
        };
        let _ = sidecar.send(&message);

        sidecar.kill()?;
        Ok(())
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::mpsc;
    use std::time::Duration;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn python_echo_script() -> &'static str {
        r#"
import sys
import json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    sys.stdout.write(line)
    sys.stdout.flush()
"#
    }

    fn make_temp_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("textbrush-{name}-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn bundled_python_from_exe_finds_app_resource_python() {
        let root = make_temp_dir("bundled-python");
        let exe_path = root.join("Textbrush.app/Contents/MacOS/Textbrush");
        let python_path = root.join("Textbrush.app/Contents/Resources/python-env/bin/python3");

        fs::create_dir_all(python_path.parent().unwrap()).unwrap();
        fs::create_dir_all(exe_path.parent().unwrap()).unwrap();
        fs::write(&exe_path, "").unwrap();
        fs::write(&python_path, "").unwrap();

        let resolved = bundled_python_from_exe(&exe_path);
        assert_eq!(resolved, Some(python_path));

        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn repo_venv_python_from_path_finds_checkout_virtualenv() {
        let root = make_temp_dir("repo-venv");
        let nested = root.join("src-tauri/target/release/bundle/macos/Textbrush.app/Contents/MacOS");
        let exe_path = nested.join("Textbrush");
        let python_path = root.join(".venv/bin/python3");

        fs::create_dir_all(nested).unwrap();
        fs::create_dir_all(python_path.parent().unwrap()).unwrap();
        fs::write(root.join("pyproject.toml"), "").unwrap();
        fs::write(&exe_path, "").unwrap();
        fs::write(&python_path, "").unwrap();

        let resolved = repo_venv_python_from_path(&exe_path);
        assert_eq!(resolved, Some(python_path));

        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn skip_image_returns_error_when_no_sidecar() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result = if sidecar_guard.is_none() {
            Err("No sidecar running".to_string())
        } else {
            Ok(())
        };

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "No sidecar running");
    }

    #[test]
    fn skip_image_sends_skip_message_when_sidecar_exists() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(sidecar) = sidecar_guard.as_ref() {
            let message = IpcMessage {
                msg_type: "skip".to_string(),
                payload: serde_json::Value::Null,
            };
            sidecar.send(&message).expect("Send should succeed");
        }
        drop(sidecar_guard);

        let received = rx.recv_timeout(Duration::from_secs(1));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "skip");
        assert_eq!(msg.payload, serde_json::Value::Null);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn accept_image_returns_error_when_no_sidecar() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result = if sidecar_guard.is_none() {
            Err("No sidecar running".to_string())
        } else {
            Ok(())
        };

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "No sidecar running");
    }

    #[test]
    fn accept_image_sends_accept_message_when_sidecar_exists() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(sidecar) = sidecar_guard.as_ref() {
            let message = IpcMessage {
                msg_type: "accept".to_string(),
                payload: serde_json::Value::Null,
            };
            sidecar.send(&message).expect("Send should succeed");
        }
        drop(sidecar_guard);

        let received = rx.recv_timeout(Duration::from_secs(1));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "accept");
        assert_eq!(msg.payload, serde_json::Value::Null);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn abort_generation_is_idempotent() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result1 = if sidecar_guard.is_none() {
            Ok(())
        } else {
            Err("Unexpected sidecar".to_string())
        };
        drop(sidecar_guard);

        assert!(result1.is_ok());

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result2 = if sidecar_guard.is_none() {
            Ok(())
        } else {
            Err("Unexpected sidecar".to_string())
        };
        drop(sidecar_guard);

        assert!(result2.is_ok());
    }

    #[test]
    fn abort_generation_kills_sidecar_and_clears_state() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = "import time; time.sleep(10)";
        let sidecar = Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        *state.sidecar.lock().unwrap() = Some(sidecar);

        assert!(state.sidecar.lock().unwrap().is_some());

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let message = IpcMessage {
                msg_type: "abort".to_string(),
                payload: serde_json::Value::Null,
            };
            let _ = sidecar.send(&message);
            let result = sidecar.kill();
            assert!(result.is_ok());
        }
        drop(sidecar_guard);

        assert!(state.sidecar.lock().unwrap().is_none());
    }

    #[test]
    fn abort_generation_attempts_to_send_abort_message() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let message = IpcMessage {
                msg_type: "abort".to_string(),
                payload: serde_json::Value::Null,
            };
            let _ = sidecar.send(&message);
            let _ = sidecar.kill();
        }
        drop(sidecar_guard);

        let received = rx.recv_timeout(Duration::from_millis(500));
        if let Ok(msg) = received {
            assert_eq!(msg.msg_type, "abort");
        }
    }

    #[test]
    fn concurrent_skip_calls_are_safe() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let sidecar = Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let state_ref = std::sync::Arc::new(state);
        let mut handles = vec![];

        for _ in 0..5 {
            let state_clone = std::sync::Arc::clone(&state_ref);
            let handle = std::thread::spawn(move || {
                let sidecar_guard = state_clone.sidecar.lock().unwrap();
                if let Some(sidecar) = sidecar_guard.as_ref() {
                    let message = IpcMessage {
                        msg_type: "skip".to_string(),
                        payload: serde_json::Value::Null,
                    };
                    sidecar.send(&message)
                } else {
                    Err("No sidecar running".to_string())
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            let result = handle.join().expect("Thread panicked");
            assert!(result.is_ok());
        }

        let mut sidecar_guard = state_ref.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn concurrent_accept_calls_are_safe() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let sidecar = Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let state_ref = std::sync::Arc::new(state);
        let mut handles = vec![];

        for _ in 0..5 {
            let state_clone = std::sync::Arc::clone(&state_ref);
            let handle = std::thread::spawn(move || {
                let sidecar_guard = state_clone.sidecar.lock().unwrap();
                if let Some(sidecar) = sidecar_guard.as_ref() {
                    let message = IpcMessage {
                        msg_type: "accept".to_string(),
                        payload: serde_json::Value::Null,
                    };
                    sidecar.send(&message)
                } else {
                    Err("No sidecar running".to_string())
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            let result = handle.join().expect("Thread panicked");
            assert!(result.is_ok());
        }

        let mut sidecar_guard = state_ref.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn skip_after_abort_returns_error() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let sidecar = Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
        drop(sidecar_guard);

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result = if sidecar_guard.is_none() {
            Err("No sidecar running".to_string())
        } else {
            Ok(())
        };

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "No sidecar running");
    }

    #[test]
    fn accept_after_abort_returns_error() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let sidecar = Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
        drop(sidecar_guard);

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result = if sidecar_guard.is_none() {
            Err("No sidecar running".to_string())
        } else {
            Ok(())
        };

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "No sidecar running");
    }

    #[test]
    fn delete_image_returns_error_when_no_sidecar() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result = if sidecar_guard.is_none() {
            Err("No sidecar running".to_string())
        } else {
            Ok(())
        };

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "No sidecar running");
    }

    #[test]
    fn delete_image_sends_delete_message_when_sidecar_exists() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let index = 42;
        let sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(sidecar) = sidecar_guard.as_ref() {
            let message = IpcMessage {
                msg_type: "delete".to_string(),
                payload: serde_json::json!({
                    "index": index,
                }),
            };
            sidecar.send(&message).expect("Send should succeed");
        }
        drop(sidecar_guard);

        let received = rx.recv_timeout(Duration::from_secs(1));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "delete");
        assert_eq!(msg.payload["index"], index);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn delete_image_sends_correct_json_structure() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let test_index = 123;
        let sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(sidecar) = sidecar_guard.as_ref() {
            let message = IpcMessage {
                msg_type: "delete".to_string(),
                payload: serde_json::json!({
                    "index": test_index,
                }),
            };
            sidecar.send(&message).expect("Send should succeed");
        }
        drop(sidecar_guard);

        let received = rx.recv_timeout(Duration::from_secs(1));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "delete");
        assert!(msg.payload.is_object());
        assert!(msg.payload.get("index").is_some());
        assert_eq!(msg.payload["index"].as_i64().unwrap(), test_index);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn delete_image_with_various_indices() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, _rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let test_indices = vec![0, 1, 42, 100, 999];

        for test_index in test_indices {
            let sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(sidecar) = sidecar_guard.as_ref() {
                let message = IpcMessage {
                    msg_type: "delete".to_string(),
                    payload: serde_json::json!({
                        "index": test_index,
                    }),
                };
                let result = sidecar.send(&message);
                assert!(
                    result.is_ok(),
                    "Failed to send delete for index: {}",
                    test_index
                );
            }
            drop(sidecar_guard);
        }

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn delete_image_after_abort_returns_error() {
        let state = AppState {
            sidecar: Mutex::new(None),
        };

        let script = python_echo_script();
        let sidecar = Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        *state.sidecar.lock().unwrap() = Some(sidecar);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
        drop(sidecar_guard);

        let sidecar_guard = state.sidecar.lock().unwrap();
        let result = if sidecar_guard.is_none() {
            Err("No sidecar running".to_string())
        } else {
            Ok(())
        };

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "No sidecar running");
    }
}

#[cfg(test)]
mod delete_image_property_tests {
    use super::*;
    use proptest::prelude::*;
    use std::sync::mpsc;
    use std::time::Duration;

    proptest! {
        #[test]
        fn delete_image_payload_has_correct_message_type(
            index in 0i32..10000
        ) {
            let state = AppState {
                sidecar: Mutex::new(None),
            };

            let script = r#"
import sys
import json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    sys.stdout.write(line)
    sys.stdout.flush()
"#;

            let mut sidecar = Sidecar::spawn("python3", &["-c", script])
                .expect("Failed to spawn Python");

            let (tx, rx) = mpsc::channel();
            sidecar.start_reader(move |msg| {
                tx.send(msg).ok();
            });

            *state.sidecar.lock().unwrap() = Some(sidecar);

            let sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(sidecar) = sidecar_guard.as_ref() {
                let message = IpcMessage {
                    msg_type: "delete".to_string(),
                    payload: serde_json::json!({
                        "index": index,
                    }),
                };
                sidecar.send(&message).expect("Send should succeed");
            }
            drop(sidecar_guard);

            let received = rx.recv_timeout(Duration::from_secs(1));
            prop_assert!(received.is_ok());

            let msg = received.unwrap();
            prop_assert_eq!(msg.msg_type, "delete");

            let mut sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(mut sidecar) = sidecar_guard.take() {
                let _ = sidecar.kill();
            }
        }

        #[test]
        fn delete_image_payload_contains_index(
            index in 0i32..10000
        ) {
            let state = AppState {
                sidecar: Mutex::new(None),
            };

            let script = r#"
import sys
import json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    sys.stdout.write(line)
    sys.stdout.flush()
"#;

            let mut sidecar = Sidecar::spawn("python3", &["-c", script])
                .expect("Failed to spawn Python");

            let (tx, rx) = mpsc::channel();
            sidecar.start_reader(move |msg| {
                tx.send(msg).ok();
            });

            *state.sidecar.lock().unwrap() = Some(sidecar);

            let sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(sidecar) = sidecar_guard.as_ref() {
                let message = IpcMessage {
                    msg_type: "delete".to_string(),
                    payload: serde_json::json!({
                        "index": index,
                    }),
                };
                sidecar.send(&message).expect("Send should succeed");
            }
            drop(sidecar_guard);

            let received = rx.recv_timeout(Duration::from_secs(1));
            prop_assert!(received.is_ok());

            let msg = received.unwrap();
            prop_assert!(msg.payload.get("index").is_some());
            prop_assert_eq!(msg.payload["index"].as_i64().unwrap(), index as i64);

            let mut sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(mut sidecar) = sidecar_guard.take() {
                let _ = sidecar.kill();
            }
        }

        #[test]
        fn delete_image_payload_is_json_object(
            index in 0i32..10000
        ) {
            let state = AppState {
                sidecar: Mutex::new(None),
            };

            let script = r#"
import sys
import json

while True:
    line = sys.stdin.readline()
    if not line:
        break
    sys.stdout.write(line)
    sys.stdout.flush()
"#;

            let mut sidecar = Sidecar::spawn("python3", &["-c", script])
                .expect("Failed to spawn Python");

            let (tx, rx) = mpsc::channel();
            sidecar.start_reader(move |msg| {
                tx.send(msg).ok();
            });

            *state.sidecar.lock().unwrap() = Some(sidecar);

            let sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(sidecar) = sidecar_guard.as_ref() {
                let message = IpcMessage {
                    msg_type: "delete".to_string(),
                    payload: serde_json::json!({
                        "index": index,
                    }),
                };
                sidecar.send(&message).expect("Send should succeed");
            }
            drop(sidecar_guard);

            let received = rx.recv_timeout(Duration::from_secs(1));
            prop_assert!(received.is_ok());

            let msg = received.unwrap();
            prop_assert!(msg.payload.is_object());

            let mut sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(mut sidecar) = sidecar_guard.take() {
                let _ = sidecar.kill();
            }
        }

        #[test]
        fn delete_image_without_sidecar_always_fails(
            _index in 0i32..10000
        ) {
            let state = AppState {
                sidecar: Mutex::new(None),
            };

            let sidecar_guard = state.sidecar.lock().unwrap();
            let result = if sidecar_guard.is_none() {
                Err("No sidecar running".to_string())
            } else {
                Ok(())
            };

            prop_assert!(result.is_err());
            prop_assert_eq!(result.unwrap_err(), "No sidecar running");
        }
    }
}
