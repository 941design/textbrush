// Exit handlers for CLI contract compliance
//
// Provides Tauri commands for controlled application exit with proper stdout handling
// and exit codes as required by the CLI specification.

/// Print multiple accepted image paths to stdout and exit with success code.
///
/// CONTRACT:
///   Inputs:
///     - paths: Vector of file path strings (absolute or relative) to saved images
///
///   Outputs:
///     - Prints each path to stdout, one per line
///     - Process exits with code 0 (success) if paths non-empty
///     - Process exits with code 1 (failure) if paths empty (no images to accept)
///
///   Invariants:
///     - Each path is printed exactly as provided (no modification)
///     - Paths separated by newlines (one path per line)
///     - Stdout is flushed before exit (ensures output visible)
///     - Exit code is 0 if paths.len() > 0, else 1
///     - No other output to stdout (no logging, no extra formatting)
///
///   Properties:
///     - Newline-separated: each path on its own line
///     - Order preserved: paths printed in same order as input vector
///     - Empty handling: empty vector exits with code 1 (same as abort)
///     - Backward compatible: single-element vector behaves like print_and_exit
///     - CLI contract: satisfies multi-path output requirement
///
///   Algorithm:
///     1. Check if paths.is_empty()
///     2. If yes: call std::process::exit(1) (nothing to accept)
///     3. For each path in paths:
///        a. Call println!("{}", path)
///     4. Call std::process::exit(0) to terminate with success code
///
/// IMPLEMENTATION GUIDANCE:
///   - Use for loop over paths vector
///   - Use println! for each path (automatically newline-separated)
///   - Exit code 1 if empty (no images = abort scenario)
///   - Exit code 0 if at least one path printed
///   - Mark as #[tauri::command] for IPC registration
#[tauri::command]
pub fn print_paths_and_exit(paths: Vec<String>) {
    if paths.is_empty() {
        std::process::exit(1);
    }
    for path in paths {
        println!("{}", path);
    }
    std::process::exit(0);
}

/// Exit process with abort code (non-zero).
///
/// CONTRACT:
///   Inputs: None
///
///   Outputs:
///     - No output to stdout (empty stdout)
///     - Process exits with code 1 (failure/abort)
///
///   Invariants:
///     - Exit code is always 1 (failure)
///     - No stdout output (silent exit)
///     - No stderr output (quiet abort)
///
///   Properties:
///     - Synchronous: immediately exits
///     - Terminal: does not return (process terminates)
///     - CLI contract: satisfies "no output, exit non-zero" requirement for abort
///
///   Algorithm:
///     1. Call std::process::exit(1) to terminate with failure code
///
/// IMPLEMENTATION GUIDANCE:
///   - Use std::process::exit(1) directly
///   - No println! or eprintln! (must be silent)
///   - Mark as #[tauri::command] for IPC registration
#[tauri::command]
pub fn abort_exit() {
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
            "abort" => abort_exit(),
            "empty" => print_paths_and_exit(vec![]),
            "single" => print_paths_and_exit(vec!["/tmp/a path.png".into()]),
            "multiple" => print_paths_and_exit(vec![
                "/tmp/z last.png".into(),
                "/tmp/ä first.png".into(),
                "/tmp/z last.png".into(),
                "/tmp/b final.png".into(),
            ]),
            _ => panic!("unknown exit scenario"),
        }
        panic!("exit handler returned");
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
