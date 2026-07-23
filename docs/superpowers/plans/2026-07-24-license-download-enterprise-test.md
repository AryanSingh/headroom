# License Download and Enterprise Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe per-license downloads to the CutCtx portal and provision plus validate a dedicated Enterprise test entitlement for the current license account.

**Architecture:** The existing authenticated `my-licenses` response remains the single source for the portal. Each rendered card will create a browser-local text download from those authorized fields only. A new immutable Supabase migration will insert an Enterprise license for `aryan.iitgn@gmail.com`; live hosted verification and seat-heartbeat tests will exercise Builder, Team, and Enterprise tier boundaries.

**Tech Stack:** Static JavaScript and CSS on Cloudflare Pages; Supabase Postgres migrations and Edge Functions; Node test runner; Vitest; Playwright CLI.

## Global Constraints

- Do not include session tokens, payment identifiers, customer ids, or database ids in downloaded files.
- Generate a text file locally in the customer browser; do not add an export API.
- Keep the existing Builder = 1, Team = 10, Business = 50, and Enterprise = 500 seat limits.
- Provision the Enterprise test entitlement only for `aryan.iitgn@gmail.com` and keep existing Builder and Team records intact.
- Use a fresh Magic Link for browser verification; never expose its token or a license key in test output.

---

### Task 1: Provision an isolated Enterprise test license

**Files:**
- Create: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/.worktrees/cutctx-commerce-release/supabase/migrations/202607240001_provision_aryan_enterprise_license.sql`
- Modify: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/.worktrees/cutctx-commerce-release/supabase/functions/tests/license-limits.test.ts`

**Interfaces:**
- Consumes: `public.customers(email, plan)` and `public.licenses(key, tier, customer_id, status, expires_at)`.
- Produces: one active `enterprise` row owned by `aryan.iitgn@gmail.com`, without changing existing license rows.

- [ ] **Step 1: Write the failing migration contract test**

```ts
it('provisions an enterprise test license without replacing existing lower-tier licenses', () => {
  const migration = readFileSync(resolve(process.cwd(), 'supabase/migrations/202607240001_provision_aryan_enterprise_license.sql'), 'utf8');
  expect(migration).toContain("values ('aryan.iitgn@gmail.com', 'enterprise')");
  expect(migration).toContain("and tier = 'enterprise'");
  expect(migration).toContain("now() + interval '1 year'");
});
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `npm run test -- supabase/functions/tests/license-limits.test.ts`

Expected: FAIL because the dated Enterprise migration does not exist.

- [ ] **Step 3: Add the idempotent migration**

```sql
do $$
declare customer_record public.customers;
begin
  insert into public.customers (email, plan)
  values ('aryan.iitgn@gmail.com', 'enterprise')
  on conflict (email) do nothing;
  select * into customer_record
  from public.customers
  where email = 'aryan.iitgn@gmail.com';

  if not exists (
    select 1 from public.licenses
    where customer_id = customer_record.id
      and tier = 'enterprise'
      and status = 'active'
      and expires_at > now()
  ) then
    insert into public.licenses (key, tier, customer_id, expires_at)
    values ('cutctx_' || replace(gen_random_uuid()::text, '-', ''), 'enterprise', customer_record.id, now() + interval '1 year');
  end if;
end;
$$;
```

- [ ] **Step 4: Run the contract test to verify it passes**

Run: `npm run test -- supabase/functions/tests/license-limits.test.ts`

Expected: PASS.

- [ ] **Step 5: Apply the migration and verify the production schema is current**

Run: `supabase db push --project-ref udeekuvifncmqvoywhlg --yes`

Expected: migration applies once; a second run reports that the remote database is up to date.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/202607240001_provision_aryan_enterprise_license.sql supabase/functions/tests/license-limits.test.ts
git commit -m "test: provision enterprise license fixture"
```

### Task 2: Add safe license-file downloads to the CutCtx portal

**Files:**
- Modify: `/Users/aryansingh/Documents/Claude/Projects/headroom/website/assets/licenses.js`
- Modify: `/Users/aryansingh/Documents/Claude/Projects/headroom/website/assets/site.css`
- Create: `/Users/aryansingh/Documents/Claude/Projects/headroom/website/tests/license-download.test.mjs`

**Interfaces:**
- Consumes: license objects shaped as `{ key, tier, status, expiresAt, seatsUsed, seatsLimit }` from `my-licenses`.
- Produces: `downloadLicense(license)` which creates a `text/plain` blob and downloads `${tier}-cutctx-license.txt`.

- [ ] **Step 1: Write the failing portal contract test**

```js
test('license cards offer a safe local text download', () => {
  const portal = readFileSync(new URL('../assets/licenses.js', import.meta.url), 'utf8');
  assert.match(portal, /function downloadLicense\(license\)/);
  assert.match(portal, /new Blob\(\[licenseText\], \{ type: 'text\/plain;charset=utf-8' \}\)/);
  assert.match(portal, /download = `\$\{license\.tier\}-cutctx-license\.txt`/);
  assert.doesNotMatch(portal, /accessToken|refresh_token|payment_id/);
});
```

- [ ] **Step 2: Run the portal contract test to verify it fails**

Run: `node --test website/tests/license-download.test.mjs`

Expected: FAIL because `downloadLicense` does not exist.

- [ ] **Step 3: Implement the minimal local download flow**

```js
function downloadLicense(license) {
  const licenseText = [
    'CutCtx License',
    `License key: ${license.key}`,
    `Tier: ${license.tier}`,
    `Status: ${license.status}`,
    `Seat limit: ${license.seatsLimit}`,
    `Expires: ${dateLabel(license.expiresAt)}`,
  ].join('\n') + '\n';
  const url = URL.createObjectURL(new Blob([licenseText], { type: 'text/plain;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${license.tier}-cutctx-license.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}
```

Add a `Download key` button to each `.license-card`, set its `type` to `button`, bind it to `downloadLicense(license)`, and add the existing `.button.button-secondary` classes.

- [ ] **Step 4: Add responsive card-action styling**

```css
.license-card-actions { display: flex; flex-wrap: wrap; gap: 0.7rem; margin-top: 1rem; }
.license-card-actions .button { min-height: 2.5rem; }
```

- [ ] **Step 5: Run all static portal tests**

Run: `node --test website/tests/*.test.mjs`

Expected: PASS.

- [ ] **Step 6: Deploy the CutCtx static site**

Run: `wrangler pages deploy website --project-name cutctx --branch main`

Expected: Cloudflare Pages returns a deployment URL.

- [ ] **Step 7: Commit**

```bash
git add website/assets/licenses.js website/assets/site.css website/tests/license-download.test.mjs
git commit -m "feat: download CutCtx license keys"
```

### Task 3: Verify tier boundaries and portal rendering

**Files:**
- Modify: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/.worktrees/cutctx-commerce-release/supabase/functions/tests/license-limits.test.ts`

**Interfaces:**
- Consumes: `verify-license` response `{ valid, tier, seatsLimit, expiresAt }` and `seat-heartbeat` response `{ accepted, seatsUsed, seatsLimit }`.
- Produces: automated tier-limit assertions and a recorded live verification result with no secrets displayed.

- [ ] **Step 1: Add failing live-contract expectations for Enterprise capacity**

```ts
it('keeps enterprise capacity at 500 seats', () => {
  expect(licenseSeatLimit('enterprise')).toBe(500);
});
```

- [ ] **Step 2: Run the focused test**

Run: `npm run test -- supabase/functions/tests/license-limits.test.ts`

Expected: PASS if the existing invariant is preserved; otherwise stop and fix the seat-limit helper before proceeding.

- [ ] **Step 3: Run hosted verification with the three authenticated portal license keys**

Use a short Node script that:

```js
for (const license of licenses) {
  const verification = await post('verify-license', { key: license.key });
  assert.equal(verification.valid, true);
  assert.equal(verification.seatsLimit, expectedLimits[verification.tier]);
}
```

Print only `{ tier, seatsLimit, valid }`; never print the key or bearer session.

- [ ] **Step 4: Exercise seat-heartbeat boundaries**

Use deterministic `hwid` values prefixed `enterprise-test-`, send one Builder heartbeat, eleven Team heartbeats, and five hundred one Enterprise heartbeats. Assert that the next heartbeat is rejected for each tier. Reuse the same identifiers for idempotency, then clean them up through the existing seat expiry behavior rather than deleting customer licenses.

- [ ] **Step 5: Run the full PitchToShip checks**

Run: `npm run test && npm run build`

Expected: all tests pass and Vite completes successfully.

- [ ] **Step 6: Verify the live CutCtx portal in a browser**

Generate a fresh admin Magic Link with `redirectTo: 'https://cutctx.com/licenses/'`, open it with Playwright CLI, wait for the portal response, and confirm:

```text
Your CutCtx licenses
builder
team
enterprise
Download key
```

Capture a screenshot only if it does not contain a readable license key.

- [ ] **Step 7: Commit and push the PitchToShip verification changes**

```bash
git add supabase/functions/tests/license-limits.test.ts
git commit -m "test: verify enterprise license boundaries"
git push origin HEAD:master
```
