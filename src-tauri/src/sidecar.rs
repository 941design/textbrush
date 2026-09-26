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
    preview_dir: Arc<tempfile::TempDir>,
    group_terminated: Arc<AtomicBool>,
    stdin: Arc<Mutex<std::process::ChildStdin>>,
}

/// A writable pipe handle that does not keep the child or session alive.
pub struct SidecarSender {
    stdin: Arc<Mutex<std::process::ChildStdin>>,
}

impl SidecarSender {
    pub fn send(&self, message: &IpcMessage) -> Result<(), String> {
        let json = serde_json::to_string(message).map_err(|e| e.to_string())?;
        let mut stdin = self.stdin.lock().map_err(|e| e.to_string())?;
        writeln!(stdin, "{json}").map_err(|e| format!("Failed to write to stdin: {e}"))?;
        stdin
            .flush()
            .map_err(|e| format!("Failed to flush stdin: {e}"))
    }
}

/// Kill the session's process group at most once, including launcher children.
fn terminate_group(child: &mut Child, terminated: &AtomicBool) -> std::io::Result<()> {
    if terminated.swap(true, Ordering::SeqCst) {
        return Ok(());
    }
    #[cfg(unix)]
    {
        // spawn() made the child a new group leader; negative pid targets only
        // that group. No shell interpolation or caller-provided pid is involved.
        let result = unsafe { libc::kill(-(child.id() as i32), libc::SIGKILL) };
        if result != 0 {
            let error = std::io::Error::last_os_error();
            if error.raw_os_error() != Some(libc::ESRCH) {
                return Err(error);
            }
        }
        Ok(())
    }
    #[cfg(not(unix))]
    {
        child.kill()
    }
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
        let preview_dir = Arc::new(
            tempfile::Builder::new()
                .prefix("textbrush-preview-")
                .tempdir()
                .map_err(|e| format!("Failed to create session preview directory: {e}"))?,
        );
        let mut command = Command::new(python_path);
        command
            .args(args)
            .env("TEXTBRUSH_PREVIEW_DIR", preview_dir.path())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            command.process_group(0);
        }
        let mut process = command
            .spawn()
            .map_err(|e| format!("Failed to spawn process: {e}"))?;

        let stdin = process
            .stdin
            .take()
            .ok_or_else(|| "Failed to capture stdin".to_string())?;

        Ok(Self {
            process: Arc::new(Mutex::new(process)),
            expected_exit: Arc::new(AtomicBool::new(false)),
            preview_dir,
            group_terminated: Arc::new(AtomicBool::new(false)),
            stdin: Arc::new(Mutex::new(stdin)),
        })
    }

    pub fn sender(&self) -> SidecarSender {
        SidecarSender {
            stdin: Arc::clone(&self.stdin),
        }
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
        let preview_dir = Arc::clone(&self.preview_dir);
        let group_terminated = Arc::clone(&self.group_terminated);
        // A launcher can exit while its child still holds stdout open. Reap
        // the leader independently so inherited pipes cannot hide its exit.
        let monitor_process = Arc::clone(&self.process);
        let monitor_group = Arc::clone(&self.group_terminated);
        std::thread::spawn(move || loop {
            let mut child = monitor_process.lock().unwrap();
            if !matches!(child.try_wait(), Ok(None)) {
                let _ = terminate_group(&mut child, &monitor_group);
                break;
            }
            drop(child);
            std::thread::sleep(Duration::from_millis(20));
        });
        std::thread::spawn(move || {
            let mut read_error = false;
            for line in BufReader::new(stdout).lines() {
                match line {
                    Ok(line) => {
                        if let Ok(msg) = serde_json::from_str::<IpcMessage>(&line) {
                            if matches!(msg.msg_type.as_str(), "accepted" | "aborted")
                                || (msg.msg_type == "error" && msg.payload["fatal"] == true)
                            {
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
                        break terminate_group(&mut child, &group_terminated)
                            .and_then(|()| child.wait())
                            .map_err(|e| e.to_string());
                    }
                    Ok(None) => {}
                }
                drop(child);
                std::thread::sleep(Duration::from_millis(10));
            };
            let _ = std::fs::remove_dir_all(preview_dir.path());
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

    /// Give ABORT a bounded chance to finish, then kill/reap and remove only
    /// this session's previews. A blocked stdin writer cannot extend the bound.
    pub fn shutdown(&mut self, grace: Duration) -> Result<(), String> {
        self.expected_exit.store(true, Ordering::SeqCst);
        let stdin = Arc::clone(&self.stdin);
        std::thread::spawn(move || {
            if let Ok(mut pipe) = stdin.lock() {
                let _ = writeln!(pipe, "{{\"type\":\"abort\",\"payload\":null}}");
                let _ = pipe.flush();
            }
        });
        let deadline = Instant::now() + grace;
        loop {
            if self
                .process
                .lock()
                .map_err(|e| e.to_string())?
                .try_wait()
                .map_err(|e| e.to_string())?
                .is_some()
            {
                break;
            }
            if Instant::now() >= deadline {
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        self.kill()
    }

    /// Intentional termination is idempotent and always reaps the child.
    pub fn kill(&mut self) -> Result<(), String> {
        self.expected_exit.store(true, Ordering::SeqCst);
        let mut child = self.process.lock().map_err(|e| e.to_string())?;
        terminate_group(&mut child, &self.group_terminated)
            .map_err(|e| format!("Failed to kill process group: {e}"))?;
        child
            .wait()
            .map_err(|e| format!("Failed to reap process: {e}"))?;
        let _ = std::fs::remove_dir_all(self.preview_dir.path());
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

    #[test]
    fn shutdown_allows_cleanup_then_reaps_and_removes_session_only() {
        let retained = tempfile::tempdir().unwrap();
        let marker = retained.path().join("saved output.png");
        let script = r#"
import json, os, pathlib, sys, time
pathlib.Path(sys.argv[1]).write_text('accepted output')
preview = pathlib.Path(os.environ['TEXTBRUSH_PREVIEW_DIR']) / 'preview.png'
preview.write_text('preview')
print(json.dumps({'type': 'ready', 'payload': {}}), flush=True)
assert json.loads(sys.stdin.readline())['type'] == 'abort'
time.sleep(0.1)
preview.unlink()
print(json.dumps({'type': 'aborted', 'payload': {}}), flush=True)
"#;
        let mut sidecar =
            Sidecar::spawn("python3", &["-c", script, marker.to_str().unwrap()]).unwrap();
        let directory = sidecar.preview_dir.path().to_path_buf();
        let pid = sidecar.process.lock().unwrap().id();
        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).unwrap();
        });
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(2)).unwrap().msg_type,
            "ready"
        );
        sidecar.shutdown(Duration::from_secs(2)).unwrap();
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(2)).unwrap().msg_type,
            "aborted"
        );
        assert!(sidecar
            .process
            .lock()
            .unwrap()
            .try_wait()
            .unwrap()
            .unwrap()
            .success());
        assert!(!directory.exists());
        assert_eq!(std::fs::read_to_string(marker).unwrap(), "accepted output");
        #[cfg(unix)]
        assert_reaped(pid);
    }

    #[test]
    fn shutdown_deadline_survives_blocked_stdin_and_cleans_previews() {
        let script = r#"
import json, os, pathlib, time
(pathlib.Path(os.environ['TEXTBRUSH_PREVIEW_DIR']) / 'preview.png').write_text('preview')
print(json.dumps({'type': 'ready', 'payload': {}}), flush=True)
time.sleep(60)
"#;
        let mut sidecar = Sidecar::spawn("python3", &["-c", script]).unwrap();
        let directory = sidecar.preview_dir.path().to_path_buf();
        let pid = sidecar.process.lock().unwrap().id();
        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).unwrap();
        });
        rx.recv_timeout(Duration::from_secs(2)).unwrap();
        let stdin = Arc::clone(&sidecar.stdin);
        let (locked_tx, locked_rx) = mpsc::channel();
        let writer = std::thread::spawn(move || {
            let mut pipe = stdin.lock().unwrap();
            locked_tx.send(()).unwrap();
            let _ = pipe.write_all(&vec![b'x'; 1_000_000]);
        });
        locked_rx.recv_timeout(Duration::from_secs(2)).unwrap();
        let start = Instant::now();
        sidecar.shutdown(Duration::from_millis(200)).unwrap();
        assert!(start.elapsed() < Duration::from_secs(2));
        writer.join().unwrap();
        assert!(!directory.exists());
        assert!(matches!(
            rx.recv_timeout(Duration::from_secs(2)),
            Err(mpsc::RecvTimeoutError::Disconnected)
        ));
        #[cfg(unix)]
        assert_reaped(pid);
    }

    #[test]
    fn crash_removes_private_previews_before_reporting_error() {
        let script = "import os,pathlib; (pathlib.Path(os.environ['TEXTBRUSH_PREVIEW_DIR'])/'preview.png').write_text('preview')";
        let mut sidecar = Sidecar::spawn("python3", &["-c", script]).unwrap();
        let directory = sidecar.preview_dir.path().to_path_buf();
        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).unwrap();
        });
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(2)).unwrap().msg_type,
            "error"
        );
        assert!(!directory.exists());
    }

    #[cfg(unix)]
    #[test]
    fn launcher_exit_does_not_leave_descendant_holding_stdout() {
        let script = r#"
import subprocess, sys, json
subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print(json.dumps({'type': 'ready', 'payload': {}}), flush=True)
"#;
        let mut sidecar = Sidecar::spawn("python3", &["-c", script]).unwrap();
        let (tx, rx) = mpsc::channel();
        sidecar.start_reader(move |msg| {
            tx.send(msg).unwrap();
        });
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(3)).unwrap().msg_type,
            "ready"
        );
        assert_eq!(
            rx.recv_timeout(Duration::from_secs(3)).unwrap().msg_type,
            "error"
        );
        assert!(!sidecar.preview_dir.path().exists());
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

            let result = sidecar.sender().send(&message);
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

        let result = sidecar.sender().send(&message);
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
                sidecar_clone.sender().send(&message)
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

        let send_result = sidecar.sender().send(&test_message);
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
