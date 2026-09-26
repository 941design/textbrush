// Exit commands settle the sidecar before publishing the CLI exit contract.
use crate::commands::AppState;
use tauri::State;

#[tauri::command]
pub async fn print_paths_and_exit(
    state: State<'_, AppState>,
    paths: Vec<String>,
) -> Result<(), String> {
    if let Err(error) = state.shutdown() {
        eprintln!("Backend shutdown failed: {error}");
    }
    exit_with_paths(paths);
}

#[tauri::command]
pub async fn abort_exit(state: State<'_, AppState>) -> Result<(), String> {
    if let Err(error) = state.shutdown() {
        eprintln!("Backend shutdown failed: {error}");
    }
    exit_abort();
}

fn exit_with_paths(paths: Vec<String>) -> ! {
    if paths.is_empty() {
        exit_abort();
    }
    for path in paths {
        println!("{}", path);
    }
    std::process::exit(0);
}

pub(crate) fn exit_abort() -> ! {
    std::process::exit(1);
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    // The child runs the real terminal function. Only this ignored probe
    // reads the scenario variable; production has no test-only exit path.
    #[test]
    #[ignore]
    fn exit_probe() {
        match std::env::var("TEXTBRUSH_EXIT_TEST_CASE").unwrap().as_str() {
            "abort" => exit_abort(),
            "empty" => exit_with_paths(vec![]),
            "single" => exit_with_paths(vec!["/tmp/a path.png".into()]),
            "multiple" => exit_with_paths(vec![
                "/tmp/z last.png".into(),
                "/tmp/ä first.png".into(),
                "/tmp/z last.png".into(),
                "/tmp/b final.png".into(),
            ]),
            _ => panic!("unknown exit scenario"),
        }
    }

    #[test]
    fn production_exit_codes_stdout_and_order() {
        for (scenario, code, stdout) in [
            ("abort", 1, ""),
            ("empty", 1, ""),
            ("single", 0, "/tmp/a path.png\n"),
            (
                "multiple",
                0,
                "/tmp/z last.png\n/tmp/ä first.png\n/tmp/z last.png\n/tmp/b final.png\n",
            ),
        ] {
            let output = Command::new(std::env::current_exe().unwrap())
                .args([
                    "--exact",
                    "exit_handlers::tests::exit_probe",
                    "--ignored",
                    "--nocapture",
                    "--quiet",
                    "--color",
                    "never",
                ])
                .env("TEXTBRUSH_EXIT_TEST_CASE", scenario)
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(code), "{scenario}");
            // libtest writes this banner before invoking the probe.
            assert_eq!(
                String::from_utf8(output.stdout).unwrap(),
                format!("\nrunning 1 test\n{stdout}"),
                "{scenario}"
            );
            assert!(output.stderr.is_empty(), "{scenario}: {:?}", output.stderr);
        }
    }
}
