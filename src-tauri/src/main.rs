// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod asset_access;
mod commands;
mod commands_reference_dialog;
mod commands_update_config;
mod exit_handlers;
mod launch_args;
#[cfg(any(test, not(debug_assertions)))]
mod python_runtime;
mod sidecar;

use commands::AppState;
use tauri::Manager;

// All desktop exit paths settle the sidecar before terminating the app.
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            commands::init_generation,
            commands::skip_image,
            commands::accept_image,
            commands::abort_generation,
            commands::pause_generation,
            commands::delete_image,
            commands::get_image_list,
            commands_update_config::update_generation_config,
            commands_reference_dialog::pick_reference_files,
            exit_handlers::print_paths_and_exit,
            exit_handlers::abort_exit,
            launch_args::get_launch_args,
        ])
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();
            let handle = app.handle().clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let handle = handle.clone();
                    std::thread::spawn(move || {
                        if let Err(error) = handle.state::<AppState>().shutdown() {
                            eprintln!("Backend shutdown failed: {error}");
                        }
                        exit_handlers::exit_abort();
                    });
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
