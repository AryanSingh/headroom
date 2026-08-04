import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const tauri = vi.hoisted(() => ({
  invoke: vi.fn(),
  openUrl: vi.fn(),
}))

vi.mock('@tauri-apps/api/core', () => ({ invoke: tauri.invoke }))
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: tauri.openUrl }))

const emptyCredential = {
  id: 'openai_api_key',
  configured: false,
  masked: null,
  unlocked_for_entry: true,
}

describe('desktop lifecycle recovery', () => {
  beforeEach(() => {
    let phase = 'stopped'
    let startAttempts = 0
    tauri.invoke.mockReset()
    tauri.invoke.mockImplementation(async (command: string) => {
      if (command === 'refresh_health') {
        return {
          phase,
          port: 8787,
          message: phase === 'healthy' ? 'Healthy' : 'Proxy stopped',
          tokens_saved: 0,
          external: false,
        }
      }
      if (command === 'get_catalog') return []
      if (command === 'list_named_profiles') return ['default']
      if (command === 'get_api_credential_status') return emptyCredential
      if (command === 'get_license_credential_status') {
        return { ...emptyCredential, id: 'cutctx_license_key' }
      }
      if (command === 'start_proxy') {
        startAttempts += 1
        if (startAttempts === 1) throw new Error('Unable to start proxy')
        phase = 'healthy'
        return null
      }
      throw new Error(`Unexpected command: ${command}`)
    })
  })

  it('surfaces a start failure accessibly and recovers on retry', async () => {
    render(<App />)

    const start = await screen.findByRole('button', { name: 'Start' })
    const stop = screen.getByRole('button', { name: 'Stop' })
    await waitFor(() => expect(start).toBeEnabled())
    expect(stop).toBeDisabled()

    fireEvent.click(start)
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to start proxy')
    await waitFor(() => expect(start).toBeEnabled())

    fireEvent.click(start)
    await waitFor(() => expect(screen.getAllByText('Healthy')).not.toHaveLength(0))
    expect(start).toBeDisabled()
    expect(stop).toBeEnabled()
  })
})
