// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod commands_update_config;
mod exit_handlers;
mod launch_args;
mod sidecar;

use commands::AppState;
use std::sync::Mutex;
use tauri::Manager;

/* Main Application Entry Point
 *
 * CONTRACT:
 *   Purpose: Initialize and launch Tauri application with all IPC command handlers registered.
 *
 *   Inputs: None (command-line arguments handled by Tauri framework)
 *
 *   Outputs:
 *     - Running Tauri application with window and IPC handlers
 *     - Process exit when application closes
 *
 *   Invariants:
 *     - AppState managed with Tauri state management (thread-safe Mutex)
 *     - All commands registered before application runs
 *     - Application expects exactly one window (configured in tauri.conf.json)
 *
 *   Properties:
 *     - Single window application
 *     - State shared across all IPC commands via Tauri's managed state
 *     - Panic on initialization failure (via expect)
 *
 *   Registered Commands:
 *     From commands module:
 *       - init_generation: Start image generation with Python sidecar
 *       - skip_image: Skip current image, show next from buffer
 *       - accept_image: Accept current image, trigger save
 *       - abort_generation: Abort generation, kill sidecar
 *
 *     From exit_handlers module (NEW):
 *       - print_and_exit: Print path to stdout and exit with code 0
 *       - abort_exit: Exit with code 1 (no output)
 *
 *   Algorithm:
 *     1. Build Tauri application with tauri::Builder::default()
 *     2. Register managed state: AppState { sidecar: Mutex::new(None) }
 *     3. Register invoke handler with tauri::generate_handler! macro
 *        - Include all 7 commands (4 existing + 2 exit handlers + 1 launch_args)
 *     4. Call .run() with tauri::generate_context!()
 *     5. Panic with error message if run fails
 *
 *   Changes from Previous Version:
 *     - Added: mod exit_handlers
 *     - Added: mod launch_args
 *     - Added: exit_handlers::print_and_exit to invoke handler
 *     - Added: exit_handlers::abort_exit to invoke handler
 *     - Added: launch_args::get_launch_args to invoke handler
 *
 * IMPLEMENTATION GUIDANCE:
 *   - Add `mod exit_handlers;` and `mod launch_args;` declarations at top
 *   - Import all commands in generate_handler! macro:
 *     tauri::generate_handler![
 *         commands::init_generation,
 *         commands::skip_image,
 *         commands::accept_image,
 *         commands::abort_generation,
 *         exit_handlers::print_and_exit,
 *         exit_handlers::abort_exit,
 *         launch_args::get_launch_args,
 *     ]
 *   - Keep all existing code unchanged (AppState, other commands)
 *   - Ensure Cargo.toml has no additional dependencies (std::process in stdlib)
 */

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
            commands::pause_generation,
            commands_update_config::update_generation_config,
            exit_handlers::print_and_exit,
            exit_handlers::print_paths_and_exit,
            exit_handlers::abort_exit,
            launch_args::get_launch_args,
        ])
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();
            window.on_window_event(|event| {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    std::process::exit(1);
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
