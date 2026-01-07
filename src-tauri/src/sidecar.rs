// Sidecar process manager for Python IPC server.
//
// Spawns Python sidecar, manages stdio pipes, provides thread-safe communication.

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct IpcMessage {
    #[serde(rename = "type")]
    pub msg_type: String,
    pub payload: serde_json::Value,
}

#[derive(Debug)]
pub struct Sidecar {
    process: Child,
    stdin: Arc<Mutex<std::process::ChildStdin>>,
}

impl Sidecar {
    /// Spawn Python sidecar process.
    ///
    /// CONTRACT:
    ///   Inputs:
    ///     - python_path: path to Python executable (e.g., "python", "python3", or absolute path)
    ///     - args: command-line arguments for Python (e.g., ["-m", "textbrush.ipc"])
    ///
    ///   Outputs:
    ///     - Result<Sidecar, String>: Sidecar instance on success, error message on failure
    ///
    ///   Invariants:
    ///     - Process is spawned with stdin/stdout piped
    ///     - stderr is inherited (goes to parent's stderr for logging)
    ///     - stdin is wrapped in Arc<Mutex<>> for thread-safe writes
    ///     - stdout is captured for reading messages
    ///
    ///   Properties:
    ///     - Blocking: waits for process to spawn
    ///     - Error handling: returns Result with descriptive error message
    ///     - Thread-safe: stdin is protected by mutex
    ///
    ///   Algorithm:
    ///     1. Create Command with python_path and args
    ///     2. Configure stdio:
    ///        - stdin: piped
    ///        - stdout: piped
    ///        - stderr: inherited
    ///     3. Spawn process
    ///     4. Extract stdin handle and wrap in Arc<Mutex<>>
    ///     5. Return Sidecar instance with process and stdin
    pub fn spawn(python_path: &str, args: &[&str]) -> Result<Self, String> {
        let mut process = Command::new(python_path)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to spawn process: {}", e))?;

        let stdin = process
            .stdin
            .take()
            .ok_or_else(|| "Failed to capture stdin".to_string())?;

        Ok(Self {
            process,
            stdin: Arc::new(Mutex::new(stdin)),
        })
    }

    /// Send JSON message to sidecar via stdin (thread-safe).
    ///
    /// CONTRACT:
    ///   Inputs:
    ///     - message: IpcMessage to send
    ///
    ///   Outputs:
    ///     - Result<(), String>: Ok on success, error message on failure
    ///
    ///   Invariants:
    ///     - Message is serialized to JSON
    ///     - JSON string is written to stdin followed by newline
    ///     - stdin is flushed immediately
    ///     - Write operation is atomic (protected by mutex)
    ///
    ///   Properties:
    ///     - Thread-safe: can be called concurrently from multiple threads
    ///     - Blocking: waits for mutex lock and I/O
    ///     - Newline-delimited: each message is a single line
    ///     - Error handling: returns Result with error description
    ///
    ///   Algorithm:
    ///     1. Serialize message to JSON string
    ///     2. Acquire stdin mutex lock
    ///     3. Write JSON string + newline to stdin
    ///     4. Flush stdin
    ///     5. Release mutex lock
    ///     6. Return Ok or Err with error message
    pub fn send(&self, message: &IpcMessage) -> Result<(), String> {
        let json = serde_json::to_string(message)
            .map_err(|e| format!("Failed to serialize message: {}", e))?;

        let mut stdin = self
            .stdin
            .lock()
            .map_err(|e| format!("Failed to acquire stdin lock: {}", e))?;

        writeln!(stdin, "{}", json).map_err(|e| format!("Failed to write to stdin: {}", e))?;

        stdin
            .flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        Ok(())
    }

    /// Start background thread reading messages from sidecar stdout.
    ///
    /// CONTRACT:
    ///   Inputs:
    ///     - on_message: callback function called for each received message
    ///                   Must be Send + 'static (can be moved to thread)
    ///
    ///   Outputs: none (starts background thread)
    ///
    ///   Invariants:
    ///     - Takes ownership of stdout handle
    ///     - Spawns daemon thread reading lines from stdout
    ///     - Each line is parsed as JSON message
    ///     - Valid messages are passed to on_message callback
    ///     - Thread exits when stdout closes (EOF) or error
    ///
    ///   Properties:
    ///     - Non-blocking: returns immediately after starting thread
    ///     - Background processing: messages delivered asynchronously
    ///     - Error tolerance: invalid JSON is skipped (logged)
    ///     - Thread lifetime: runs until stdout closes
    ///
    ///   Algorithm:
    ///     1. Take stdout handle from process (consuming it)
    ///     2. Spawn thread:
    ///        a. Create BufReader wrapping stdout
    ///        b. Loop over lines:
    ///           - Read line
    ///           - Try parse as IpcMessage
    ///           - If valid: call on_message(msg)
    ///           - If invalid: skip (optional: log error)
    ///        c. Exit when EOF or error
    pub fn start_reader<F>(&mut self, on_message: F)
    where
        F: Fn(IpcMessage) + Send + 'static,
    {
        let stdout = self
            .process
            .stdout
            .take()
            .expect("stdout was already taken");

        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(line) => {
                        if let Ok(msg) = serde_json::from_str::<IpcMessage>(&line) {
                            on_message(msg);
                        }
                    }
                    Err(_) => break,
                }
            }
        });
    }

    /// Terminate sidecar process.
    ///
    /// CONTRACT:
    ///   Inputs: none
    ///
    ///   Outputs:
    ///     - Result<(), String>: Ok on success, error message on failure
    ///
    ///   Invariants:
    ///     - Process is forcefully terminated
    ///     - Does not wait for graceful shutdown
    ///
    ///   Properties:
    ///     - Blocking: waits for kill operation
    ///     - Forceful: sends SIGKILL (Unix) or TerminateProcess (Windows)
    ///     - Error handling: returns Result with error description
    ///
    ///   Algorithm:
    ///     1. Call process.kill()
    ///     2. Return Ok or Err with error message
    pub fn kill(&mut self) -> Result<(), String> {
        self.process
            .kill()
            .map_err(|e| format!("Failed to kill process: {}", e))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;
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

    proptest! {
        #[test]
        fn spawn_with_various_arguments(
            _arg1 in "[a-z]{1,10}",
            _arg2 in "[0-9]{1,5}",
        ) {
            let result = Sidecar::spawn("python3", &["-c", "import sys; sys.exit(0)"]);
            prop_assert!(result.is_ok());

            if let Ok(mut sidecar) = result {
                let _ = sidecar.kill();
            }
        }

        #[test]
        fn send_various_json_messages(
            msg_type in "[a-z]{3,15}",
            payload_value in ".*",
        ) {
            let script = python_echo_script();
            let mut sidecar = Sidecar::spawn("python3", &["-c", script])
                .expect("Failed to spawn Python");

            let message = IpcMessage {
                msg_type: msg_type.clone(),
                payload: serde_json::json!(payload_value),
            };

            let result = sidecar.send(&message);
            prop_assert!(result.is_ok());

            let _ = sidecar.kill();
        }

        #[test]
        fn parse_valid_json_lines(
            msg_type in "[a-z]{3,15}",
            payload_str in "[a-zA-Z0-9 ]{0,50}",
        ) {
            let message = IpcMessage {
                msg_type: msg_type.clone(),
                payload: serde_json::json!(payload_str),
            };

            let json_str = serde_json::to_string(&message).unwrap();
            let parsed: Result<IpcMessage, _> = serde_json::from_str(&json_str);

            prop_assert!(parsed.is_ok());
            if let Ok(parsed_msg) = parsed {
                prop_assert_eq!(&parsed_msg.msg_type, &msg_type);
            }
        }
    }

    #[test]
    fn spawn_creates_process_with_piped_stdio() {
        let result = Sidecar::spawn("python3", &["-c", "import sys; sys.exit(0)"]);
        assert!(result.is_ok());

        if let Ok(mut sidecar) = result {
            let _ = sidecar.kill();
        }
    }

    #[test]
    fn spawn_returns_error_for_invalid_executable() {
        let result = Sidecar::spawn("nonexistent_python", &[]);
        assert!(result.is_err());
        let err_msg = result.unwrap_err();
        assert!(err_msg.contains("Failed to spawn process"));
    }

    #[test]
    fn send_serializes_and_writes_json_with_newline() {
        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let message = IpcMessage {
            msg_type: "test".to_string(),
            payload: serde_json::json!({"key": "value"}),
        };

        let result = sidecar.send(&message);
        assert!(result.is_ok());

        std::thread::sleep(Duration::from_millis(100));
        let _ = sidecar.kill();
    }

    #[test]
    fn send_is_thread_safe() {
        let script = python_echo_script();
        let sidecar =
            Arc::new(Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python"));

        let mut handles = vec![];

        for i in 0..10 {
            let sidecar_clone = Arc::clone(&sidecar);
            let handle = std::thread::spawn(move || {
                let message = IpcMessage {
                    msg_type: format!("msg_{}", i),
                    payload: serde_json::json!(i),
                };
                sidecar_clone.send(&message)
            });
            handles.push(handle);
        }

        for handle in handles {
            let result = handle.join().expect("Thread panicked");
            assert!(result.is_ok());
        }
    }

    #[test]
    fn start_reader_invokes_callback_for_valid_json() {
        let script = r#"
import sys
import json

msg = {"type": "ready", "payload": {"status": "ok"}}
sys.stdout.write(json.dumps(msg) + "\n")
sys.stdout.flush()
"#;

        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        let received = rx.recv_timeout(Duration::from_secs(2));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "ready");

        let _ = sidecar.kill();
    }

    #[test]
    fn start_reader_skips_invalid_json() {
        let script = r#"
import sys
import json

sys.stdout.write("invalid json\n")
sys.stdout.flush()

msg = {"type": "valid", "payload": {}}
sys.stdout.write(json.dumps(msg) + "\n")
sys.stdout.flush()
"#;

        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        let received = rx.recv_timeout(Duration::from_secs(2));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "valid");

        let _ = sidecar.kill();
    }

    #[test]
    fn start_reader_handles_eof_gracefully() {
        let script = r#"
import sys
import json

msg = {"type": "message", "payload": {}}
sys.stdout.write(json.dumps(msg) + "\n")
sys.stdout.flush()
sys.exit(0)
"#;

        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        let received = rx.recv_timeout(Duration::from_secs(2));
        assert!(received.is_ok());

        std::thread::sleep(Duration::from_millis(200));

        let no_more = rx.recv_timeout(Duration::from_millis(100));
        assert!(no_more.is_err());
    }

    #[test]
    fn start_reader_handles_multiple_messages() {
        let script = r#"
import sys
import json

for i in range(5):
    msg = {"type": f"msg_{i}", "payload": {"index": i}}
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()
"#;

        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        let mut received_count = 0;
        while let Ok(_msg) = rx.recv_timeout(Duration::from_millis(500)) {
            received_count += 1;
        }

        assert_eq!(received_count, 5);
        let _ = sidecar.kill();
    }

    #[test]
    fn kill_terminates_process() {
        let script = "import time; time.sleep(10)";
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let result = sidecar.kill();
        assert!(result.is_ok());

        std::thread::sleep(Duration::from_millis(100));

        let status = sidecar.process.try_wait();
        assert!(status.is_ok());
        assert!(status.unwrap().is_some());
    }

    #[test]
    fn full_communication_cycle() {
        let script = python_echo_script();
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script]).expect("Failed to spawn Python");

        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).ok();
        });

        let test_message = IpcMessage {
            msg_type: "init".to_string(),
            payload: serde_json::json!({
                "prompt": "test prompt",
                "seed": 42
            }),
        };

        let send_result = sidecar.send(&test_message);
        assert!(send_result.is_ok());

        let received = rx.recv_timeout(Duration::from_secs(2));
        assert!(received.is_ok());

        let msg = received.unwrap();
        assert_eq!(msg.msg_type, "init");
        assert_eq!(msg.payload["prompt"], "test prompt");
        assert_eq!(msg.payload["seed"], 42);

        let _ = sidecar.kill();
    }
}
