// Sidecar process manager for Python IPC server.
//
// Spawns Python sidecar, manages stdio pipes, provides thread-safe communication.

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct IpcMessage {
    #[serde(rename = "type")]
    pub msg_type: String,
    pub payload: serde_json::Value,
}

#[derive(Debug)]
pub struct Sidecar {
    process: Arc<Mutex<Child>>,
    expected_exit: Arc<AtomicBool>,
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
            process: Arc::new(Mutex::new(process)),
            expected_exit: Arc::new(AtomicBool::new(false)),
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

    /// Forward complete JSON lines, then reap the child and report unexpected EOF.
    /// Terminal protocol messages and explicit termination suppress crash reports.
    /// Stderr remains inherited; it is never copied into frontend error messages.
    pub fn start_reader<F>(&mut self, on_message: F)
    where
        F: Fn(IpcMessage) + Send + 'static,
    {
        let stdout = self
            .process
            .lock()
            .unwrap()
            .stdout
            .take()
            .expect("stdout was already taken");
        let process = Arc::clone(&self.process);
        let expected_exit = Arc::clone(&self.expected_exit);
        std::thread::spawn(move || {
            let mut read_error = false;
            for line in BufReader::new(stdout).lines() {
                match line {
                    Ok(line) => {
                        if let Ok(msg) = serde_json::from_str::<IpcMessage>(&line) {
                            if matches!(msg.msg_type.as_str(), "accepted" | "aborted") {
                                expected_exit.store(true, Ordering::SeqCst);
                            }
                            on_message(msg);
                        }
                    }
                    Err(_) => {
                        read_error = true;
                        break;
                    }
                }
            }
            // EOF may arrive just before the OS publishes the exit status.
            // A process that closes stdout but keeps running cannot serve IPC.
            let deadline = Instant::now() + Duration::from_millis(100);
            let outcome = loop {
                let mut child = process.lock().unwrap();
                match child.try_wait() {
                    Ok(Some(status)) => break Ok(status),
                    Err(error) => break Err(error.to_string()),
                    Ok(None) if Instant::now() >= deadline => {
                        break child
                            .kill()
                            .and_then(|()| child.wait())
                            .map_err(|e| e.to_string());
                    }
                    Ok(None) => {}
                }
                drop(child);
                std::thread::sleep(Duration::from_millis(10));
            };
            if !expected_exit.load(Ordering::SeqCst) {
                let reason = match outcome {
                    Ok(status) => format!("Backend connection closed unexpectedly ({status})."),
                    Err(_) => {
                        "Backend connection closed unexpectedly; process cleanup failed.".into()
                    }
                };
                let detail = if read_error {
                    " Reading backend output failed."
                } else {
                    ""
                };
                on_message(IpcMessage {
                    msg_type: "error".into(),
                    payload: serde_json::json!({
                        "message": format!("{reason}{detail} Check backend stderr and the Python runtime installation."),
                        "fatal": true,
                        "operation": "sidecar_exit",
                    }),
                });
            }
        });
    }

    /// Intentional termination is idempotent and always reaps the child.
    pub fn kill(&mut self) -> Result<(), String> {
        self.expected_exit.store(true, Ordering::SeqCst);
        let mut child = self.process.lock().map_err(|e| e.to_string())?;
        if child.try_wait().map_err(|e| e.to_string())?.is_none() {
            child
                .kill()
                .map_err(|e| format!("Failed to kill process: {e}"))?;
        }
        child
            .wait()
            .map_err(|e| format!("Failed to reap process: {e}"))?;
        Ok(())
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        let _ = self.kill();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;
    use std::sync::mpsc;
    use std::time::Duration;

    #[cfg(unix)]
    fn assert_reaped(pid: u32) {
        let exists = Command::new("kill")
            .args(["-0", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .unwrap()
            .success();
        assert!(!exists, "child {pid} still exists (possibly unreaped)");
    }

    #[test]
    fn unexpected_exits_and_broken_stdout_report_one_terminal_error() {
        for script in [
            "import sys; sys.exit(7)",
            "import sys; print('not JSON', flush=True); sys.exit(8)",
            "import os,time; os.close(1); time.sleep(60)",
            "import os,time; os.write(1, b'\\xff\\n'); time.sleep(60)",
        ] {
            let mut sidecar = Sidecar::spawn("python3", &["-c", script]).unwrap();
            let pid = sidecar.process.lock().unwrap().id();
            let (tx, rx) = mpsc::channel();
            sidecar.start_reader(move |msg| {
                tx.send(msg).unwrap();
            });
            let error = rx.recv_timeout(Duration::from_secs(3)).unwrap();
            assert_eq!(error.msg_type, "error");
            assert_eq!(error.payload["fatal"], true);
            assert_eq!(error.payload["operation"], "sidecar_exit");
            assert!(error.payload["message"]
                .as_str()
                .unwrap()
                .contains("Python runtime"));
            assert!(matches!(
                rx.recv_timeout(Duration::from_secs(1)),
                Err(mpsc::RecvTimeoutError::Disconnected)
            ));
            #[cfg(unix)]
            assert_reaped(pid);
        }
    }

    #[test]
    fn acknowledged_terminal_messages_exit_without_crash_reports() {
        for terminal in ["accepted", "aborted"] {
            let script = format!("import json; print(json.dumps({{'type': '{terminal}', 'payload': {{}}}}), flush=True)");
            let mut sidecar = Sidecar::spawn("python3", &["-c", &script]).unwrap();
            let pid = sidecar.process.lock().unwrap().id();
            let (tx, rx) = mpsc::channel();
            sidecar.start_reader(move |msg| {
                tx.send(msg).unwrap();
            });
            assert_eq!(
                rx.recv_timeout(Duration::from_secs(3)).unwrap().msg_type,
                terminal
            );
            assert!(matches!(
                rx.recv_timeout(Duration::from_secs(3)),
                Err(mpsc::RecvTimeoutError::Disconnected)
            ));
            #[cfg(unix)]
            assert_reaped(pid);
        }
    }

    #[test]
    fn intentional_kill_and_drop_reap_without_crash_reports() {
        for explicit in [true, false] {
            let mut sidecar =
                Sidecar::spawn("python3", &["-c", "import time; time.sleep(60)"]).unwrap();
            let pid = sidecar.process.lock().unwrap().id();
            let (tx, rx) = mpsc::channel();
            sidecar.start_reader(move |msg| {
                tx.send(msg).unwrap();
            });
            if explicit {
                sidecar.kill().unwrap();
                sidecar.kill().unwrap();
            }
            drop(sidecar);
            assert!(matches!(
                rx.recv_timeout(Duration::from_secs(3)),
                Err(mpsc::RecvTimeoutError::Disconnected)
            ));
            #[cfg(unix)]
            assert_reaped(pid);
        }
    }

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

        let terminal = rx.recv_timeout(Duration::from_secs(2)).unwrap();
        assert_eq!(terminal.msg_type, "error");
        assert_eq!(terminal.payload["fatal"], true);
        assert!(sidecar
            .process
            .lock()
            .unwrap()
            .try_wait()
            .unwrap()
            .is_some());
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
        while let Ok(msg) = rx.recv_timeout(Duration::from_millis(500)) {
            if msg.msg_type == "error" {
                break;
            }
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

        let status = sidecar.process.lock().unwrap().try_wait();
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
