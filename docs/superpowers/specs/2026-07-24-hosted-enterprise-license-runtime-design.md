# Hosted Enterprise License Runtime Design

## Goal

Make a CutCtx license downloaded from the hosted CutCtx portal the authoritative
credential for the Enterprise runtime, including online validation and seat
leasing, without removing the existing offline signed-token or local-database
fallbacks.

## Root cause

The runtime client calls legacy PitchToShip `/api/licenses/*` paths. The hosted
portal now owns licenses in Supabase and exposes `verify-license` and
`seat-heartbeat` Edge Functions. A portal-issued `cutctx_` key is therefore not
found by the runtime's legacy local SQLite database after remote verification
is unavailable.

## Chosen approach

Use the hosted Supabase Edge Functions as the primary runtime authority:

1. `verify_license(key, hwid)` posts `{ key }` to the hosted verification
   function and maps its `{ valid, tier, seatsLimit, expiresAt }` response into
   the existing runtime validation shape.
2. `heartbeat_seat(key, hwid)` posts `{ key, hwid }` to the hosted seat function
   and maps its accepted/rejected result into the existing seat-management
   shape.
3. A response from the hosted service is definitive: invalid or expired keys
   are rejected and must not fall back to local state. Network/configuration
   failures return `None`, preserving the existing offline signed-token and
   local SQLite fallback behavior.
4. Configuration remains explicit through environment variables. The public
   Supabase anon key is supplied as a runtime configuration value, never a
   service-role credential.

## Acceptance evidence

- Focused client tests cover valid, definitive-invalid, and transport-failure
  responses, including the exact Supabase request paths and payloads.
- Proxy license validation accepts a hosted Enterprise response and exposes the
  Enterprise plan.
- Seat checkout uses the hosted heartbeat result and rejects a capacity denial.
- The existing Enterprise smoke suite proves the accepted Enterprise plan
  enables every mapped Enterprise entitlement plus organization, RBAC, audit,
  and retention flows.
- A live call using the portal-issued Enterprise key validates as Enterprise;
  its live heartbeat succeeds without revealing the key.

## Non-goals

- No service-role key in clients or source control.
- No duplication or migration of hosted license rows into local SQLite.
- No changes to checkout, payment, or email delivery.
