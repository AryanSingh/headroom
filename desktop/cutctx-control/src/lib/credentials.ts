export type CredentialStatus = {
  id: string
  configured: boolean
  masked: string | null
  unlocked_for_entry: boolean
}

/** Whether the UI should show a token input field. */
export function shouldShowCredentialInput(status: CredentialStatus): boolean {
  return status.unlocked_for_entry
}

/** Whether Rotate is available (configured and currently locked). */
export function canRotateCredential(status: CredentialStatus): boolean {
  return status.configured && !status.unlocked_for_entry
}
