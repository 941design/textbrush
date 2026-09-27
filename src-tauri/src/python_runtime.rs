//! Packaged apps require an external Python installation; never search the checkout.
use crate::sidecar::Sidecar;
use std::path::Path;

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

fn program(configured: Option<&str>, settings: &Path) -> Result<String, String> {
    if let Some(value) = configured {
        return if value.is_empty() {
            Err("TEXTBRUSH_PYTHON must name a Python executable".into())
        } else {
            Ok(value.into())
        };
    }
    match std::fs::read_to_string(settings) {
        Ok(value) => {
            let value = value.trim_end_matches(['\r', '\n']);
            if !Path::new(value).is_absolute() || value.contains(['\r', '\n']) {
                return Err(format!(
                    "{} must contain one absolute Python executable path (without quotes)",
                    settings.display()
                ));
            }
            Ok(value.into())
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok("python3".into()),
        Err(error) => Err(format!("Cannot read {}: {error}", settings.display())),
    }
}

pub fn spawn(configured: Option<&str>, settings: &Path) -> Result<Sidecar, String> {
    // -I excludes cwd/PYTHONPATH/user-site imports, preserving the selected
    // environment even when the desktop is launched from a source checkout.
    Sidecar::spawn(&program(configured, settings)?, &["-I", "-c", BOOTSTRAP]).map_err(|error| {
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
        let directory = tempfile::tempdir().unwrap();
        let settings = directory.path().join("python-path");
        assert_eq!(program(None, &settings).unwrap(), "python3");
        assert_eq!(
            program(Some("/runtime with spaces/bin/python"), &settings).unwrap(),
            "/runtime with spaces/bin/python"
        );
        assert!(program(Some(""), &settings).is_err());
        let missing = directory.path().join("missing python");
        let error = spawn(Some(missing.to_str().unwrap()), &settings).unwrap_err();
        assert!(error.contains("TEXTBRUSH_PYTHON"));
        assert!(error.contains("textbrush[model]"));
    }

    #[test]
    fn desktop_settings_preserve_spaces_and_environment_precedence() {
        let directory = tempfile::tempdir().unwrap();
        let settings = directory.path().join("python-path");
        let missing = directory.path().join("runtime with spaces/bin/python");
        std::fs::write(&settings, format!("{}\n", missing.display())).unwrap();
        assert_eq!(program(None, &settings).unwrap(), missing.to_str().unwrap());
        assert!(spawn(None, &settings).unwrap_err().contains("Cannot start"));
        assert_eq!(program(Some("override"), &settings).unwrap(), "override");
        assert!(program(Some(""), &settings).is_err());
    }

    #[test]
    fn invalid_desktop_settings_fail_without_silent_fallback() {
        let directory = tempfile::tempdir().unwrap();
        let settings = directory.path().join("python-path");
        for value in [
            "",
            "python3",
            "~/venv/bin/python",
            "\"/python\"",
            "/one\n/two",
        ] {
            std::fs::write(&settings, value).unwrap();
            assert!(program(None, &settings).unwrap_err().contains("absolute"));
        }
        std::fs::write(&settings, [0xff]).unwrap();
        assert!(program(None, &settings)
            .unwrap_err()
            .contains("Cannot read"));
        // An explicit environment setting does not read a stale settings file.
        assert_eq!(program(Some("override"), &settings).unwrap(), "override");
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
