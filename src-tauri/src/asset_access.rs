//! Asset access is granted only by native launch options, the file picker,
//! and the private preview directory created for the sidecar session.
use std::path::Path;
use tauri::scope::fs::Scope;

pub fn allow_previews(scope: &Scope, directory: &Path) -> Result<(), String> {
    scope
        .allow_directory(directory, false)
        .map_err(|e| e.to_string())
}

pub fn allow_references(scope: &Scope, paths: &[String]) -> Result<(), String> {
    for path in paths {
        // Canonicalize relative paths and symlinks exactly as the asset handler
        // does. Missing/invalid references still receive Python's normal error.
        if let Ok(path) = std::fs::canonicalize(path) {
            if path.is_file() {
                scope.allow_file(path).map_err(|e| e.to_string())?;
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn real_tauri_scope_allows_only_selected_files_and_session_previews() {
        let app = tauri::test::mock_app();
        let config: tauri::Config =
            serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
        let scope = Scope::new(&app, &config.app.security.asset_protocol.scope).unwrap();
        let root = tempfile::tempdir().unwrap();
        let previews = root.path().join("private previews");
        std::fs::create_dir(&previews).unwrap();
        let preview = previews.join("image.png");
        let selected = root.path().join(".selected [1]*.png");
        let unrelated = root.path().join(".private.txt");
        let wildcard_neighbor = root.path().join(".selected 1-other.png");
        for path in [&preview, &selected, &unrelated, &wildcard_neighbor] {
            std::fs::write(path, "fixture").unwrap();
            assert!(!scope.is_allowed(path));
        }
        allow_previews(&scope, &previews).unwrap();
        allow_references(&scope, &[selected.to_string_lossy().into_owned()]).unwrap();
        assert!(scope.is_allowed(&preview));
        assert!(scope.is_allowed(&selected));
        assert!(!scope.is_allowed(&unrelated));
        assert!(!scope.is_allowed(&wildcard_neighbor));
        assert!(!scope.is_allowed(previews.join("nested/image.png")));
        assert!(!scope.is_allowed(previews.join("../.private.txt")));
        #[cfg(unix)]
        {
            let escape = previews.join("escape.png");
            std::os::unix::fs::symlink(&unrelated, &escape).unwrap();
            assert!(!scope.is_allowed(&escape));
            let chosen_link = root.path().join("chosen symlink.png");
            std::os::unix::fs::symlink(&selected, &chosen_link).unwrap();
            allow_references(&scope, &[chosen_link.to_string_lossy().into_owned()]).unwrap();
            assert!(scope.is_allowed(chosen_link));
        }
    }
}
