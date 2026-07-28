import { describe, expect, it } from 'vitest'
import {
  canRotateCredential,
  shouldShowCredentialInput,
  type CredentialStatus,
} from './credentials'

const locked: CredentialStatus = {
  id: 'openai_api_key',
  configured: true,
  masked: 'sk-…1234',
  unlocked_for_entry: false,
}

const unlockedNew: CredentialStatus = {
  id: 'openai_api_key',
  configured: false,
  masked: null,
  unlocked_for_entry: true,
}

const rotating: CredentialStatus = {
  id: 'openai_api_key',
  configured: true,
  masked: 'sk-…1234',
  unlocked_for_entry: true,
}

describe('credential UI gates', () => {
  it('hides input when locked', () => {
    expect(shouldShowCredentialInput(locked)).toBe(false)
    expect(canRotateCredential(locked)).toBe(true)
  })

  it('shows input for first-time entry', () => {
    expect(shouldShowCredentialInput(unlockedNew)).toBe(true)
    expect(canRotateCredential(unlockedNew)).toBe(false)
  })

  it('shows input during rotation but not rotate again', () => {
    expect(shouldShowCredentialInput(rotating)).toBe(true)
    expect(canRotateCredential(rotating)).toBe(false)
  })
})
