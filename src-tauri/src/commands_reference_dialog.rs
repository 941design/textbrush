use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::{DialogExt, FilePath};

fn paths_to_strings(paths: Vec<FilePath>) -> Result<Vec<String>, String> {
    paths
        .into_iter()
        .map(|path| {
            path.into_path()
                .map(|path| path.to_string_lossy().into_owned())
                .map_err(|error| error.to_string())
        })
        .collect()
}

// `async` is load-bearing: Tauri runs synchronous commands on the main
// thread, and a blocking dialog there stalls the event loop the dialog
// itself needs -- the window freezes with no error. An async command runs
// on the async runtime's pool, where the plugin documents the blocking
// pickers as safe.
#[tauri::command]
pub async fn pick_reference_files(app: AppHandle) -> Result<Vec<String>, String> {
    let picked = app
        .dialog()
        .file()
        .add_filter(
            "Images",
            &["png", "jpg", "jpeg", "webp", "PNG", "JPG", "JPEG", "WEBP"],
        )
        .blocking_pick_files()
        .unwrap_or_default();
    let paths = paths_to_strings(picked)?;
    crate::asset_access::allow_references(&app.asset_protocol_scope(), &paths)?;
    Ok(paths)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn path_conversion_preserves_order_and_duplicates() {
        let paths = vec![
            FilePath::from(PathBuf::from("/tmp/first.png")),
            FilePath::from(PathBuf::from("/tmp/second.JPG")),
            FilePath::from(PathBuf::from("/tmp/first.png")),
        ];
        assert_eq!(
            paths_to_strings(paths).unwrap(),
            vec!["/tmp/first.png", "/tmp/second.JPG", "/tmp/first.png"]
        );
    }

    #[test]
    fn cancellation_yields_empty_paths() {
        assert!(paths_to_strings(vec![]).unwrap().is_empty());
    }
}
