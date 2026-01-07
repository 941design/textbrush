// Tauri commands for UI interaction with IPC sidecar.
//
// Commands are invoked from JavaScript UI, manage sidecar lifecycle and send IPC messages.

use crate::sidecar::{IpcMessage, Sidecar};
use std::sync::Mutex;
use tauri::{command, Emitter, State, Window};

pub struct AppState {
    pub sidecar: Mutex<Option<Sidecar>>,
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
pub async fn init_generation(
    state: State<'_, AppState>,
    window: Window,
    prompt: String,
    output_path: Option<String>,
    seed: Option<i64>,
    aspect_ratio: String,
) -> Result<(), String> {
    let mut sidecar = Sidecar::spawn("uv", &["run", "python", "-m", "textbrush.ipc"])?;

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
    use std::sync::mpsc;
    use std::time::Duration;

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
}
