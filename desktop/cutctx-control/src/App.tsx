import { useCallback, useEffect, useMemo, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import './App.css'
import {
  canRotateCredential,
  shouldShowCredentialInput,
  type CredentialStatus,
} from './lib/credentials'
import {
  canRestartProxy,
  canStartProxy,
  canStopProxy,
  statusLabel,
  trayColorForPhase,
  type ProxyPhase,
} from './lib/status'

type ProxyStatus = {
  phase: ProxyPhase
  port: number
  message: string
  tokens_saved: number
  external: boolean
}

type CatalogEntry = {
  key: string
  group: string
  label: string
  kind: string
  apply: string
  enabled: boolean
  text: string
  choices: string[]
}

const browserMockStatus: ProxyStatus = {
  phase: 'stopped',
  port: 8787,
  message: 'Proxy stopped',
  tokens_saved: 0,
  external: false,
}

const emptyCredential: CredentialStatus = {
  id: 'openai_api_key',
  configured: false,
  masked: null,
  unlocked_for_entry: true,
}

async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(cmd, args)
  } catch (err) {
    // Browser/dev without Tauri: surface a readable error.
    throw err instanceof Error ? err : new Error(String(err))
  }
}

export default function App() {
  const [status, setStatus] = useState<ProxyStatus>(browserMockStatus)
  const [catalog, setCatalog] = useState<CatalogEntry[]>([])
  const [profiles, setProfiles] = useState<string[]>([])
  const [profileName, setProfileName] = useState('default')
  const [credential, setCredential] = useState<CredentialStatus>(emptyCredential)
  const [apiTokenDraft, setApiTokenDraft] = useState('')
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)

  const color = trayColorForPhase(status.phase)
  const showCredentialInput = shouldShowCredentialInput(credential)
  const showRotate = canRotateCredential(credential)
  const startEnabled = canStartProxy(status.phase)
  const stopEnabled = canStopProxy(status.phase)
  const restartEnabled = canRestartProxy(status.phase)

  const grouped = useMemo(() => {
    const map = new Map<string, CatalogEntry[]>()
    for (const item of catalog) {
      const list = map.get(item.group) ?? []
      list.push(item)
      map.set(item.group, list)
    }
    return [...map.entries()]
  }, [catalog])

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextCatalog, nextProfiles, nextCred] = await Promise.all([
        call<ProxyStatus>('refresh_health'),
        call<CatalogEntry[]>('get_catalog'),
        call<string[]>('list_named_profiles'),
        call<CredentialStatus>('get_api_credential_status'),
      ])
      setStatus(nextStatus)
      setCatalog(nextCatalog)
      setProfiles(nextProfiles)
      setCredential(nextCred)
      if (!nextCred.unlocked_for_entry) {
        setApiTokenDraft('')
      }
    } catch {
      // Keep UI usable in pure browser preview.
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => {
      void call<ProxyStatus>('refresh_health')
        .then(setStatus)
        .catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(id)
  }, [refresh])

  async function run(action: () => Promise<unknown>, okMessage?: string) {
    setBusy(true)
    setToast('')
    try {
      const result = await action()
      if (typeof result === 'string' && result) {
        setToast(result)
      } else if (okMessage) {
        setToast(okMessage)
      }
      await refresh()
    } catch (err) {
      setToast(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header className="brand">
        <h1>CutCtx</h1>
        <div className="sub">Control</div>
      </header>

      <section className="status-strip" aria-live="polite">
        <div className="status-row">
          <div className="status-row" style={{ gap: 8 }}>
            <span className={`dot ${color}`} aria-hidden />
            <span className="phase">{statusLabel(status.phase)}</span>
          </div>
          <span className="sub">{status.external ? 'external' : 'supervised'}</span>
        </div>
        <div className="meta">
          <div>
            Port
            <strong>{status.port}</strong>
          </div>
          <div>
            Tokens saved
            <strong>{status.tokens_saved.toLocaleString()}</strong>
          </div>
        </div>
        <div className="sub">{status.message}</div>
      </section>

      <section className="panel">
        <h2>API credentials</h2>
        {credential.configured && !showCredentialInput ? (
          <div className="client-row">
            <div>
              <div className="name">OpenAI API key</div>
              <div className="sub locked-hint">
                Saved · <span className="mono">{credential.masked}</span>
              </div>
            </div>
            <button
              className="btn"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  const next = await call<CredentialStatus>('begin_api_credential_rotation')
                  setCredential(next)
                  setApiTokenDraft('')
                  return 'Enter the new token, then Save'
                })
              }
            >
              Rotate
            </button>
          </div>
        ) : null}

        {showCredentialInput ? (
          <div className="cred-form">
            <div className="name" style={{ marginBottom: 8 }}>
              {credential.configured ? 'Rotate OpenAI API key' : 'OpenAI API key'}
            </div>
            <input
              className="cred-input"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="sk-…"
              value={apiTokenDraft}
              disabled={busy}
              onChange={(e) => setApiTokenDraft(e.target.value)}
            />
            <div className="profile-row" style={{ marginTop: 8, marginBottom: 0 }}>
              <button
                className="btn primary"
                disabled={busy || !apiTokenDraft.trim()}
                onClick={() =>
                  void run(async () => {
                    const next = await call<CredentialStatus>('save_api_credential', {
                      token: apiTokenDraft.trim(),
                    })
                    setCredential(next)
                    setApiTokenDraft('')
                    return 'API credential saved and locked'
                  })
                }
              >
                Save
              </button>
              {credential.configured ? (
                <button
                  className="btn"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      const next = await call<CredentialStatus>(
                        'cancel_api_credential_rotation',
                      )
                      setCredential(next)
                      setApiTokenDraft('')
                      return 'Rotation cancelled'
                    })
                  }
                >
                  Cancel
                </button>
              ) : null}
            </div>
            <div className="sub" style={{ marginTop: 8 }}>
              After save, the token is locked. Use Rotate to replace it.
            </div>
          </div>
        ) : null}

        {!credential.configured && !showCredentialInput ? (
          <div className="sub">No API credential configured.</div>
        ) : null}
      </section>

      <section className="panel">
        <h2>Power</h2>
        <div className="actions">
          <button
            className="btn primary"
            disabled={busy || !startEnabled}
            onClick={() => void run(() => call('start_proxy'))}
          >
            Start
          </button>
          <button
            className="btn danger"
            disabled={busy || !stopEnabled}
            onClick={() => void run(() => call('stop_proxy'))}
          >
            Stop
          </button>
          <button
            className="btn"
            disabled={busy || !restartEnabled}
            onClick={() => void run(() => call('restart_proxy'))}
          >
            Restart
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const url = await call<string>('dashboard_url')
                await openUrl(url)
                return `Opened ${url}`
              })
            }
          >
            Dashboard
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Clients</h2>
        <div className="client-row">
          <div>
            <div className="name">Codex</div>
            <div className="sub">Route + seat token header</div>
          </div>
          <button
            className="btn primary"
            disabled={busy}
            onClick={() => void run(() => call('fix_codex_seat'))}
          >
            Fix seat token
          </button>
        </div>
        <div className="client-row">
          <div>
            <div className="name">Claude</div>
            <div className="sub">Copy env snippet</div>
          </div>
          <button
            className="btn"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const snippet = await call<string>('copy_claude_snippet')
                await navigator.clipboard.writeText(snippet)
                return snippet
              })
            }
          >
            Copy setup
          </button>
        </div>
        <div className="client-row">
          <div>
            <div className="name">Seat token</div>
            <div className="sub">Mint header only</div>
          </div>
          <button
            className="btn"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                const header = await call<string>('mint_seat_token')
                await navigator.clipboard.writeText(header)
                return 'Copied X-Cutctx-User-Token header'
              })
            }
          >
            Mint & copy
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Profiles</h2>
        <div className="profile-row">
          <input
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            placeholder="profile name"
          />
          <button
            className="btn"
            disabled={busy || !profileName.trim()}
            onClick={() =>
              void run(() => call('save_named_profile', { name: profileName.trim() }), 'Profile saved')
            }
          >
            Save
          </button>
        </div>
        <div className="profile-row">
          <select
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
          >
            <option value="default">default</option>
            {profiles.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            className="btn"
            disabled={busy}
            onClick={() =>
              void run(() => call('load_named_profile', { name: profileName }), 'Profile loaded')
            }
          >
            Load
          </button>
        </div>
        <button
          className="btn"
          disabled={busy}
          onClick={() =>
            void run(() => call('use_all_optional_profile'), 'Loaded release-verify-all-on')
          }
        >
          Load “all optional on”
        </button>
      </section>

      <section className="panel">
        <h2>Features</h2>
        <div className="feature-scroll">
          {grouped.map(([group, items]) => (
            <div key={group}>
              <div className="group-title">{group}</div>
              {items.map((item) => (
                <div className="feature-row" key={item.key}>
                  <div>
                    <div className="name">{item.label}</div>
                    {item.apply === 'restart' ? <div className="badge">Restart required</div> : null}
                  </div>
                  {item.kind === 'text' || item.kind === 'choice' ? (
                    <input
                      style={{ width: 140 }}
                      value={item.text}
                      disabled={busy}
                      onChange={(e) => {
                        const text = e.target.value
                        setCatalog((prev) =>
                          prev.map((row) => (row.key === item.key ? { ...row, text } : row)),
                        )
                      }}
                      onBlur={() =>
                        void run(() =>
                          call('set_feature', {
                            key: item.key,
                            enabled: true,
                            text: item.text,
                          }),
                        )
                      }
                    />
                  ) : (
                    <button
                      type="button"
                      className={`toggle ${item.enabled ? 'on' : ''}`}
                      aria-pressed={item.enabled}
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          await call('set_feature', {
                            key: item.key,
                            enabled: !item.enabled,
                          })
                        })
                      }
                    />
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      {toast ? <div className="toast">{toast}</div> : null}

      <footer className="footer">
        <span>CutCtx Control 0.1.0</span>
        <button className="btn" style={{ padding: '4px 8px' }} onClick={() => void refresh()}>
          Refresh
        </button>
      </footer>
    </div>
  )
}
