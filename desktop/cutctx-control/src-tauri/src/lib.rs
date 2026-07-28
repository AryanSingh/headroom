mod argv;
mod catalog;
mod codex_config;
mod credentials;
mod health;
mod profiles;
mod restart_apply;
mod seat;
mod supervisor;

use argv::{FeatureValue, ProxyProfile};
use health::{HealthMachine, ProxyStatus};
use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use supervisor::ProxySupervisor;
use tauri::State;

struct AppState {
    supervisor: ProxySupervisor,
    health: Mutex<HealthMachine>,
    profile: Mutex<ProxyProfile>,
    credentials: Mutex<credentials::CredentialVault>,
    home: PathBuf,
}

fn default_home() -> PathBuf {
    dirs::home_dir().unwrap_or_else(|| PathBuf::from("."))
}

fn resolve_cutctx_bin() -> PathBuf {
    if let Ok(p) = std::env::var("CUTCTX_BIN") {
        return PathBuf::from(p);
    }
    which_cutctx().unwrap_or_else(|| PathBuf::from("cutctx"))
}

fn which_cutctx() -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join("cutctx");
        if candidate.is_file() {
            return Some(candidate);
        }
        #[cfg(windows)]
        {
            let candidate = dir.join("cutctx.exe");
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

#[derive(Serialize)]
struct CatalogEntry {
    key: String,
    group: String,
    label: String,
    kind: String,
    apply: String,
    enabled: bool,
    text: String,
    choices: Vec<String>,
}

#[tauri::command]
fn get_catalog(state: State<'_, AppState>) -> Result<Vec<CatalogEntry>, String> {
    let profile = state.profile.lock().map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    for def in catalog::catalog() {
        let value = profile
            .features
            .get(def.key)
            .cloned()
            .unwrap_or(FeatureValue {
                enabled: def.default_bool,
                text: def.default_text.to_string(),
            });
        out.push(CatalogEntry {
            key: def.key.into(),
            group: def.group.into(),
            label: def.label.into(),
            kind: format!("{:?}", def.kind).to_ascii_lowercase(),
            apply: format!("{:?}", def.apply).to_ascii_lowercase(),
            enabled: value.enabled,
            text: value.text,
            choices: def.choices.iter().map(|s| (*s).to_string()).collect(),
        });
    }
    Ok(out)
}

#[tauri::command]
fn get_status(state: State<'_, AppState>) -> Result<ProxyStatus, String> {
    let health = state.health.lock().map_err(|e| e.to_string())?;
    Ok(health.status.clone())
}

#[tauri::command]
fn get_profile(state: State<'_, AppState>) -> Result<ProxyProfile, String> {
    let profile = state.profile.lock().map_err(|e| e.to_string())?;
    Ok(profile.clone())
}

#[tauri::command]
fn preview_argv(state: State<'_, AppState>) -> Result<Vec<String>, String> {
    let profile = state.profile.lock().map_err(|e| e.to_string())?;
    Ok(argv::build_proxy_argv(&profile))
}

#[tauri::command]
fn set_feature(
    state: State<'_, AppState>,
    key: String,
    enabled: bool,
    text: Option<String>,
) -> Result<ProxyStatus, String> {
    {
        let mut profile = state.profile.lock().map_err(|e| e.to_string())?;
        let entry = profile
            .features
            .entry(key.clone())
            .or_insert_with(|| FeatureValue::bool(false));
        entry.enabled = enabled;
        if let Some(t) = text {
            entry.text = t;
        }
    }
    let mut health = state.health.lock().map_err(|e| e.to_string())?;
    if let Some(def) = catalog::get(&key) {
        if def.apply == catalog::ApplyMode::Restart
            && matches!(
                health.status.phase,
                health::ProxyPhase::Healthy
                    | health::ProxyPhase::Degraded
                    | health::ProxyPhase::RestartPending
            )
        {
            health.on_toggle_needs_restart();
        }
    }
    Ok(health.status.clone())
}

#[tauri::command]
fn load_named_profile(state: State<'_, AppState>, name: String) -> Result<ProxyProfile, String> {
    let loaded = profiles::load_profile(&state.home, &name).map_err(|e| e.to_string())?;
    let mut profile = state.profile.lock().map_err(|e| e.to_string())?;
    *profile = loaded.clone();
    Ok(loaded)
}

#[tauri::command]
fn save_named_profile(state: State<'_, AppState>, name: String) -> Result<(), String> {
    let mut profile = state.profile.lock().map_err(|e| e.to_string())?;
    profile.name = name;
    profiles::save_profile(&state.home, &profile).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn list_named_profiles(state: State<'_, AppState>) -> Result<Vec<String>, String> {
    profiles::list_profiles(&state.home).map_err(|e| e.to_string())
}

#[tauri::command]
fn use_all_optional_profile(state: State<'_, AppState>) -> Result<ProxyProfile, String> {
    let p = ProxyProfile::all_optional_on();
    let mut profile = state.profile.lock().map_err(|e| e.to_string())?;
    *profile = p.clone();
    let mut health = state.health.lock().map_err(|e| e.to_string())?;
    if matches!(
        health.status.phase,
        health::ProxyPhase::Healthy | health::ProxyPhase::Degraded
    ) {
        health.on_toggle_needs_restart();
    }
    Ok(p)
}

fn probe_health(port: u16) -> Result<(bool, u64), String> {
    let url = format!("http://127.0.0.1:{port}/health");
    match ureq::get(&url).timeout(std::time::Duration::from_secs(2)).call() {
        Ok(resp) if resp.status() >= 200 && resp.status() < 300 => {
            let tokens = probe_tokens_saved(port).unwrap_or(0);
            Ok((true, tokens))
        }
        Ok(_) => Ok((false, 0)),
        Err(e) => Err(e.to_string()),
    }
}

fn probe_tokens_saved(port: u16) -> Option<u64> {
    let url = format!("http://127.0.0.1:{port}/stats");
    let resp = ureq::get(&url)
        .timeout(std::time::Duration::from_secs(2))
        .call()
        .ok()?;
    let json: serde_json::Value = resp.into_json().ok()?;
    json.get("tokens_saved")
        .and_then(|v| v.as_u64())
        .or_else(|| {
            json.pointer("/savings/tokens_saved")
                .and_then(|v| v.as_u64())
        })
}

#[tauri::command]
fn refresh_health(state: State<'_, AppState>) -> Result<ProxyStatus, String> {
    let port = {
        let profile = state.profile.lock().map_err(|e| e.to_string())?;
        profile.port
    };
    let mut health = state.health.lock().map_err(|e| e.to_string())?;
    match probe_health(port) {
        Ok((true, tokens)) => {
            if matches!(
                health.status.phase,
                health::ProxyPhase::Stopped | health::ProxyPhase::Error
            ) && !state.supervisor.is_running()
            {
                health.on_external_detected();
            }
            health.on_health_ok(tokens);
        }
        Ok((false, _)) => {
            if !state.supervisor.is_running() {
                health.on_stopped();
            } else {
                health.on_health_fail("Health check returned non-OK");
            }
        }
        Err(err) => {
            if !state.supervisor.is_running() {
                health.on_stopped();
            } else if health.status.phase != health::ProxyPhase::Starting {
                health.on_health_fail(err);
            }
        }
    }
    health.status.port = port;
    Ok(health.status.clone())
}

#[tauri::command]
fn start_proxy(state: State<'_, AppState>) -> Result<ProxyStatus, String> {
    let profile = state.profile.lock().map_err(|e| e.to_string())?.clone();
    {
        let mut health = state.health.lock().map_err(|e| e.to_string())?;
        health.on_start_requested();
    }
    // If something already healthy on port, attach instead of double-bind.
    if let Ok((true, tokens)) = probe_health(profile.port) {
        let mut health = state.health.lock().map_err(|e| e.to_string())?;
        health.on_external_detected();
        health.on_health_ok(tokens);
        return Ok(health.status.clone());
    }
    let env_vars = {
        let vault = state.credentials.lock().map_err(|e| e.to_string())?;
        proxy_launch_env(&state.home, &vault)?
    };
    state.supervisor.start(&profile, &env_vars)?;
    // Brief wait then probe
    std::thread::sleep(std::time::Duration::from_millis(800));
    drop(profile);
    refresh_health(state)
}

#[tauri::command]
fn stop_proxy(state: State<'_, AppState>) -> Result<ProxyStatus, String> {
    let port = state.profile.lock().map_err(|e| e.to_string())?.port;
    {
        let mut health = state.health.lock().map_err(|e| e.to_string())?;
        health.on_stop_requested();
    }
    // Reclaim port so Stop works for attached/external proxies too.
    state.supervisor.stop_and_reclaim_port(port)?;
    let mut health = state.health.lock().map_err(|e| e.to_string())?;
    health.on_stopped();
    Ok(health.status.clone())
}

#[tauri::command]
fn restart_proxy(state: State<'_, AppState>) -> Result<ProxyStatus, String> {
    let profile = state.profile.lock().map_err(|e| e.to_string())?.clone();
    let port = profile.port;
    {
        let mut health = state.health.lock().map_err(|e| e.to_string())?;
        health.on_stop_requested();
    }
    state.supervisor.stop_and_reclaim_port(port)?;
    {
        let mut health = state.health.lock().map_err(|e| e.to_string())?;
        health.on_stopped();
        health.on_start_requested();
    }
    let env_vars = {
        let vault = state.credentials.lock().map_err(|e| e.to_string())?;
        proxy_launch_env(&state.home, &vault)?
    };
    // Always spawn with the current profile argv so restart-required toggles apply.
    state.supervisor.start(&profile, &env_vars)?;
    std::thread::sleep(std::time::Duration::from_millis(900));
    let tokens = probe_health(port)
        .ok()
        .and_then(|(ok, n)| if ok { Some(n) } else { None })
        .unwrap_or(0);
    let mut health = state.health.lock().map_err(|e| e.to_string())?;
    health.on_restart_applied(tokens);
    health.status.port = port;
    Ok(health.status.clone())
}

#[tauri::command]
fn dashboard_url(state: State<'_, AppState>) -> Result<String, String> {
    let profile = state.profile.lock().map_err(|e| e.to_string())?;
    Ok(format!("http://127.0.0.1:{}/", profile.port))
}

#[tauri::command]
fn mint_seat_token(state: State<'_, AppState>) -> Result<String, String> {
    let bin = state.supervisor.cutctx_bin.to_string_lossy().to_string();
    let subject = whoami_subject();
    let token = seat::mint_via_cli(&bin, Some(&subject))?;
    let record = seat::SeatTokenRecord {
        subject,
        token: token.clone(),
        issued_at_unix: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
    };
    seat::save_seat(&state.home, &record).map_err(|e| e.to_string())?;
    // Return header line for copy; UI should not log it.
    Ok(seat::header_line(&token))
}

fn whoami_subject() -> String {
    std::env::var("USER")
        .or_else(|_| std::env::var("USERNAME"))
        .unwrap_or_else(|_| "cutctx-user".into())
}

#[tauri::command]
fn fix_codex_seat(state: State<'_, AppState>) -> Result<String, String> {
    let header = mint_seat_token(state.clone())?;
    let token = header
        .strip_prefix("X-Cutctx-User-Token: ")
        .unwrap_or(header.as_str())
        .to_string();
    let port = state.profile.lock().map_err(|e| e.to_string())?.port;
    let codex_home = state.home.join(".codex");
    let config_path = codex_home.join("config.toml");
    let original = if config_path.exists() {
        fs::read_to_string(&config_path).map_err(|e| e.to_string())?
    } else {
        String::new()
    };
    let mut next = codex_config::inject_base_url(&original, port);
    next = codex_config::inject_seat_token_header(&next, &token);
    fs::create_dir_all(&codex_home).map_err(|e| e.to_string())?;
    fs::write(&config_path, next).map_err(|e| e.to_string())?;
    Ok(format!(
        "Updated {} with proxy URL and seat token header",
        config_path.display()
    ))
}

#[tauri::command]
fn get_api_credential_status(
    state: State<'_, AppState>,
) -> Result<credentials::CredentialStatus, String> {
    let vault = state.credentials.lock().map_err(|e| e.to_string())?;
    vault
        .status(&state.home, credentials::OPENAI_API_KEY)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn save_api_credential(
    state: State<'_, AppState>,
    token: String,
) -> Result<credentials::CredentialStatus, String> {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let mut vault = state.credentials.lock().map_err(|e| e.to_string())?;
    vault.save(&state.home, credentials::OPENAI_API_KEY, &token, now)
}

#[tauri::command]
fn begin_api_credential_rotation(
    state: State<'_, AppState>,
) -> Result<credentials::CredentialStatus, String> {
    let mut vault = state.credentials.lock().map_err(|e| e.to_string())?;
    vault.begin_rotate(&state.home, credentials::OPENAI_API_KEY)
}

#[tauri::command]
fn cancel_api_credential_rotation(
    state: State<'_, AppState>,
) -> Result<credentials::CredentialStatus, String> {
    let mut vault = state.credentials.lock().map_err(|e| e.to_string())?;
    vault.cancel_rotate(&state.home, credentials::OPENAI_API_KEY)
}

fn proxy_launch_env(
    home: &std::path::Path,
    vault: &credentials::CredentialVault,
) -> Result<Vec<(String, String)>, String> {
    let mut env = Vec::new();
    if let Some(token) = vault
        .get_secret(home, credentials::OPENAI_API_KEY)
        .map_err(|e| e.to_string())?
    {
        env.push(("OPENAI_API_KEY".into(), token));
    }
    Ok(env)
}

#[tauri::command]
fn copy_claude_snippet(state: State<'_, AppState>) -> Result<String, String> {
    let port = state.profile.lock().map_err(|e| e.to_string())?.port;
    let seat = seat::load_seat(&state.home).map_err(|e| e.to_string())?;
    let token = seat.map(|s| s.token).unwrap_or_default();
    let mut out = format!("export ANTHROPIC_BASE_URL=http://127.0.0.1:{port}\n");
    if !token.is_empty() {
        out.push_str(&format!(
            "export ANTHROPIC_CUSTOM_HEADERS=$'X-Cutctx-User-Token: {token}'\n"
        ));
    } else {
        out.push_str("# Run Fix seat token first to include X-Cutctx-User-Token\n");
    }
    Ok(out)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let home = default_home();
    let profile = ProxyProfile::default_profile();
    let port = profile.port;
    let state = AppState {
        supervisor: ProxySupervisor::new(resolve_cutctx_bin()),
        health: Mutex::new(HealthMachine::new(port)),
        profile: Mutex::new(profile),
        credentials: Mutex::new(credentials::CredentialVault::default()),
        home,
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(state)
        .setup(|app| {
            use tauri::menu::{Menu, MenuItem};
            use tauri::tray::TrayIconBuilder;
            use tauri::Manager;

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            let show = MenuItem::with_id(app, "show", "Open Control", true, None::<&str>)?;
            let start = MenuItem::with_id(app, "start", "Start Proxy", true, None::<&str>)?;
            let stop = MenuItem::with_id(app, "stop", "Stop Proxy", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &start, &stop, &quit])?;

            let mut tray = TrayIconBuilder::with_id("cutctx-control")
                .menu(&menu)
                .tooltip("CutCtx Control")
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "start" => {
                        let state = app.state::<AppState>();
                        let _ = start_proxy(state);
                    }
                    "stop" => {
                        let state = app.state::<AppState>();
                        let _ = stop_proxy(state);
                    }
                    "quit" => app.exit(0),
                    _ => {}
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            let _ = tray.build(app)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_catalog,
            get_status,
            get_profile,
            preview_argv,
            set_feature,
            load_named_profile,
            save_named_profile,
            list_named_profiles,
            use_all_optional_profile,
            refresh_health,
            start_proxy,
            stop_proxy,
            restart_proxy,
            dashboard_url,
            mint_seat_token,
            fix_codex_seat,
            copy_claude_snippet,
            get_api_credential_status,
            save_api_credential,
            begin_api_credential_rotation,
            cancel_api_credential_rotation,
        ])
        .run(tauri::generate_context!())
        .expect("error while running CutCtx Control");
}
