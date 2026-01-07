// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod sidecar;

use commands::AppState;
use std::sync::Mutex;

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            sidecar: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            commands::init_generation,
            commands::skip_image,
            commands::accept_image,
            commands::abort_generation,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
