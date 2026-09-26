//! Packaged apps require an external Python installation; never search the checkout.
use crate::sidecar::Sidecar;

const BOOTSTRAP: &str = r#"
import json, runpy, sys

def fail(message):
    print(json.dumps({'type': 'error', 'payload': {
        'message': message, 'fatal': True, 'operation': 'startup'
    }}), flush=True)
    raise SystemExit(1)

if sys.version_info < (3, 11):
    fail('Textbrush requires Python 3.11 or newer. Set TEXTBRUSH_PYTHON to a supported interpreter.')
try:
    runpy.run_module('textbrush.ipc', run_name='__main__')
except ImportError as error:
    name = error.name or 'a required module'
    fail('The selected Python runtime cannot import ' + name +
         '. Install textbrush[model] in that environment, or set TEXTBRUSH_PYTHON to its Python executable.')
"#;

fn program(configured: Option<&str>) -> Result<&str, String> {
    match configured {
        Some("") => Err("TEXTBRUSH_PYTHON must name a Python executable".into()),
        Some(value) => Ok(value),
        None => Ok("python3"),
    }
}

pub fn spawn(configured: Option<&str>) -> Result<Sidecar, String> {
    // -I excludes cwd/PYTHONPATH/user-site imports, preserving the selected
    // environment even when the desktop is launched from a source checkout.
    Sidecar::spawn(program(configured)?, &["-I", "-c", BOOTSTRAP]).map_err(|error| {
        format!("Cannot start the selected Python runtime. Install Python 3.11+ with textbrush[model], or set TEXTBRUSH_PYTHON to that environment's executable. {error}")
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc;
    use std::time::Duration;

    #[test]
    fn selection_preserves_paths_with_spaces_and_does_not_fallback() {
        assert_eq!(program(None).unwrap(), "python3");
        assert_eq!(
            program(Some("/runtime with spaces/bin/python")).unwrap(),
            "/runtime with spaces/bin/python"
        );
        assert!(program(Some("")).is_err());
        let directory = tempfile::tempdir().unwrap();
        let missing = directory.path().join("missing python");
        let error = spawn(Some(missing.to_str().unwrap())).unwrap_err();
        assert!(error.contains("TEXTBRUSH_PYTHON"));
        assert!(error.contains("textbrush[model]"));
    }

    #[test]
    fn startup_reports_missing_package_and_unsupported_version_once() {
        for (prefix, expected) in [
            ("", "textbrush[model]"),
            (
                "import sys; sys.version_info = (3, 10)\n",
                "Python 3.11 or newer",
            ),
        ] {
            let script = format!("{prefix}{BOOTSTRAP}");
            // Disable site-packages to deterministically exercise missing-package
            // diagnostics regardless of the test host's Python installation.
            let mut child = Sidecar::spawn("python3", &["-I", "-S", "-c", &script]).unwrap();
            let (tx, rx) = mpsc::channel();
            child.start_reader(move |message| {
                tx.send(message).unwrap();
            });
            let message = rx.recv_timeout(Duration::from_secs(3)).unwrap();
            assert_eq!(message.msg_type, "error");
            assert_eq!(message.payload["operation"], "startup");
            assert!(message.payload["message"]
                .as_str()
                .unwrap()
                .contains(expected));
            assert!(matches!(
                rx.recv_timeout(Duration::from_secs(3)),
                Err(mpsc::RecvTimeoutError::Disconnected)
            ));
        }
    }
}
