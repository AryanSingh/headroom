import { useCallback, useEffect, useMemo, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { openUrl } from '@tauri-apps/plugin-opener'
import './App.css'
import {
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
  needs_restart?: boolean
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

const emptyLicense: CredentialStatus = {
  id: 'cutctx_license_key',
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

type CredPanelProps = {
  title: string
  placeholder: string
  status: CredentialStatus
  draft: string
  setDraft: (value: string) => void
  busy: boolean
  onSave: () => void
  onRotate: () => void
  onCancel: () => void
}

function CredentialPanel({
  title,
  placeholder,
  status,
  draft,
  setDraft,
  busy,
  onSave,
  onRotate,
  onCancel,
}: CredPanelProps) {
  const showInput = shouldShowCredentialInput(status)
  return (
    <div className="cred-block">
      {status.configured && !showInput ? (
        <div className="client-row">
          <div>
            <div className="name">{title}</div>
            <div className="sub locked-hint">
              Saved · <span className="mono">{status.masked}</span>
            </div>
          </div>
          <button className="btn" disabled={busy} onClick={onRotate}>
            Rotate
          </button>
        </div>
      ) : null}

      {showInput ? (
        <div className="cred-form">
          <div className="name" style={{ marginBottom: 8 }}>
            {status.configured ? `Rotate ${title}` : title}
          </div>
          <input
            className="cred-input"
            type="password"
            autoComplete="off"
            spellCheck={false}
            placeholder={placeholder}
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="profile-row" style={{ marginTop: 8, marginBottom: 0 }}>
            <button
              className="btn primary"
              disabled={busy || !draft.trim()}
              onClick={onSave}
            >
              Save
            </button>
            {status.configured ? (
              <button className="btn" disabled={busy} onClick={onCancel}>
                Cancel
              </button>
            ) : null}
          </div>
          <div className="sub" style={{ marginTop: 8 }}>
            After save, the value is locked. Use Rotate to replace it.
          </div>
        </div>
      ) : null}

      {!status.configured && !showInput ? (
        <div className="sub">No {title.toLowerCase()} configured.</div>
      ) : null}
    </div>
  )
}

export default function App() {
  const [status, setStatus] = useState<ProxyStatus>(browserMockStatus)
  const [catalog, setCatalog] = useState<CatalogEntry[]>([])
  const [profiles, setProfiles] = useState<string[]>([])
  const [profileName, setProfileName] = useState('default')
  const [selectedProfile, setSelectedProfile] = useState('default')
  const [credential, setCredential] = useState<CredentialStatus>(emptyCredential)
  const [license, setLicense] = useState<CredentialStatus>(emptyLicense)
  const [apiTokenDraft, setApiTokenDraft] = useState('')
  const [licenseDraft, setLicenseDraft] = useState('')
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)

  const color = trayColorForPhase(status.phase)
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
      const [nextStatus, nextCatalog, nextProfiles, nextCred, nextLicense] =
        await Promise.all([
          call<ProxyStatus>('refresh_health'),
          call<CatalogEntry[]>('get_catalog'),
          call<string[]>('list_named_profiles'),
          call<CredentialStatus>('get_api_credential_status'),
          call<CredentialStatus>('get_license_credential_status'),
        ])
      setStatus(nextStatus)
      setCatalog(nextCatalog)
      setProfiles(nextProfiles)
      setSelectedProfile((current) =>
        nextProfiles.includes(current)
          ? current
          : nextProfiles.includes('default')
            ? 'default'
            : nextProfiles[0] ?? 'default',
      )
      setCredential(nextCred)
      setLicense(nextLicense)
      if (!nextCred.unlocked_for_entry) {
        setApiTokenDraft('')
      }
      if (!nextLicense.unlocked_for_entry) {
        setLicenseDraft('')
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
        <h2>Credentials</h2>
        <CredentialPanel
          title="CutCtx license key"
          placeholder="cutctx_…"
          status={license}
          draft={licenseDraft}
          setDraft={setLicenseDraft}
          busy={busy}
          onSave={() =>
            void run(async () => {
              const next = await call<CredentialStatus>('save_license_credential', {
                token: licenseDraft.trim(),
              })
              setLicense(next)
              setLicenseDraft('')
              return 'License key saved and locked'
            })
          }
          onRotate={() =>
            void run(async () => {
              const next = await call<CredentialStatus>('begin_license_credential_rotation')
              setLicense(next)
              setLicenseDraft('')
              return 'Enter the new license key, then Save'
            })
          }
          onCancel={() =>
            void run(async () => {
              const next = await call<CredentialStatus>(
                'cancel_license_credential_rotation',
              )
              setLicense(next)
              setLicenseDraft('')
              return 'License rotation cancelled'
            })
          }
        />
        <CredentialPanel
          title="OpenAI API key"
          placeholder="sk-…"
          status={credential}
          draft={apiTokenDraft}
          setDraft={setApiTokenDraft}
          busy={busy}
          onSave={() =>
            void run(async () => {
              const next = await call<CredentialStatus>('save_api_credential', {
                token: apiTokenDraft.trim(),
              })
              setCredential(next)
              setApiTokenDraft('')
              return 'API credential saved and locked'
            })
          }
          onRotate={() =>
            void run(async () => {
              const next = await call<CredentialStatus>('begin_api_credential_rotation')
              setCredential(next)
              setApiTokenDraft('')
              return 'Enter the new token, then Save'
            })
          }
          onCancel={() =>
            void run(async () => {
              const next = await call<CredentialStatus>(
                'cancel_api_credential_rotation',
              )
              setCredential(next)
              setApiTokenDraft('')
              return 'Rotation cancelled'
            })
          }
        />
      </section>

      <section className="panel">
        <h2>Power</h2>
        <div className="actions">
          <button
            className={startEnabled ? 'btn primary' : 'btn'}
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
            disabled={busy || !stopEnabled}
            title={
              stopEnabled
                ? 'Open http://127.0.0.1:<port>/dashboard'
                : 'Start the proxy first'
            }
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
            <div className="sub">Route via openai_base_url</div>
          </div>
          <button
            className={busy ? 'btn' : 'btn primary'}
            disabled={busy}
            onClick={() => void run(() => call('fix_codex_seat'))}
          >
            Fix Codex routing
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
                await call<string>('copy_claude_snippet')
                return 'Copied Claude env snippet'
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
                await call<string>('mint_seat_token')
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
              void run(async () => {
                const names = await call<string[]>('save_named_profile', {
                  name: profileName.trim(),
                })
                setProfiles(names)
                setSelectedProfile(profileName.trim())
                return `Saved profile “${profileName.trim()}”`
              })
            }
          >
            Save
          </button>
        </div>
        <div className="profile-row">
          <select
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
          >
            {!profiles.includes('default') ? (
              <option value="default">default</option>
            ) : null}
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
              void run(async () => {
                const loaded = await call<{ name: string }>('load_named_profile', {
                  name: selectedProfile,
                })
                const loadedName = loaded.name || selectedProfile
                setSelectedProfile(loadedName)
                setProfileName(loadedName)
                return `Loaded profile “${loadedName}”`
              })
            }
          >
            Load
          </button>
        </div>
        <button
          className="btn"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              const loaded = await call<{ name: string }>('use_all_optional_profile')
              const loadedName = loaded.name || 'release-verify-all-on'
              setSelectedProfile(loadedName)
              setProfileName(loadedName)
              return 'Loaded release-verify-all-on'
            })
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
                    {item.needs_restart ? (
                      <div className="badge">Restart required</div>
                    ) : null}
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
