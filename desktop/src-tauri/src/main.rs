// Strava Analyzer — Tauri desktop app
// Manages the Python sidecar (FastAPI server) and provides a native window

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use std::sync::Mutex;
use tauri::{Manager, State};

struct ServerState {
    pid: Mutex<Option<u32>>,
}

#[tauri::command]
fn get_server_status(state: State<ServerState>) -> String {
    let pid = state.pid.lock().unwrap();
    match *pid {
        Some(p) => format!("running (pid: {})", p),
        None => "stopped".to_string(),
    }
}

#[tauri::command]
fn start_server(state: State<ServerState>) -> Result<String, String> {
    let mut pid_lock = state.pid.lock().unwrap();
    if pid_lock.is_some() {
        return Ok("Server already running".to_string());
    }

    // Find the Python sidecar
    let sidecar_path = get_sidecar_path();

    let child = Command::new(&sidecar_path)
        .spawn()
        .map_err(|e| format!("Failed to start server: {}", e))?;

    *pid_lock = Some(child.id());
    Ok(format!("Server started (pid: {})", child.id()))
}

#[tauri::command]
fn stop_server(state: State<ServerState>) -> Result<String, String> {
    let mut pid_lock = state.pid.lock().unwrap();
    if let Some(pid) = *pid_lock {
        #[cfg(unix)]
        {
            unsafe {
                libc::kill(pid as i32, libc::SIGTERM);
            }
        }
        *pid_lock = None;
        Ok("Server stopped".to_string())
    } else {
        Ok("Server was not running".to_string())
    }
}

fn get_sidecar_path() -> String {
    // In development: use the Python venv directly
    // In production: use the bundled PyInstaller binary
    let resource_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_default();

    let sidecar = resource_dir.join("sidecar").join("StravaAnalyzer");
    if sidecar.exists() {
        return sidecar.to_string_lossy().to_string();
    }

    // Fallback: development mode — run from venv
    "python".to_string()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(ServerState {
            pid: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            get_server_status,
            start_server,
            stop_server,
        ])
        .setup(|app| {
            // Auto-start the Python server on app launch
            let state = app.state::<ServerState>();
            let _ = start_server_internal(state.inner());

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Stop server when window closes
                let state = window.state::<ServerState>();
                let mut pid_lock = state.pid.lock().unwrap();
                if let Some(pid) = *pid_lock {
                    #[cfg(unix)]
                    unsafe {
                        libc::kill(pid as i32, libc::SIGTERM);
                    }
                    *pid_lock = None;
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn start_server_internal(state: &ServerState) -> Result<(), String> {
    let mut pid_lock = state.pid.lock().unwrap();
    let sidecar_path = get_sidecar_path();

    let child = Command::new(&sidecar_path)
        .spawn()
        .map_err(|e| format!("Failed to start server: {}", e))?;

    *pid_lock = Some(child.id());
    Ok(())
}
