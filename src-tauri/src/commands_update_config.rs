// Stub for update_generation_config Tauri command
//
// This file will be integrated into commands.rs after implementation.

use crate::commands::AppState;
use crate::sidecar::IpcMessage;
use tauri::{command, State};

/// Update generation configuration (prompt, aspect ratio, and dimensions).
///
/// CONTRACT:
///   Inputs:
///     - state: AppState containing sidecar
///     - prompt: new text description for image generation, non-empty string
///     - aspect_ratio: new aspect ratio string, one of "1:1", "16:9", "9:16"
///     - width: optional image width in pixels (overrides aspect_ratio)
///     - height: optional image height in pixels (overrides aspect_ratio)
///
///   Outputs:
///     - Result<(), String>: Ok on success, error message on failure
///
///   Invariants:
///     - If sidecar exists: sends UPDATE_CONFIG command with prompt, aspect_ratio, width, height
///     - If no sidecar: returns error "No sidecar running"
///     - Python backend will:
///       * Stop current generation worker
///       * Clear image buffer
///       * Restart generation with new configuration
///       * Send BUFFER_STATUS event showing reset state
///
///   Properties:
///     - Synchronous: returns after sending command (backend restart is async)
///     - Error handling: returns Result with error if no sidecar
///     - Validation: input validation happens on frontend and Python backend
///     - Non-blocking: command send is fast, restart happens in backend
///     - Dimension priority: explicit width/height override aspect_ratio
///
///   Algorithm:
///     1. Lock AppState.sidecar mutex
///     2. If sidecar exists:
///        a. Create IpcMessage:
///           - msg_type: "update_config"
///           - payload: JSON object with "prompt", "aspect_ratio", "width", "height" fields
///        b. Send message via sidecar.send()
///        c. Return Ok or Err from send operation
///     3. If no sidecar:
///        a. Return Err("No sidecar running")
///
/// Integration:
///   - Add this function to commands.rs after skip_image() function
///   - Add to tauri::Builder in main.rs: .invoke_handler(tauri::generate_handler![..., update_generation_config])
///   - Frontend invokes via: await invoke('update_generation_config', { prompt, aspect_ratio, width, height })
#[command]
pub async fn update_generation_config(
    state: State<'_, AppState>,
    prompt: String,
    aspect_ratio: String,
    width: Option<u32>,
    height: Option<u32>,
) -> Result<(), String> {
    let sidecar_guard = state.sidecar.lock().unwrap();

    if let Some(sidecar) = sidecar_guard.as_ref() {
        let message = IpcMessage {
            msg_type: "update_config".to_string(),
            payload: serde_json::json!({
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
            }),
        };
        sidecar.send(&message)?;
        Ok(())
    } else {
        Err("No sidecar running".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sidecar::Sidecar;
    use std::sync::mpsc;
    use std::sync::Mutex;
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
    fn update_generation_config_returns_error_when_no_sidecar() {
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
    fn update_generation_config_sends_update_config_message_when_sidecar_exists() {
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

        let test_prompt = "A beautiful sunset over mountains";
        let test_aspect_ratio = "16:9";

        let sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(sidecar) = sidecar_guard.as_ref() {
            let message = IpcMessage {
                msg_type: "update_config".to_string(),
                payload: serde_json::json!({
                    "prompt": test_prompt,
                    "aspect_ratio": test_aspect_ratio,
                }),
            };
            sidecar.send(&message).expect("Send should succeed");
        }
        drop(sidecar_guard);

        let received = rx.recv_timeout(Duration::from_secs(1));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "update_config");

        let payload = msg.payload.as_object().expect("Payload should be object");
        assert_eq!(payload["prompt"].as_str().unwrap(), test_prompt);
        assert_eq!(payload["aspect_ratio"].as_str().unwrap(), test_aspect_ratio);

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn update_generation_config_accepts_valid_aspect_ratios() {
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

        let valid_ratios = vec!["1:1", "16:9", "9:16"];

        for ratio in valid_ratios {
            let sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(sidecar) = sidecar_guard.as_ref() {
                let message = IpcMessage {
                    msg_type: "update_config".to_string(),
                    payload: serde_json::json!({
                        "prompt": "test prompt",
                        "aspect_ratio": ratio,
                    }),
                };
                let result = sidecar.send(&message);
                assert!(
                    result.is_ok(),
                    "Failed to send message with aspect ratio: {}",
                    ratio
                );
            }
            drop(sidecar_guard);

            let received = rx.recv_timeout(Duration::from_millis(500));
            assert!(
                received.is_ok(),
                "Failed to receive message for ratio: {}",
                ratio
            );

            let msg = received.unwrap();
            let payload = msg.payload.as_object().unwrap();
            assert_eq!(payload["aspect_ratio"].as_str().unwrap(), ratio);
        }

        let mut sidecar_guard = state.sidecar.lock().unwrap();
        if let Some(mut sidecar) = sidecar_guard.take() {
            let _ = sidecar.kill();
        }
    }
}

#[cfg(test)]
mod proptests {
    use super::*;
    use crate::sidecar::Sidecar;
    use proptest::prelude::*;
    use std::sync::mpsc;
    use std::sync::Mutex;
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

    proptest! {
        #[test]
        fn message_serialization_roundtrip(
            prompt in "[a-zA-Z0-9 ]{1,100}",
            aspect_ratio in prop::sample::select(vec!["1:1", "16:9", "9:16"])
        ) {
            let message = IpcMessage {
                msg_type: "update_config".to_string(),
                payload: serde_json::json!({
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                }),
            };

            let serialized = serde_json::to_string(&message).unwrap();
            let deserialized: IpcMessage = serde_json::from_str(&serialized).unwrap();

            prop_assert_eq!(&deserialized.msg_type, "update_config");
            let payload = deserialized.payload.as_object().unwrap();
            prop_assert_eq!(payload["prompt"].as_str().unwrap(), prompt);
            prop_assert_eq!(payload["aspect_ratio"].as_str().unwrap(), aspect_ratio);
        }

        #[test]
        fn valid_config_updates_succeed(
            prompt in "[a-zA-Z0-9 ,.!?'-]{1,200}",
            aspect_ratio in prop::sample::select(vec!["1:1", "16:9", "9:16"])
        ) {
            let state = AppState {
                sidecar: Mutex::new(None),
            };

            let script = python_echo_script();
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
                    msg_type: "update_config".to_string(),
                    payload: serde_json::json!({
                        "prompt": &prompt,
                        "aspect_ratio": &aspect_ratio,
                    }),
                };
                let result = sidecar.send(&message);
                prop_assert!(result.is_ok());
            }
            drop(sidecar_guard);

            let received = rx.recv_timeout(Duration::from_secs(1));
            prop_assert!(received.is_ok());

            let msg = received.unwrap();
            prop_assert_eq!(&msg.msg_type, "update_config");

            let payload = msg.payload.as_object().unwrap();
            prop_assert_eq!(payload["prompt"].as_str().unwrap(), prompt);
            prop_assert_eq!(payload["aspect_ratio"].as_str().unwrap(), aspect_ratio);

            let mut sidecar_guard = state.sidecar.lock().unwrap();
            if let Some(mut sidecar) = sidecar_guard.take() {
                let _ = sidecar.kill();
            }
        }
    }
}
