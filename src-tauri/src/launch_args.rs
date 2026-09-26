// Launch arguments handler for UI initialization
//
// Provides command to retrieve CLI arguments passed to the application,
// enabling JavaScript UI to access prompt, output path, seed, and aspect ratio.

use serde::{Deserialize, Serialize};
use tauri::Manager;

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
    pub model_id: Option<String>,
    pub references: Vec<String>,
    pub preset: Option<String>,
}

/// Get default resolution for an aspect ratio.
/// Returns the first (smallest) resolution for each ratio, matching
/// SUPPORTED_RATIOS[ratio][0] in textbrush/cli.py and the first entry in
/// ASPECT_RATIO_RESOLUTIONS in src-tauri/ui/config_controls.ts.
fn get_default_resolution(aspect_ratio: &str) -> (u32, u32) {
    // Ordered height/width ascending, as SUPPORTED_RATIOS declares them.
    match aspect_ratio {
        "4:1" => (1200, 300),
        "3:1" => (900, 300),
        "16:9" => (640, 360),
        "4:3" => (512, 384),
        "1:1" => (256, 256),
        "4:5" => (540, 675),
        "3:4" => (384, 512),
        "9:16" => (360, 640),
        _ => (256, 256), // Fallback to square
    }
}

/// Parse the native executable's options for frontend initialization.
/// Model capability validation remains owned by the Python registry.
#[tauri::command]
pub fn get_launch_args(app: tauri::AppHandle) -> Result<LaunchArgs, String> {
    let args = parse_launch_args(std::env::args())?;
    crate::asset_access::allow_references(&app.asset_protocol_scope(), &args.references)?;
    Ok(args)
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

    let mut model_id = None;
    let mut references = Vec::new();
    let mut preset = None;
    let mut explicit_ratio = false;
    let mut i = 1;
    while i < args.len() {
        let option = args[i].as_str();
        // Older Finder launches may supply a process serial number.
        if option.starts_with("-psn_") {
            i += 1;
            continue;
        }
        if !matches!(
            option,
            "--prompt"
                | "--out"
                | "--seed"
                | "--aspect-ratio"
                | "--buffer-max"
                | "--width"
                | "--height"
                | "--model"
                | "--reference"
                | "--preset"
        ) {
            return Err(format!("Unsupported argument: {option}"));
        }
        let value = args
            .get(i + 1)
            .filter(|value| !value.is_empty() && !value.starts_with("--"))
            .ok_or_else(|| format!("{option} requires a value"))?;
        match option {
            "--prompt" => prompt = value.clone(),
            "--out" => output_path = Some(value.clone()),
            "--seed" => {
                let parsed: i64 = value.parse().map_err(|_| "Invalid --seed value")?;
                if !(-9_007_199_254_740_991..=9_007_199_254_740_991).contains(&parsed) {
                    return Err("--seed must be an exactly representable JavaScript integer".into());
                }
                seed = Some(parsed);
            }
            "--aspect-ratio" => {
                if !matches!(
                    value.as_str(),
                    "4:1" | "3:1" | "16:9" | "4:3" | "1:1" | "4:5" | "3:4" | "9:16"
                ) {
                    return Err(format!("Unsupported --aspect-ratio: {value}"));
                }
                aspect_ratio = value.clone();
                explicit_ratio = true;
            }
            "--buffer-max" | "--width" | "--height" => {
                let parsed: u32 = value
                    .parse()
                    .map_err(|_| format!("Invalid {option} value"))?;
                if parsed == 0 {
                    return Err(format!("{option} must be positive"));
                }
                match option {
                    "--width" => width = Some(parsed),
                    "--height" => height = Some(parsed),
                    _ => buffer_max = parsed,
                }
            }
            "--model" => model_id = Some(value.clone()),
            "--reference" => references.push(value.clone()),
            "--preset" => preset = Some(value.clone()),
            _ => unreachable!(),
        }
        i += 2;
    }
    if width.is_some() != height.is_some() {
        return Err("--width and --height must be supplied together".into());
    }
    if let Some(name) = preset.as_deref() {
        if width.is_some() || explicit_ratio {
            return Err(
                "--preset cannot be combined with --width/--height or --aspect-ratio".into(),
            );
        }
        // Keep these named canvases in sync with textbrush.validation.EDITING_PRESETS.
        let (ratio, w, h) = match name {
            "landscape-small" => ("4:3", 512, 384),
            "landscape-medium" => ("4:3", 768, 576),
            "landscape-large" => ("4:3", 1024, 768),
            "portrait-small" => ("3:4", 384, 512),
            "portrait-medium" => ("3:4", 576, 768),
            "portrait-large" => ("3:4", 768, 1024),
            _ => return Err(format!("Unsupported --preset: {name}")),
        };
        aspect_ratio = ratio.into();
        width = Some(w);
        height = Some(h);
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
        model_id,
        references,
        preset,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(args: &[&str]) -> Result<LaunchArgs, String> {
        parse_launch_args(
            std::iter::once("textbrush")
                .chain(args.iter().copied())
                .map(String::from),
        )
    }

    #[test]
    fn forwards_model_ordered_duplicate_references_and_preset() {
        let args = parse(&[
            "--model",
            "flux2-klein-4b",
            "--reference",
            "/a b.png",
            "--reference",
            "/c.png",
            "--reference",
            "/a b.png",
            "--preset",
            "portrait-medium",
            "--buffer-max",
            "3",
            "--seed",
            "0",
        ])
        .unwrap();
        assert_eq!(
            serde_json::to_value(args).unwrap(),
            serde_json::json!({
                "prompt": DEFAULT_PROMPT, "output_path": null, "seed": 0,
                "aspect_ratio": "3:4", "buffer_max": 3, "width": 576, "height": 768,
                "model_id": "flux2-klein-4b", "references": ["/a b.png", "/c.png", "/a b.png"],
                "preset": "portrait-medium",
            })
        );
    }

    #[test]
    fn rejects_missing_invalid_and_unknown_options() {
        for option in [
            "--model",
            "--reference",
            "--preset",
            "--prompt",
            "--out",
            "--seed",
            "--aspect-ratio",
            "--buffer-max",
            "--width",
            "--height",
        ] {
            assert_eq!(
                parse(&[option]).unwrap_err(),
                format!("{option} requires a value")
            );
            assert_eq!(
                parse(&[option, "--prompt", "cat"]).unwrap_err(),
                format!("{option} requires a value")
            );
        }
        for args in [
            vec!["--width", "0"],
            vec!["--height", "bad"],
            vec!["--buffer-max", "0"],
            vec!["--seed", "bad"],
            vec!["--seed", "9007199254740992"],
            vec!["--aspect-ratio", "7:2"],
            vec!["--preset", "unknown"],
            vec!["--width", "512"],
            vec!["--preset", "portrait-medium", "--aspect-ratio", "1:1"],
            vec![
                "--preset",
                "portrait-medium",
                "--width",
                "512",
                "--height",
                "512",
            ],
            vec!["--headless"],
            vec!["surprise"],
        ] {
            assert!(parse(&args).is_err(), "accepted invalid args: {args:?}");
        }
    }

    #[test]
    fn canvas_selection_is_independent_of_model_and_references() {
        for model in ["flux1-schnell", "flux1-kontext-dev", "flux2-klein-4b"] {
            for (size, ratio, width, height) in [
                (vec![], "1:1", 256, 256),
                (vec!["--aspect-ratio", "16:9"], "16:9", 640, 360),
                (vec!["--aspect-ratio", "9:16"], "9:16", 360, 640),
                (vec!["--preset", "portrait-medium"], "3:4", 576, 768),
            ] {
                let mut options = vec!["--model", model, "--reference", "/ref image.png"];
                options.extend(size);
                let args = parse(&options).unwrap();
                assert_eq!(
                    (args.aspect_ratio.as_str(), args.width, args.height),
                    (ratio, width, height)
                );
            }
        }
    }

    #[test]
    fn tolerates_finder_serial_and_uses_ratio_size() {
        let args = parse(&["-psn_0_123", "--aspect-ratio", "16:9"]).unwrap();
        assert_eq!((args.width, args.height), (640, 360));
        assert!(args.model_id.is_none());
        assert!(args.references.is_empty());
    }

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
            model_id: None,
            references: vec![],
            preset: None,
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
        // 4:3 and 3:4 are the landscape and portrait ladders that used to
        // be reachable only as editing presets; they are ordinary ratios
        // in the one output-size group now.
        assert_eq!(get_default_resolution("4:3"), (512, 384));
        assert_eq!(get_default_resolution("3:4"), (384, 512));
        assert_eq!(get_default_resolution("9:16"), (360, 640));
        // Unknown aspect ratios fall back to 256x256
        assert_eq!(get_default_resolution("unknown"), (256, 256));
    }
}
