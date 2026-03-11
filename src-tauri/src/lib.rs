use std::{
    collections::HashMap,
    net::TcpStream,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{AppHandle, Emitter, Manager, RunEvent};

struct BackendState {
    child: Mutex<Option<Child>>,
}

impl BackendState {
    fn new() -> Self {
        Self {
            child: Mutex::new(None),
        }
    }

    fn set_child(&self, child: Child) {
        if let Ok(mut child_guard) = self.child.lock() {
            *child_guard = Some(child);
        }
    }

    fn terminate(&self) {
        if let Ok(mut child_guard) = self.child.lock() {
            if let Some(child) = child_guard.as_mut() {
                let _ = child.kill();
                let _ = child.wait();
            }
            *child_guard = None;
        }
    }
}

#[derive(Clone)]
struct BackendLaunchConfig {
    program: String,
    args: Vec<String>,
    cwd: PathBuf,
    env: HashMap<String, String>,
}

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".."))
}

fn backend_dir() -> PathBuf {
    project_root().join("backend")
}

fn backend_env() -> HashMap<String, String> {
    let project_root = project_root();
    let backend_dir = backend_dir();
    let database_path = backend_dir.join("agentic.db");

    HashMap::from([
        (
            "DATABASE_URL".into(),
            format!("sqlite:///{}", database_path.display()),
        ),
        (
            "FS_ALLOWED_ROOTS".into(),
            format!("[\"{}\"]", project_root.display()),
        ),
        (
            "SCYTHE_PROJECT_ROOT".into(),
            project_root.display().to_string(),
        ),
    ])
}

fn wait_for_backend() -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(20);
    while Instant::now() < deadline {
        if TcpStream::connect("127.0.0.1:3001").is_ok() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(250));
    }

    Err("Timed out waiting for backend on 127.0.0.1:3001".into())
}

fn emit_backend_status(app: &AppHandle, status: &str, detail: &str) {
    let _ = app.emit(
        "backend-status",
        serde_json::json!({
            "status": status,
            "detail": detail,
        }),
    );
}

fn spawn_backend(config: &BackendLaunchConfig) -> Result<Child, String> {
    let mut command = Command::new(&config.program);
    command
        .args(&config.args)
        .current_dir(&config.cwd)
        .env("SCYTHE_TAURI_MANAGED", "1")
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    for (key, value) in &config.env {
        command.env(key, value);
    }

    command.spawn().map_err(|error| {
        format!(
            "Failed to spawn backend command {:?} {:?} in {}: {error}",
            config.program,
            config.args,
            config.cwd.display()
        )
    })
}

fn backend_launch_candidates(app: &AppHandle) -> Vec<BackendLaunchConfig> {
    let backend_dir = backend_dir();
    let resource_backend_dir = app
        .path()
        .resource_dir()
        .ok()
        .map(|dir| dir.join("backend"));
    let backend_env = backend_env();

    let mut candidates = Vec::new();

    if backend_dir.exists() {
        candidates.push(BackendLaunchConfig {
            program: "uv".into(),
            args: vec![
                "run".into(),
                "--project".into(),
                "backend".into(),
                "python".into(),
                "-m".into(),
                "app.desktop_entry".into(),
            ],
            cwd: backend_dir.clone(),
            env: backend_env.clone(),
        });

        candidates.push(BackendLaunchConfig {
            program: "python3".into(),
            args: vec!["-m".into(), "app.desktop_entry".into()],
            cwd: backend_dir.clone(),
            env: backend_env.clone(),
        });
    }

    if let Some(resource_backend_dir) = resource_backend_dir.filter(|dir| dir.exists()) {
        candidates.push(BackendLaunchConfig {
            program: "python3".into(),
            args: vec!["-m".into(), "app.desktop_entry".into()],
            cwd: resource_backend_dir,
            env: backend_env,
        });
    }

    candidates
}

fn start_backend_in_background(app: AppHandle) {
    thread::spawn(move || {
        emit_backend_status(&app, "starting", "Launching local Python backend");

        let mut errors = Vec::new();
        for candidate in backend_launch_candidates(&app) {
            match spawn_backend(&candidate) {
                Ok(mut child) => match wait_for_backend() {
                    Ok(()) => {
                        app.state::<BackendState>().set_child(child);
                        emit_backend_status(&app, "ready", "Backend is accepting connections");
                        return;
                    }
                    Err(error) => {
                        let _ = child.kill();
                        let _ = child.wait_with_output();
                        errors.push(format!(
                            "Backend command {:?} {:?} started but never became ready: {error}",
                            candidate.program, candidate.args
                        ));
                    }
                },
                Err(error) => errors.push(error),
            }
        }

        let detail = if errors.is_empty() {
            "No backend launch candidates were available".to_string()
        } else {
            errors.join(" | ")
        };

        eprintln!("{detail}");
        emit_backend_status(&app, "failed", &detail);
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let backend_state = BackendState::new();
            app.manage(backend_state);
            start_backend_in_background(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                app_handle.state::<BackendState>().terminate();
            }
        });
}
