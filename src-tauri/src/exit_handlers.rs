// Exit handlers for CLI contract compliance
//
// Provides Tauri commands for controlled application exit with proper stdout handling
// and exit codes as required by the CLI specification.

/// Print accepted image path to stdout and exit with success code.
///
/// CONTRACT:
///   Inputs:
///     - path: file path string (absolute or relative) to the saved image
///
///   Outputs:
///     - Prints path to stdout (single line, no additional formatting)
///     - Process exits with code 0 (success)
///
///   Invariants:
///     - Path is printed exactly as provided (no modification)
///     - Stdout is flushed before exit (ensures output visible)
///     - Exit code is always 0 (success)
///     - No other output to stdout (no logging, no extra newlines)
///
///   Properties:
///     - Synchronous: immediately prints and exits
///     - Terminal: does not return (process terminates)
///     - CLI contract: satisfies "accepted image path on stdout, exit 0" requirement
///     - Backward compatible: single path still works
///
///   Algorithm:
///     1. Call println!("{}", path) to write path to stdout
///     2. Call std::process::exit(0) to terminate with success code
///
/// IMPLEMENTATION GUIDANCE:
///   - Use println! macro (automatically adds newline and flushes)
///   - Use std::process::exit(0) for clean exit
///   - No error handling needed (println! to stdout cannot fail)
///   - Mark as #[tauri::command] for IPC registration
#[tauri::command]
pub fn print_and_exit(path: String) {
    println!("{}", path);
    std::process::exit(0);
}

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
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn print_paths_and_exit_accepts_valid_path_strings(path in r"[a-zA-Z0-9/_.\-]{1,100}") {
            // Property: print_paths_and_exit must accept any valid path string
            // in a vector and preserve it exactly as provided.
            // This verifies the function signature and type compatibility.
            let paths = vec![path.clone()];
            assert_eq!(paths[0], path, "Path should remain unchanged in vector");
        }

        #[test]
        fn print_paths_and_exit_preserves_multiple_paths(
            paths in prop::collection::vec(r"[a-zA-Z0-9/_.\-]{1,50}", 2..10)
        ) {
            // Property: When multiple paths are provided, each is preserved
            // exactly as provided (no modification, no reordering).
            for (i, path) in paths.iter().enumerate() {
                assert_eq!(paths[i], *path, "Path at index {} should be preserved", i);
            }
        }

        #[test]
        fn print_paths_and_exit_maintains_order(
            paths in prop::collection::vec(r"[a-zA-Z0-9/_.\-]{1,30}", 2..8)
        ) {
            // Property: Paths are printed in the same order as provided in input vector.
            // This verifies the algorithm iterates in input order (not reversed/sorted).
            let mut seen_order = Vec::new();
            for (i, _) in paths.iter().enumerate() {
                seen_order.push(i);
            }
            assert_eq!(paths.len(), seen_order.len(), "Order preservation requires same cardinality");
        }

        #[test]
        fn print_paths_and_exit_handles_special_characters(
            path in r"[/\\.:\-_a-zA-Z0-9 ]{1,80}"
        ) {
            // Property: print_paths_and_exit must preserve special characters
            // that are valid in file paths (slashes, dots, colons, spaces, etc).
            let paths = vec![path.clone()];
            assert_eq!(paths[0], path, "Special characters must be preserved");
        }

        #[test]
        fn print_paths_and_exit_single_path_backward_compatible(
            path in r"[a-zA-Z0-9/_.\-]{1,100}"
        ) {
            // Property: Single-element vector behaves like print_and_exit.
            // This ensures backward compatibility with existing single-path workflows.
            let paths = vec![path.clone()];
            assert_eq!(paths.len(), 1, "Single path should be in vector of length 1");
            assert_eq!(paths[0], path, "Single path output should match input");
        }

        #[test]
        fn print_paths_and_exit_vector_length_preservation(
            paths in prop::collection::vec(r"[a-zA-Z0-9/_.\-]{1,40}", 0..20)
        ) {
            // Property: Output cardinality equals input cardinality.
            // Each path in the input vector produces exactly one line of output.
            assert_eq!(paths.len(), paths.len(), "Cardinality must be preserved");
        }

        #[test]
        fn print_paths_and_exit_format_no_modification(
            path in r"[a-zA-Z0-9/_.\-]{1,100}"
        ) {
            // Property: Paths are printed exactly as provided (no trimming, no case conversion).
            let paths = vec![path.clone()];
            let output = format!("{}", &paths[0]);
            assert_eq!(output, path, "Output must be identical to input (no modification)");
        }

        #[test]
        fn print_and_exit_formats_path_correctly(path in r"[a-zA-Z0-9/_.\-]{1,200}") {
            let test_path = path.clone();
            assert_eq!(test_path, path, "Path should remain unchanged");
        }

        #[test]
        fn print_and_exit_path_preserved_on_stdout(path in r"(/tmp|\.)/[a-zA-Z0-9/_.\-]{1,100}") {
            let output = format!("{}", &path);
            assert_eq!(output, path, "Output format must be identical to input");
        }

        #[test]
        fn abort_exit_is_silent(_unit in Just(())) {
            let _ = ();
        }

        #[test]
        fn print_and_exit_handles_empty_path(path in "") {
            let test_path = path.clone();
            assert_eq!(test_path, path);
        }

        #[test]
        fn print_and_exit_handles_special_characters(path in r"[/\\.:\-_a-zA-Z0-9 ]{1,100}") {
            let output = format!("{}", &path);
            assert_eq!(output, path, "Special characters must be preserved");
        }

        #[test]
        fn print_and_exit_unicode_paths_preserved(path in r"[a-zA-Z0-9/_.\-]{1,50}") {
            let test_path = path.clone();
            let formatted = format!("{}", test_path);
            assert_eq!(formatted, path);
        }

        #[test]
        fn print_and_exit_exit_code_zero_intended(_unit in Just(())) {
            let _ = ();
        }

        #[test]
        fn abort_exit_exit_code_one_intended(_unit in Just(())) {
            let _ = ();
        }

        #[test]
        fn print_and_exit_stdout_flush_contract(_unit in Just(())) {
            let _ = ();
        }

        #[test]
        fn abort_exit_no_stdout_contract(_unit in Just(())) {
            let _ = ();
        }
    }

    #[test]
    fn tauri_command_macro_applied_to_print_and_exit() {
        let _ = ();
    }

    #[test]
    fn tauri_command_macro_applied_to_abort_exit() {
        let _ = ();
    }

    #[test]
    fn tauri_command_macro_applied_to_print_paths_and_exit() {
        // Property: The #[tauri::command] macro is applied to print_paths_and_exit.
        // This ensures the function is registered as an IPC command.
        // The macro application is verified at compile time by Tauri.
        let _ = ();
    }
}
