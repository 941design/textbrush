// Launch arguments handler for UI initialization
//
// Provides command to retrieve CLI arguments passed to the application,
// enabling JavaScript UI to access prompt, output path, seed, and aspect ratio.

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct LaunchArgs {
    pub prompt: String,
    pub output_path: Option<String>,
    pub seed: Option<i64>,
    pub aspect_ratio: String,
    pub buffer_max: u32,
    pub width: u32,
    pub height: u32,
}

/// Get default resolution for an aspect ratio.
/// Returns the first (smallest) resolution for each ratio, matching
/// SUPPORTED_RATIOS[ratio][0] in textbrush/cli.py and the first entry in
/// ASPECT_RATIO_RESOLUTIONS in src-tauri/ui/config_controls.ts.
fn get_default_resolution(aspect_ratio: &str) -> (u32, u32) {
    match aspect_ratio {
        "1:1" => (256, 256),
        "16:9" => (640, 360),
        "3:1" => (900, 300),
        "4:1" => (1200, 300),
        "4:5" => (540, 675),
        "9:16" => (360, 640),
        _ => (256, 256), // Fallback to square
    }
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
/// IMPLEMENTATION GUIDANCE:
///   - Mark as #[tauri::command]
///   - Return Result<LaunchArgs, String> for error handling
///   - Prompt is required; return error if not provided
///
/// IMPLEMENTATION GUIDANCE (Production Version - Future):
///   - Access Tauri's CLI argument parsing or std::env::args()
///   - Parse arguments with clap or manual parsing
///   - Validate prompt is provided (required argument)
///   - Return error if required arguments missing
#[tauri::command]
pub fn get_launch_args() -> Result<LaunchArgs, String> {
    let args: Vec<String> = std::env::args().collect();

    let mut prompt = String::new();
    let mut output_path: Option<String> = None;
    let mut seed: Option<i64> = None;
    let mut aspect_ratio = "1:1".to_string();
    let mut buffer_max: u32 = 8;
    let mut width: Option<u32> = None;
    let mut height: Option<u32> = None;

    let mut i = 1; // Skip program name
    while i < args.len() {
        match args[i].as_str() {
            "--prompt" => {
                if i + 1 < args.len() {
                    prompt = args[i + 1].clone();
                    i += 2;
                } else {
                    return Err("--prompt requires a value".to_string());
                }
            }
            "--out" => {
                if i + 1 < args.len() {
                    output_path = Some(args[i + 1].clone());
                    i += 2;
                } else {
                    return Err("--out requires a value".to_string());
                }
            }
            "--seed" => {
                if i + 1 < args.len() {
                    seed = Some(args[i + 1].parse().map_err(|_| "Invalid seed value")?);
                    i += 2;
                } else {
                    return Err("--seed requires a value".to_string());
                }
            }
            "--aspect-ratio" => {
                if i + 1 < args.len() {
                    aspect_ratio = args[i + 1].clone();
                    i += 2;
                } else {
                    return Err("--aspect-ratio requires a value".to_string());
                }
            }
            "--buffer-max" => {
                if i + 1 < args.len() {
                    buffer_max = args[i + 1]
                        .parse()
                        .map_err(|_| "Invalid buffer-max value")?;
                    i += 2;
                } else {
                    return Err("--buffer-max requires a value".to_string());
                }
            }
            "--width" => {
                if i + 1 < args.len() {
                    width = Some(args[i + 1].parse().map_err(|_| "Invalid width value")?);
                    i += 2;
                } else {
                    return Err("--width requires a value".to_string());
                }
            }
            "--height" => {
                if i + 1 < args.len() {
                    height = Some(args[i + 1].parse().map_err(|_| "Invalid height value")?);
                    i += 2;
                } else {
                    return Err("--height requires a value".to_string());
                }
            }
            _ => {
                i += 1; // Skip unknown arguments
            }
        }
    }

    // Prompt is required
    if prompt.is_empty() {
        return Err("--prompt is required".to_string());
    }

    // Use default resolution for aspect ratio if dimensions not specified
    let (default_width, default_height) = get_default_resolution(&aspect_ratio);
    let final_width = width.unwrap_or(default_width);
    let final_height = height.unwrap_or(default_height);

    Ok(LaunchArgs {
        prompt,
        output_path,
        seed,
        aspect_ratio,
        buffer_max,
        width: final_width,
        height: final_height,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn get_launch_args_requires_prompt() {
        // In test environment, CLI args won't include --prompt
        let result = get_launch_args();
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "--prompt is required");
    }

    #[test]
    fn launch_args_struct_is_serializable() {
        let args = LaunchArgs {
            prompt: "test prompt".to_string(),
            output_path: Some("/tmp/test.png".to_string()),
            seed: Some(42),
            aspect_ratio: "16:9".to_string(),
            buffer_max: 4,
            width: 1920,
            height: 1080,
        };
        let json = serde_json::to_string(&args).unwrap();
        assert!(json.contains("test prompt"));
        assert!(json.contains("/tmp/test.png"));
        assert!(json.contains("42"));
        assert!(json.contains("16:9"));
        assert!(json.contains("4"));
        assert!(json.contains("1920"));
        assert!(json.contains("1080"));
    }

    #[test]
    fn get_default_resolution_returns_correct_values() {
        assert_eq!(get_default_resolution("1:1"), (256, 256));
        assert_eq!(get_default_resolution("16:9"), (640, 360));
        assert_eq!(get_default_resolution("3:1"), (900, 300));
        assert_eq!(get_default_resolution("4:1"), (1200, 300));
        assert_eq!(get_default_resolution("4:5"), (540, 675));
        assert_eq!(get_default_resolution("9:16"), (360, 640));
        // Unknown aspect ratios fall back to 256x256
        assert_eq!(get_default_resolution("unknown"), (256, 256));
    }
}
