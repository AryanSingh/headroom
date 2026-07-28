export type ProxyPhase =
  | 'stopped'
  | 'starting'
  | 'healthy'
  | 'degraded'
  | 'restart_pending'
  | 'stopping'
  | 'error'

export type TrayColor = 'green' | 'amber' | 'red' | 'grey'

export function trayColorForPhase(phase: ProxyPhase): TrayColor {
  switch (phase) {
    case 'healthy':
      return 'green'
    case 'restart_pending':
    case 'degraded':
      return 'amber'
    case 'error':
    case 'stopped':
      return 'red'
    case 'starting':
    case 'stopping':
      return 'grey'
    default:
      return 'red'
  }
}

export function statusLabel(phase: ProxyPhase): string {
  switch (phase) {
    case 'healthy':
      return 'Healthy'
    case 'restart_pending':
      return 'Restart required'
    case 'degraded':
      return 'Degraded'
    case 'starting':
      return 'Starting'
    case 'stopping':
      return 'Stopping'
    case 'error':
      return 'Error'
    case 'stopped':
      return 'Stopped'
    default:
      return phase
  }
}
