// Launch arguments handler for UI initialization
//
// Provides command to retrieve CLI arguments passed to the application,
// enabling JavaScript UI to access prompt, output path, seed, and aspect ratio.

use serde::{Deserialize, Serialize};

const DEFAULT_PROMPT: &str = "A watercolor painting of a cat";

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
///     - If no prompt argument is provided: returns bundled-app defaults
///     - Arguments match what would be passed to init_generation
///
///   Properties:
///     - Synchronous: returns immediately
///     - Stateless: does not modify application state
///     - Fallback: provides sensible defaults if no CLI args
///
///   LaunchArgs Structure:
///     - prompt: text description for image generation
///     - output_path: optional path where accepted image should be saved
///     - seed: optional random seed for reproducibility
///     - aspect_ratio: aspect ratio string (default "1:1")
///
///   Algorithm:
///       1. Parse --prompt, --out, --seed, --aspect-ratio, --buffer-max,
///          --width, and --height from process arguments
///       2. If --prompt is omitted, use bundled-app defaults so Finder launches
///          initialize the UI without extra CLI flags
///       3. Resolve width/height from explicit values or aspect-ratio defaults
///       4. Return LaunchArgs struct
///
/// IMPLEMENTATION GUIDANCE:
///   - Mark as #[tauri::command]
///   - Return Result<LaunchArgs, String> for error handling
///   - Packaged app launches must work without requiring CLI flags
#[tauri::command]
pub fn get_launch_args() -> Result<LaunchArgs, String> {
    parse_launch_args(std::env::args())
}

fn parse_launch_args<I>(args: I) -> Result<LaunchArgs, String>
where
    I: IntoIterator<Item = String>,
{
    let args: Vec<String> = args.into_iter().collect();

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

    // Finder launches packaged apps without CLI args. In that case, start with a
    // sensible default prompt so the bundled GUI can initialize normally.
    if prompt.is_empty() {
        prompt = DEFAULT_PROMPT.to_string();
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
    fn get_launch_args_uses_default_prompt_when_omitted() {
        let result = parse_launch_args(vec!["textbrush".to_string()]);
        assert!(result.is_ok());
        assert_eq!(result.unwrap().prompt, DEFAULT_PROMPT);
    }

    #[test]
    fn get_launch_args_parses_prompt_when_provided() {
        let result = parse_launch_args(vec![
            "textbrush".to_string(),
            "--prompt".to_string(),
            "sunset".to_string(),
            "--width".to_string(),
            "512".to_string(),
            "--height".to_string(),
            "512".to_string(),
        ]);

        assert!(result.is_ok());
        let args = result.unwrap();
        assert_eq!(args.prompt, "sunset");
        assert_eq!(args.width, 512);
        assert_eq!(args.height, 512);
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
