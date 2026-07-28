import { describe, expect, it } from 'vitest'
import { statusLabel, trayColorForPhase } from './status'

describe('trayColorForPhase', () => {
  it('maps healthy to green', () => {
    expect(trayColorForPhase('healthy')).toBe('green')
  })

  it('maps restart_pending to amber', () => {
    expect(trayColorForPhase('restart_pending')).toBe('amber')
  })

  it('maps stopped and error to red', () => {
    expect(trayColorForPhase('stopped')).toBe('red')
    expect(trayColorForPhase('error')).toBe('red')
  })

  it('maps transitional states to grey', () => {
    expect(trayColorForPhase('starting')).toBe('grey')
    expect(trayColorForPhase('stopping')).toBe('grey')
  })
})

describe('statusLabel', () => {
  it('returns human labels', () => {
    expect(statusLabel('restart_pending')).toBe('Restart required')
    expect(statusLabel('healthy')).toBe('Healthy')
  })
})
