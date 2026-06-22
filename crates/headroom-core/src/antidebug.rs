//! Anti-debug and anti-dump guards for the Cutctx EE runtime.
//!
//! Called once at startup (before any EE module executes) to detect or deny
//! debugger attachment. The intent is not unbreakable security — determined
//! reverse-engineers can bypass these — but to raise the bar past casual
//! memory-dump or dynamic-analysis attempts.
//!
//! # Platform behaviour
//!
//! | Platform | Strategy                                                         |
//! |----------|------------------------------------------------------------------|
//! | macOS    | `ptrace(PT_DENY_ATTACH, …)` — makes the process unattachable    |
//! | Linux    | Read `/proc/self/status` → `TracerPid`; non-zero = debugger     |
//! | Windows  | `IsDebuggerPresent()` Win32 API                                  |
//! | other    | No-op (returns `false`)                                          |
//!
//! `deny_debugger_attach()` is idempotent — safe to call multiple times.

/// Attempt to deny future debugger attachment and detect existing ones.
///
/// Returns `true` if a debugger was detected (Linux / Windows path).
/// Returns `false` on macOS (we deny rather than detect), or if detection
/// is not supported on the current platform.
///
/// # Panics
/// Never panics — all unsafe operations are guarded.
pub fn deny_debugger_attach() -> bool {
    #[cfg(target_os = "macos")]
    {
        _macos_deny_attach();
        return false; // deny, not detect
    }

    #[cfg(target_os = "linux")]
    {
        return _linux_is_traced();
    }

    #[cfg(target_os = "windows")]
    {
        return _windows_is_debugged();
    }

    #[allow(unreachable_code)]
    false
}

// ── macOS ─────────────────────────────────────────────────────────────────

#[cfg(target_os = "macos")]
fn _macos_deny_attach() {
    // PT_DENY_ATTACH prevents any future debugger from attaching to this
    // process. If a debugger is already attached, the process receives
    // SIGKILL. The syscall is safe to call multiple times.
    const PT_DENY_ATTACH: i32 = 31;

    extern "C" {
        fn ptrace(request: i32, pid: libc::pid_t, addr: *mut libc::c_char, data: i32) -> i32;
    }

    // SAFETY: ptrace with PT_DENY_ATTACH / pid=0 / addr=NULL / data=0
    // is a well-documented, idempotent macOS syscall. The null pointer for
    // addr is the correct argument for this request variant.
    unsafe {
        ptrace(PT_DENY_ATTACH, 0, std::ptr::null_mut(), 0);
    }
}

// ── Linux ─────────────────────────────────────────────────────────────────

#[cfg(target_os = "linux")]
fn _linux_is_traced() -> bool {
    use std::fs;

    let Ok(content) = fs::read_to_string("/proc/self/status") else {
        return false; // /proc not available (container without procfs?)
    };

    for line in content.lines() {
        if let Some(rest) = line.strip_prefix("TracerPid:") {
            if let Ok(pid) = rest.trim().parse::<u64>() {
                return pid != 0;
            }
        }
    }

    false
}

// ── Windows ───────────────────────────────────────────────────────────────

#[cfg(target_os = "windows")]
fn _windows_is_debugged() -> bool {
    extern "system" {
        fn IsDebuggerPresent() -> i32;
    }
    // SAFETY: `IsDebuggerPresent` is a trivial Win32 API with no side effects.
    unsafe { IsDebuggerPresent() != 0 }
}
