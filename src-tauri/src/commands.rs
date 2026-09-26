// Tauri commands for UI interaction with IPC sidecar.
//
// Commands are invoked from JavaScript UI, manage sidecar lifecycle and send IPC messages.

use crate::sidecar::{IpcMessage, Sidecar};
use std::sync::Mutex;
use tauri::{command, Emitter, Manager, State, Window};

/// The exact JSON payload sent to Python, shared by production and bridge tests.
#[derive(serde::Serialize)]
struct InitPayload {
    prompt: String,
    output_path: Option<String>,
    seed: Option<i64>,
    aspect_ratio: String,
    width: Option<u32>,
    height: Option<u32>,
    model_id: Option<String>,
    references: Option<Vec<String>>,
    preset: Option<String>,
    buffer_max: Option<u32>,
}

impl InitPayload {
    fn into_message(self) -> IpcMessage {
        IpcMessage {
            msg_type: "init".into(),
            payload: serde_json::to_value(self).expect("INIT contains only JSON-safe values"),
        }
    }
}

#[derive(Default)]
pub struct AppState {
    pub sidecar: Mutex<Option<Sidecar>>,
    pub closing: std::sync::atomic::AtomicBool,
}

impl AppState {
    pub fn send(&self, message: &IpcMessage) -> Result<(), String> {
        let sender = {
            let guard = self.sidecar.lock().map_err(|e| e.to_string())?;
            if self.closing.load(std::sync::atomic::Ordering::SeqCst) {
                return Err("Application is closing".into());
            }
            guard.as_ref().ok_or("No sidecar running")?.sender()
        };
        // Never hold application ownership while writing a potentially full pipe.
        sender.send(message)
    }

    pub fn shutdown(&self) -> Result<(), String> {
        self.closing
            .store(true, std::sync::atomic::Ordering::SeqCst);
        // Serialize competing close/abort/accept exits until cleanup is complete.
        let mut guard = self.sidecar.lock().map_err(|e| e.to_string())?;
        if let Some(mut sidecar) = guard.take() {
            sidecar.shutdown(std::time::Duration::from_secs(5))?;
        }
        Ok(())
    }
}

/// Store the child before sending INIT so shutdown can reach a blocked pipe.
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
    model_id: Option<String>,
    references: Option<Vec<String>>,
    preset: Option<String>,
    buffer_max: Option<u32>,
) -> Result<(), String> {
    let mut sidecar_guard = state.sidecar.lock().map_err(|e| e.to_string())?;
    if state.closing.load(std::sync::atomic::Ordering::SeqCst) {
        return Err("Application is closing".into());
    }
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
        let configured = match std::env::var("TEXTBRUSH_PYTHON") {
            Ok(value) => Some(value),
            Err(std::env::VarError::NotPresent) => None,
            Err(_) => return Err("TEXTBRUSH_PYTHON must be valid UTF-8".into()),
        };
        crate::python_runtime::spawn(configured.as_deref())?
    };

    crate::asset_access::allow_previews(
        &window.asset_protocol_scope(),
        sidecar.preview_directory(),
    )?;
    let window_clone = window.clone();
    sidecar.start_reader(move |msg| {
        window_clone.emit("sidecar-message", msg).ok();
    });

    let message = InitPayload {
        prompt,
        output_path,
        seed,
        aspect_ratio,
        width,
        height,
        model_id,
        references,
        preset,
        buffer_max,
    }
    .into_message();

    let sender = sidecar.sender();
    *sidecar_guard = Some(sidecar);
    drop(sidecar_guard);
    sender.send(&message)
}

/// Dispatch skip without holding app-state ownership during the pipe write.
#[command]
pub async fn skip_image(state: State<'_, AppState>) -> Result<(), String> {
    let message = IpcMessage {
        msg_type: "skip".to_string(),
        payload: serde_json::Value::Null,
    };
    state.send(&message)
}

/// Dispatch acceptance; saved paths arrive asynchronously from Python.
#[command]
pub async fn accept_image(state: State<'_, AppState>) -> Result<(), String> {
    let message = IpcMessage {
        msg_type: "accept".to_string(),
        payload: serde_json::Value::Null,
    };
    state.send(&message)
}

/// Dispatch pause/resume; Python reports the settled worker state.
#[command]
pub async fn pause_generation(state: State<'_, AppState>) -> Result<(), String> {
    let message = IpcMessage {
        msg_type: "pause".to_string(),
        payload: serde_json::Value::Null,
    };
    state.send(&message)
}

/// Dispatch deletion by stable image index.
#[command]
pub async fn delete_image(index: i32, state: State<'_, AppState>) -> Result<(), String> {
    let message = IpcMessage {
        msg_type: "delete".to_string(),
        payload: serde_json::json!({
            "index": index,
        }),
    };
    state.send(&message)
}

/// Request the current list of delivered images.
#[command]
pub async fn get_image_list(state: State<'_, AppState>) -> Result<(), String> {
    let message = IpcMessage {
        msg_type: "get_image_list".to_string(),
        payload: serde_json::Value::Null,
    };
    state.send(&message)
}

/// Close the session with a five-second grace period, then kill/reap if necessary.
#[command]
pub async fn abort_generation(state: State<'_, AppState>) -> Result<(), String> {
    state.shutdown()
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
        let state = AppState::default();

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
        let state = AppState::default();

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
            sidecar
                .sender()
                .send(&message)
                .expect("Send should succeed");
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
        let state = AppState::default();

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
        let state = AppState::default();

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
            sidecar
                .sender()
                .send(&message)
                .expect("Send should succeed");
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
        let state = AppState::default();

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
        let state = AppState::default();

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
            let _ = sidecar.sender().send(&message);
            let result = sidecar.kill();
            assert!(result.is_ok());
        }
        drop(sidecar_guard);

        assert!(state.sidecar.lock().unwrap().is_none());
    }

    #[test]
    fn abort_generation_attempts_to_send_abort_message() {
        let state = AppState::default();

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
            let _ = sidecar.sender().send(&message);
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
        let state = AppState::default();

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
                    sidecar.sender().send(&message)
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
        let state = AppState::default();

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
                    sidecar.sender().send(&message)
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
        let state = AppState::default();

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
        let state = AppState::default();

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
        let state = AppState::default();

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
        let state = AppState::default();

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
            sidecar
                .sender()
                .send(&message)
                .expect("Send should succeed");
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
        let state = AppState::default();

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
            sidecar
                .sender()
                .send(&message)
                .expect("Send should succeed");
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
        let state = AppState::default();

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
                let result = sidecar.sender().send(&message);
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
        let state = AppState::default();

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
            let state = AppState::default();

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
                sidecar.sender().send(&message).expect("Send should succeed");
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
            let state = AppState::default();

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
                sidecar.sender().send(&message).expect("Send should succeed");
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
            let state = AppState::default();

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
                sidecar.sender().send(&message).expect("Send should succeed");
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
            let state = AppState::default();

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

#[cfg(test)]
mod init_bridge_tests {
    use super::*;

    #[test]
    fn init_serializes_native_options_exactly() {
        let message = InitPayload {
            prompt: "cat".into(),
            output_path: Some("/output path/cat.png".into()),
            seed: Some(0),
            aspect_ratio: "3:4".into(),
            width: Some(576),
            height: Some(768),
            model_id: Some("flux2-klein-4b".into()),
            references: Some(vec!["/a b.png".into(), "/c.png".into(), "/a b.png".into()]),
            preset: Some("portrait-medium".into()),
            buffer_max: Some(3),
        }
        .into_message();
        assert_eq!(message.msg_type, "init");
        assert_eq!(
            message.payload,
            serde_json::json!({
                "prompt": "cat", "output_path": "/output path/cat.png", "seed": 0,
                "aspect_ratio": "3:4", "width": 576, "height": 768,
                "model_id": "flux2-klein-4b", "references": ["/a b.png", "/c.png", "/a b.png"],
                "preset": "portrait-medium", "buffer_max": 3,
            })
        );
    }
}

#[cfg(test)]
mod shutdown_tests {
    use super::*;
    use std::sync::Arc;

    #[test]
    fn shutdown_can_reach_child_while_a_command_write_is_blocked() {
        let script = "import sys,json,time; sys.stdin.buffer.read(1); print(json.dumps({'type':'blocked','payload':{}}),flush=True); time.sleep(60)";
        let mut sidecar = Sidecar::spawn("python3", &["-c", script]).unwrap();
        let (tx, rx) = std::sync::mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });
        let state = Arc::new(AppState::default());
        *state.sidecar.lock().unwrap() = Some(sidecar);
        let writer_state = Arc::clone(&state);
        let writer = std::thread::spawn(move || {
            writer_state.send(&IpcMessage {
                msg_type: "update_config".into(),
                payload: serde_json::json!({"prompt": "x".repeat(1_000_000)}),
            })
        });
        assert_eq!(
            rx.recv_timeout(std::time::Duration::from_secs(3))
                .unwrap()
                .msg_type,
            "blocked"
        );
        let start = std::time::Instant::now();
        state.shutdown().unwrap();
        assert!(start.elapsed() < std::time::Duration::from_secs(6));
        assert!(writer.join().unwrap().is_err());
        assert!(state.sidecar.lock().unwrap().is_none());
    }

    #[test]
    fn concurrent_exit_paths_wait_for_shared_cleanup() {
        let temp = tempfile::tempdir().unwrap();
        let marker = temp.path().join("cleanup complete");
        let script = "import sys,time,pathlib; sys.stdin.readline(); time.sleep(0.1); pathlib.Path(sys.argv[1]).write_text('cleaned')";
        let sidecar = Sidecar::spawn("python3", &["-c", script, marker.to_str().unwrap()]).unwrap();
        let state = Arc::new(AppState::default());
        *state.sidecar.lock().unwrap() = Some(sidecar);
        let mut exits = vec![];
        for _ in 0..2 {
            let state = Arc::clone(&state);
            let marker = marker.clone();
            exits.push(std::thread::spawn(move || {
                state.shutdown().unwrap();
                assert_eq!(std::fs::read_to_string(marker).unwrap(), "cleaned");
            }));
        }
        for exit in exits {
            exit.join().unwrap();
        }
        assert!(state.sidecar.lock().unwrap().is_none());
        assert!(state.closing.load(std::sync::atomic::Ordering::SeqCst));
    }
}
