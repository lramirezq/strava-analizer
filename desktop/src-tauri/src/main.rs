// Strava Analyzer — Tauri desktop app
// Launches Python sidecar and shows native window pointing to localhost:8050

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use std::thread;
use tauri::Manager;

struct AppState {
    server_process: Mutex<Option<Child>>,
}

fn find_sidecar() -> Option<std::path::PathBuf> {
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();

    // Check inside the app bundle: Contents/MacOS/sidecar/StravaAnalyzer
    let sidecar = exe_dir.join("sidecar").join("StravaAnalyzer");
    if sidecar.exists() {
        return Some(sidecar);
    }

    // Development fallback
    None
}

fn start_sidecar() -> Option<Child> {
    let sidecar_path = find_sidecar()?;

    // Kill port 8050 first
    let _ = Command::new("sh")
        .args(["-c", "lsof -ti :8050 | xargs kill -9 2>/dev/null"])
        .output();

    thread::sleep(Duration::from_millis(500));

    let child = Command::new(sidecar_path)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .ok()?;

    Some(child)
}

fn wait_for_server(timeout_secs: u64) -> bool {
    let start = std::time::Instant::now();
    while start.elapsed() < Duration::from_secs(timeout_secs) {
        if let Ok(resp) = reqwest_lite("http://localhost:8050/") {
            if resp {
                return true;
            }
        }
        thread::sleep(Duration::from_millis(500));
    }
    false
}

fn reqwest_lite(url: &str) -> Result<bool, ()> {
    // Minimal HTTP check using std::net
    use std::io::{Read, Write};
    use std::net::TcpStream;

    let stream = TcpStream::connect("127.0.0.1:8050").map_err(|_| ())?;
    let mut stream = stream;
    stream.set_read_timeout(Some(Duration::from_secs(2))).ok();
    write!(stream, "GET / HTTP/1.0\r\nHost: localhost\r\n\r\n").map_err(|_| ())?;
    let mut buf = [0u8; 32];
    let n = stream.read(&mut buf).map_err(|_| ())?;
    let response = String::from_utf8_lossy(&buf[..n]);
    Ok(response.contains("200") || response.contains("HTTP"))
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            server_process: Mutex::new(None),
        })
        .setup(|app| {
            let state = app.state::<AppState>();

            // Start Python sidecar
            if let Some(child) = start_sidecar() {
                *state.server_process.lock().unwrap() = Some(child);
            }

            // Wait for server in background, then navigate the window
            let window = app.get_webview_window("main").unwrap();
            thread::spawn(move || {
                if wait_for_server(20) {
                    let _ = window.eval("window.location.href = 'http://localhost:8050/'");
                } else {
                    let _ = window.eval(
                        "document.body.innerHTML = '<div style=\"text-align:center;padding:50px;font-family:sans-serif\"><h2>Error: Server could not start</h2><p>Try restarting the app</p></div>'"
                    );
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill sidecar when window closes
                let state = window.state::<AppState>();
                if let Some(mut child) = state.server_process.lock().unwrap().take() {
                    let _ = child.kill();
                }
                // Also kill by port as fallback
                let _ = Command::new("sh")
                    .args(["-c", "lsof -ti :8050 | xargs kill -9 2>/dev/null"])
                    .output();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
