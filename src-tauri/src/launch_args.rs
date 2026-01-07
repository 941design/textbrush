// Launch arguments handler for UI initialization
//
// Provides command to retrieve CLI arguments passed to the application,
// enabling JavaScript UI to access prompt, output path, seed, and aspect ratio.

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone)]
pub struct LaunchArgs {
    pub prompt: String,
    pub output_path: Option<String>,
    pub seed: Option<i64>,
    pub aspect_ratio: String,
}

/// Get launch arguments for UI initialization.
///
/// CONTRACT:
///   Inputs: None (reads from environment/CLI args)
///
///   Outputs:
///     - Result<LaunchArgs, String>: Launch arguments or error message
///
///   Invariants:
///     - Returns arguments used to launch the application
///     - If no arguments found: returns default values for testing
///     - Arguments match what would be passed to init_generation
///
///   Properties:
///     - Synchronous: returns immediately
///     - Stateless: does not modify application state
///     - Fallback: provides sensible defaults if no CLI args
///
///   LaunchArgs Structure:
///     - prompt: text description for image generation (required)
///     - output_path: optional path where accepted image should be saved
///     - seed: optional random seed for reproducibility
///     - aspect_ratio: aspect ratio string (default "1:1")
///
///   Algorithm:
///     For initial implementation (testing):
///       1. Return default LaunchArgs with test prompt
///       2. In production: parse from std::env::args() or Tauri config
///
///     Production implementation (future):
///       1. Access Tauri App state or CLI arguments
///       2. Parse --prompt, --output-path, --seed, --aspect-ratio flags
///       3. Validate required arguments (prompt)
///       4. Return LaunchArgs struct
///
/// IMPLEMENTATION GUIDANCE (Initial Version):
///   - Return hardcoded LaunchArgs for testing:
///     LaunchArgs {
///       prompt: "A watercolor painting of a cat".to_string(),
///       output_path: None,
///       seed: None,
///       aspect_ratio: "1:1".to_string(),
///     }
///   - Mark as #[tauri::command]
///   - Return Result<LaunchArgs, String> for error handling
///
/// IMPLEMENTATION GUIDANCE (Production Version - Future):
///   - Access Tauri's CLI argument parsing or std::env::args()
///   - Parse arguments with clap or manual parsing
///   - Validate prompt is provided (required argument)
///   - Return error if required arguments missing
#[tauri::command]
pub fn get_launch_args() -> Result<LaunchArgs, String> {
    // Initial implementation: return test arguments for development
    // TODO: In production, parse from CLI args or Tauri config
    Ok(LaunchArgs {
        prompt: "A watercolor painting of a cat".to_string(),
        output_path: None,
        seed: None,
        aspect_ratio: "1:1".to_string(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn get_launch_args_returns_valid_structure() {
        let result = get_launch_args();
        assert!(result.is_ok());
        let args = result.unwrap();
        assert!(!args.prompt.is_empty());
        assert_eq!(args.aspect_ratio, "1:1");
    }
}
