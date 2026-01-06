# Increment 3: Tauri Integration - UI Shell & IPC Protocol

## Overview
Connect the Tauri desktop shell to the Python backend via IPC. This increment establishes the communication layer between the Rust/JavaScript frontend and the Python sidecar process.

## Goals
- Implement sidecar process management (spawn/kill Python)
- Design and implement IPC protocol (stdio JSON)
- Create Tauri commands for UI actions
- Handle lifecycle events (startup, shutdown, abort)
- Build minimal placeholder UI for testing IPC

## Prerequisites
- Increment 1 complete (CLI, config)
- Increment 2 complete (inference backend)

## Deliverables

### 3.1 IPC Protocol Design

Communication via stdio JSON messages (simpler than HTTP for desktop app):

```
textbrush/
├── ipc/
│   ├── __init__.py
│   ├── protocol.py          # Message types
│   ├── server.py            # Python IPC server
│   └── handler.py           # Message handlers
```

**Message Protocol (`textbrush/ipc/protocol.py`):**

```python
from dataclasses import dataclass, asdict
from enum import Enum
import json

class MessageType(str, Enum):
    # Commands (Tauri → Python)
    INIT = "init"
    GENERATE = "generate"
    SKIP = "skip"
    ACCEPT = "accept"
    ABORT = "abort"
    STATUS = "status"

    # Events (Python → Tauri)
    READY = "ready"
    IMAGE_READY = "image_ready"
    BUFFER_STATUS = "buffer_status"
    ERROR = "error"
    ACCEPTED = "accepted"
    ABORTED = "aborted"

@dataclass
class InitCommand:
    prompt: str
    output_path: str | None = None
    seed: int | None = None
    aspect_ratio: str = "1:1"
    format: str = "png"

@dataclass
class ImageReadyEvent:
    image_data: str  # Base64 encoded
    seed: int
    buffer_count: int
    buffer_max: int

@dataclass
class BufferStatusEvent:
    count: int
    max: int
    generating: bool

@dataclass
class AcceptedEvent:
    path: str

@dataclass
class ErrorEvent:
    message: str
    fatal: bool = False

class Message:
    def __init__(self, type: MessageType, payload: dict | None = None):
        self.type = type
        self.payload = payload or {}

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "payload": self.payload
        })

    @classmethod
    def from_json(cls, data: str) -> "Message":
        parsed = json.loads(data)
        return cls(
            type=MessageType(parsed["type"]),
            payload=parsed.get("payload", {})
        )
```

### 3.2 Python IPC Server

Stdio-based server that runs as sidecar:

```python
# textbrush/ipc/server.py
import sys
import json
import threading
import logging
from .protocol import Message, MessageType
from .handler import MessageHandler

logger = logging.getLogger(__name__)

class IPCServer:
    def __init__(self, handler: MessageHandler):
        self.handler = handler
        self._running = False
        self._write_lock = threading.Lock()

    def send(self, message: Message) -> None:
        """Send message to Tauri (thread-safe)."""
        with self._write_lock:
            sys.stdout.write(message.to_json() + "\n")
            sys.stdout.flush()

    def run(self) -> None:
        """Main loop - read commands from stdin."""
        self._running = True
        logger.info("IPC server started")

        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    # EOF - parent process closed pipe
                    logger.info("Stdin closed, shutting down")
                    break

                line = line.strip()
                if not line:
                    continue

                message = Message.from_json(line)
                self._handle_message(message)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                self.send(Message(
                    MessageType.ERROR,
                    {"message": f"Invalid JSON: {e}", "fatal": False}
                ))
            except Exception as e:
                logger.error(f"Handler error: {e}")
                self.send(Message(
                    MessageType.ERROR,
                    {"message": str(e), "fatal": False}
                ))

        self._running = False

    def _handle_message(self, message: Message) -> None:
        """Dispatch message to handler."""
        match message.type:
            case MessageType.INIT:
                self.handler.handle_init(message.payload, self)
            case MessageType.SKIP:
                self.handler.handle_skip(self)
            case MessageType.ACCEPT:
                self.handler.handle_accept(self)
            case MessageType.ABORT:
                self.handler.handle_abort(self)
                self._running = False
            case MessageType.STATUS:
                self.handler.handle_status(self)
            case _:
                logger.warning(f"Unknown message type: {message.type}")

    def shutdown(self) -> None:
        """Stop the server."""
        self._running = False
```

### 3.3 Message Handler

```python
# textbrush/ipc/handler.py
import base64
import io
import logging
import threading
from pathlib import Path
from ..backend import TextbrushBackend
from ..config import Config
from .protocol import Message, MessageType, InitCommand

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, config: Config):
        self.config = config
        self.backend: TextbrushBackend | None = None
        self._current_image = None
        self._image_ready_callback = None

    def handle_init(self, payload: dict, server: "IPCServer") -> None:
        """Initialize backend and start generation."""
        cmd = InitCommand(**payload)

        # Create and initialize backend
        self.backend = TextbrushBackend(self.config)

        # Send ready event when model loads
        def on_ready():
            server.send(Message(MessageType.READY))
            # Start generation
            self.backend.start_generation(
                prompt=cmd.prompt,
                seed=cmd.seed,
                aspect_ratio=cmd.aspect_ratio
            )
            # Start image delivery thread
            self._start_image_delivery(server, cmd.output_path)

        # Load model in background
        threading.Thread(
            target=self._init_backend,
            args=(on_ready, server),
            daemon=True
        ).start()

    def _init_backend(self, on_ready, server) -> None:
        """Load model and call ready callback."""
        try:
            self.backend.initialize()
            on_ready()
        except Exception as e:
            logger.error(f"Backend init failed: {e}")
            server.send(Message(
                MessageType.ERROR,
                {"message": str(e), "fatal": True}
            ))

    def _start_image_delivery(self, server: "IPCServer", output_path: str | None) -> None:
        """Background thread that delivers images as they're ready."""
        self._output_path = Path(output_path) if output_path else None

        def deliver_loop():
            while True:
                try:
                    buffered = self.backend.get_next_image()
                    if buffered is None:
                        break

                    self._current_image = buffered

                    # Encode image as base64
                    buffer = io.BytesIO()
                    buffered.image.save(buffer, format="PNG")
                    image_b64 = base64.b64encode(buffer.getvalue()).decode()

                    # Send to UI
                    server.send(Message(
                        MessageType.IMAGE_READY,
                        {
                            "image_data": image_b64,
                            "seed": buffered.seed,
                            "buffer_count": len(self.backend.buffer),
                            "buffer_max": self.backend.buffer.max_size
                        }
                    ))

                    # Wait for skip/accept before delivering next
                    self._wait_for_action()

                except Exception as e:
                    logger.error(f"Image delivery error: {e}")
                    break

        threading.Thread(target=deliver_loop, daemon=True).start()

    def handle_skip(self, server: "IPCServer") -> None:
        """Skip current image."""
        self._current_image = None
        self._signal_action()

        # Send buffer status
        if self.backend:
            server.send(Message(
                MessageType.BUFFER_STATUS,
                {
                    "count": len(self.backend.buffer),
                    "max": self.backend.buffer.max_size,
                    "generating": True
                }
            ))

    def handle_accept(self, server: "IPCServer") -> None:
        """Accept current image and save."""
        if not self._current_image or not self.backend:
            server.send(Message(
                MessageType.ERROR,
                {"message": "No image to accept", "fatal": False}
            ))
            return

        try:
            path = self.backend.accept_current(self._output_path)
            server.send(Message(
                MessageType.ACCEPTED,
                {"path": str(path.absolute())}
            ))
        except Exception as e:
            server.send(Message(
                MessageType.ERROR,
                {"message": str(e), "fatal": False}
            ))

    def handle_abort(self, server: "IPCServer") -> None:
        """Abort generation and cleanup."""
        if self.backend:
            self.backend.abort()
        server.send(Message(MessageType.ABORTED))

    def handle_status(self, server: "IPCServer") -> None:
        """Send current status."""
        if self.backend:
            server.send(Message(
                MessageType.BUFFER_STATUS,
                {
                    "count": len(self.backend.buffer),
                    "max": self.backend.buffer.max_size,
                    "generating": self.backend._worker is not None
                }
            ))
```

### 3.4 Tauri Sidecar Integration

**Rust side (`src-tauri/src/sidecar.rs`):**

```rust
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use serde::{Deserialize, Serialize};
use tauri::Manager;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct IpcMessage {
    #[serde(rename = "type")]
    pub msg_type: String,
    pub payload: serde_json::Value,
}

pub struct Sidecar {
    process: Child,
    stdin: Arc<Mutex<std::process::ChildStdin>>,
}

impl Sidecar {
    pub fn spawn(python_path: &str, args: &[&str]) -> Result<Self, String> {
        let mut process = Command::new(python_path)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

        let stdin = process.stdin.take()
            .ok_or("Failed to get stdin")?;

        Ok(Self {
            process,
            stdin: Arc::new(Mutex::new(stdin)),
        })
    }

    pub fn send(&self, message: &IpcMessage) -> Result<(), String> {
        let json = serde_json::to_string(message)
            .map_err(|e| format!("JSON error: {}", e))?;

        let mut stdin = self.stdin.lock()
            .map_err(|e| format!("Lock error: {}", e))?;

        writeln!(stdin, "{}", json)
            .map_err(|e| format!("Write error: {}", e))?;

        stdin.flush()
            .map_err(|e| format!("Flush error: {}", e))?;

        Ok(())
    }

    pub fn start_reader<F>(&mut self, on_message: F)
    where
        F: Fn(IpcMessage) + Send + 'static,
    {
        let stdout = self.process.stdout.take().unwrap();

        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(line) = line {
                    if let Ok(msg) = serde_json::from_str::<IpcMessage>(&line) {
                        on_message(msg);
                    }
                }
            }
        });
    }

    pub fn kill(&mut self) -> Result<(), String> {
        self.process.kill()
            .map_err(|e| format!("Kill error: {}", e))
    }
}
```

### 3.5 Tauri Commands

```rust
// src-tauri/src/commands.rs
use tauri::{command, State, Window};
use crate::sidecar::{Sidecar, IpcMessage};
use std::sync::Mutex;

pub struct AppState {
    pub sidecar: Mutex<Option<Sidecar>>,
}

#[command]
pub async fn init_generation(
    state: State<'_, AppState>,
    window: Window,
    prompt: String,
    output_path: Option<String>,
    seed: Option<i64>,
    aspect_ratio: String,
) -> Result<(), String> {
    let mut sidecar = Sidecar::spawn("python", &["-m", "textbrush.ipc"])?;

    // Set up message handler
    let window_clone = window.clone();
    sidecar.start_reader(move |msg| {
        window_clone.emit("sidecar-message", msg).ok();
    });

    // Send init command
    sidecar.send(&IpcMessage {
        msg_type: "init".to_string(),
        payload: serde_json::json!({
            "prompt": prompt,
            "output_path": output_path,
            "seed": seed,
            "aspect_ratio": aspect_ratio,
        }),
    })?;

    *state.sidecar.lock().unwrap() = Some(sidecar);
    Ok(())
}

#[command]
pub fn skip_image(state: State<'_, AppState>) -> Result<(), String> {
    if let Some(sidecar) = state.sidecar.lock().unwrap().as_ref() {
        sidecar.send(&IpcMessage {
            msg_type: "skip".to_string(),
            payload: serde_json::Value::Null,
        })?;
    }
    Ok(())
}

#[command]
pub fn accept_image(state: State<'_, AppState>) -> Result<(), String> {
    if let Some(sidecar) = state.sidecar.lock().unwrap().as_ref() {
        sidecar.send(&IpcMessage {
            msg_type: "accept".to_string(),
            payload: serde_json::Value::Null,
        })?;
    }
    Ok(())
}

#[command]
pub fn abort_generation(state: State<'_, AppState>) -> Result<(), String> {
    if let Some(mut sidecar) = state.sidecar.lock().unwrap().take() {
        sidecar.send(&IpcMessage {
            msg_type: "abort".to_string(),
            payload: serde_json::Value::Null,
        }).ok();
        sidecar.kill().ok();
    }
    Ok(())
}
```

### 3.6 Python Entry Point

```python
# textbrush/ipc/__main__.py
"""IPC server entry point for sidecar process."""
import logging
import sys
from ..config import load_config
from .server import IPCServer
from .handler import MessageHandler

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr  # Logs go to stderr, IPC goes to stdout
    )

    config = load_config()
    handler = MessageHandler(config)
    server = IPCServer(handler)

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        if handler.backend:
            handler.backend.shutdown()

if __name__ == "__main__":
    main()
```

### 3.7 Minimal Test UI

Simple HTML/JS to verify IPC works:

```html
<!-- src-tauri/ui/index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Textbrush</title>
    <style>
        body { font-family: system-ui; padding: 20px; background: #1a1a1a; color: white; }
        #image { max-width: 512px; max-height: 512px; border: 1px solid #333; }
        .controls { margin-top: 20px; }
        button { padding: 10px 20px; margin-right: 10px; cursor: pointer; }
        #status { margin-top: 20px; font-family: monospace; }
    </style>
</head>
<body>
    <h1>Textbrush Test UI</h1>
    <div id="image-container">
        <img id="image" src="" alt="Generated image" />
    </div>
    <div class="controls">
        <button id="skip">Skip (Space)</button>
        <button id="accept">Accept (Enter)</button>
        <button id="abort">Abort (Esc)</button>
    </div>
    <div id="status">Status: Waiting...</div>

    <script type="module" src="/main.js"></script>
</body>
</html>
```

```javascript
// src-tauri/ui/main.js
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

let currentImage = null;

// Listen for sidecar messages
listen('sidecar-message', (event) => {
    const msg = event.payload;
    handleMessage(msg);
});

function handleMessage(msg) {
    const status = document.getElementById('status');

    switch (msg.type) {
        case 'ready':
            status.textContent = 'Status: Model loaded, generating...';
            break;
        case 'image_ready':
            document.getElementById('image').src =
                `data:image/png;base64,${msg.payload.image_data}`;
            status.textContent =
                `Status: Image ready (seed: ${msg.payload.seed}, buffer: ${msg.payload.buffer_count}/${msg.payload.buffer_max})`;
            break;
        case 'accepted':
            status.textContent = `Status: Saved to ${msg.payload.path}`;
            setTimeout(() => window.close(), 1000);
            break;
        case 'aborted':
            status.textContent = 'Status: Aborted';
            setTimeout(() => window.close(), 500);
            break;
        case 'error':
            status.textContent = `Error: ${msg.payload.message}`;
            break;
    }
}

// Button handlers
document.getElementById('skip').onclick = () => invoke('skip_image');
document.getElementById('accept').onclick = () => invoke('accept_image');
document.getElementById('abort').onclick = () => invoke('abort_generation');

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === ' ' || e.key === 'ArrowRight') {
        invoke('skip_image');
    } else if (e.key === 'Enter') {
        invoke('accept_image');
    } else if (e.key === 'Escape') {
        invoke('abort_generation');
    }
});

// Start generation when window opens (get args from CLI)
// In real implementation, args come from Tauri
invoke('init_generation', {
    prompt: 'A watercolor cat',
    aspectRatio: '1:1'
});
```

## Acceptance Criteria

1. [ ] Python IPC server starts and accepts JSON commands
2. [ ] Tauri spawns Python sidecar correctly
3. [ ] Init command loads model and starts generation
4. [ ] Image data transfers via base64 encoding
5. [ ] Skip command advances to next image
6. [ ] Accept command saves image and returns path
7. [ ] Abort command stops generation cleanly
8. [ ] UI closes after accept/abort
9. [ ] Keyboard shortcuts work (Enter/Space/Esc)

## Testing

```python
# tests/test_ipc_protocol.py
def test_message_serialization():
    """Messages serialize/deserialize correctly."""

def test_init_command_validation():
    """Init command validates required fields."""

# tests/test_ipc_server.py
def test_server_handles_commands():
    """Server dispatches commands to handler."""

def test_server_handles_invalid_json():
    """Server recovers from malformed input."""

# Integration test (requires model)
@pytest.mark.slow
def test_full_ipc_cycle():
    """Init → generate → skip → accept flow works."""
```
