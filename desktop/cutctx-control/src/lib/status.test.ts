import { describe, expect, it } from 'vitest'
import {
  canRestartProxy,
  canStartProxy,
  canStopProxy,
  statusLabel,
  trayColorForPhase,
} from './status'

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

describe('power button gates', () => {
  it('disables start while proxy is healthy or restart_pending', () => {
    expect(canStartProxy('healthy')).toBe(false)
    expect(canStartProxy('restart_pending')).toBe(false)
    expect(canStartProxy('starting')).toBe(false)
    expect(canStartProxy('degraded')).toBe(false)
  })

  it('enables start only when stopped or error', () => {
    expect(canStartProxy('stopped')).toBe(true)
    expect(canStartProxy('error')).toBe(true)
  })

  it('disables stop when proxy is down', () => {
    expect(canStopProxy('stopped')).toBe(false)
    expect(canStopProxy('error')).toBe(false)
    expect(canStopProxy('stopping')).toBe(false)
  })

  it('enables stop when proxy is up', () => {
    expect(canStopProxy('healthy')).toBe(true)
    expect(canStopProxy('restart_pending')).toBe(true)
    expect(canStopProxy('starting')).toBe(true)
  })

  it('allows restart while running', () => {
    expect(canRestartProxy('healthy')).toBe(true)
    expect(canRestartProxy('restart_pending')).toBe(true)
    expect(canRestartProxy('stopped')).toBe(false)
  })
})
