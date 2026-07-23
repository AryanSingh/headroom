# CutCtx Inline Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render and charge CutCtx plans from a Supabase catalog without leaving `cutctx.com`.

**Architecture:** A `billing_plans` catalog owns public CutCtx plan data and amounts. A catalog Edge Function returns only active display data, while `create-order` uses the same catalog server-side before contacting Razorpay. The static CutCtx pricing page uses those functions and Razorpay Checkout directly, then returns buyers to the existing CutCtx license portal.

**Tech Stack:** Supabase Postgres and Edge Functions, Razorpay Checkout.js, static HTML/CSS/ES modules, Vitest/Deno tests.

## Global Constraints

- The catalog is the only source of plan amounts; browsers never submit an amount.
- Seed `starter` (Team) and `studio` (Business) at USD 200 minor units / $2 monthly.
- Razorpay keys and Supabase service-role credentials remain server-side.
- The CutCtx static CSP permits only `https://checkout.razorpay.com` and the configured Supabase origin in addition to existing self restrictions.
- Successful CutCtx checkout returns to `https://cutctx.com/licenses`.

---

### Task 1: Add the authoritative Supabase billing catalog

**Files:**
- Create: `supabase/migrations/202607230006_billing_plan_catalog.sql`
- Create: `supabase/functions/_shared/billing-plans.ts`
- Test: `supabase/functions/tests/billing-plans.test.ts`

**Interfaces:**
- Produces `getActivePlan(admin, product, planId, billing)` returning `{ id, product, planId, name, description, amount, currency, interval }`.
- Produces `listActivePlans(admin, product)` returning public plan rows ordered by display order.

- [ ] **Step 1: Write the failing catalog tests**

```ts
expect(normalizePlanRow({ product: 'cutctx', plan_id: 'starter', amount: 200, currency: 'USD', interval: 'monthly' }))
  .toMatchObject({ planId: 'starter', amount: 200, currency: 'USD' });
expect(normalizePlanRow({ active: false })).toBeNull();
```

- [ ] **Step 2: Run the catalog test and confirm it fails because the shared module is absent.**

Run: `deno test --allow-env --allow-net supabase/functions/tests/billing-plans.test.ts`

- [ ] **Step 3: Add the migration and minimal shared catalog helper.**

```sql
create table public.billing_plans (...);
insert into public.billing_plans (product, plan_id, name, amount, currency, interval, active, display_order)
values ('cutctx', 'starter', 'Team', 200, 'USD', 'monthly', true, 10),
       ('cutctx', 'studio', 'Business', 200, 'USD', 'monthly', true, 20);
```

The helper validates fields, filters inactive rows, and queries with an injected Supabase client.

- [ ] **Step 4: Run the catalog test and confirm it passes.**

- [ ] **Step 5: Commit the catalog task.**

### Task 2: Use the catalog for public retrieval and order creation

**Files:**
- Create: `supabase/functions/list-plans/index.ts`
- Modify: `supabase/functions/create-order/index.ts`
- Modify: `supabase/config.toml`
- Test: `supabase/functions/tests/create-order-catalog.test.ts`

**Interfaces:**
- `POST /functions/v1/list-plans` accepts `{ product: 'cutctx' }` and returns `{ plans: PublicPlan[] }`.
- `POST /functions/v1/create-order` accepts `{ product, planId, billing, userEmail }`; amount is derived from `billing_plans`.

- [ ] **Step 1: Write failing tests for catalog-backed order creation.**

```ts
expect(createOrder({ product: 'cutctx', planId: 'starter', userEmail: 'buyer@example.com' })).toCreateRazorpayOrder({ amount: 200 });
expect(createOrder({ product: 'cutctx', planId: 'missing', userEmail: 'buyer@example.com' })).toReturn(400);
```

- [ ] **Step 2: Run the targeted test and confirm it fails because `create-order` still calls `getCheckoutAmount`.**

- [ ] **Step 3: Implement the list endpoint and replace hard-coded amount selection with `getActivePlan`.**

Use `SUPABASE_SERVICE_ROLE_KEY` only inside Edge Functions; preserve order notes with `product`, `planId`, `billing`, and normalized email.

- [ ] **Step 4: Run all Supabase function tests and confirm they pass.**

- [ ] **Step 5: Commit the Edge Function task.**

### Task 3: Make CutCtx pricing database-backed and checkout inline

**Files:**
- Modify: `website/pricing/index.html`
- Create: `website/assets/pricing.js`
- Modify: `website/assets/site.css`
- Modify: `website/_headers`
- Test: `website/tests/inline-checkout.test.mjs`

**Interfaces:**
- `pricing.js` requests `list-plans`, renders catalog values into `[data-plan-id]` cards, and starts Razorpay only after email and plan selection.
- `pricing.js` invokes `create-order` and `verify-payment`, then navigates to `/licenses` on verified success.

- [ ] **Step 1: Write the static checkout test.**

```js
assert.match(pricingSource, /functions\/v1\/list-plans/);
assert.match(pricingSource, /functions\/v1\/create-order/);
assert.match(pricingSource, /window\.Razorpay/);
assert.match(pricingSource, /window\.location\.assign\(licensePortalUrl\(\)\)/);
```

- [ ] **Step 2: Run it and confirm it fails because `pricing.js` does not exist.**

- [ ] **Step 3: Replace external PitchToShip billing links with CutCtx plan buttons and inline checkout panel.**

Load Razorpay lazily, use server-provided order amount/key, report recoverable errors, and use `$2 / month` only as a pre-load placeholder until catalog rendering replaces it.

- [ ] **Step 4: Update CSP and run the static test plus JavaScript syntax check.**

- [ ] **Step 5: Commit the CutCtx UI task.**

### Task 4: Deploy and verify the complete flow

**Files:**
- Modify only if verification reveals a defect.

- [ ] **Step 1: Apply the migration and deploy `list-plans` and updated `create-order`.**

Run: `supabase db push` then `supabase functions deploy list-plans create-order --project-ref udeekuvifncmqvoywhlg`.

- [ ] **Step 2: Run full PitchToShip tests/build and static CutCtx checks.**

- [ ] **Step 3: Deploy the CutCtx Pages project and smoke-test live catalog/CSP/CORS.**

- [ ] **Step 4: Commit and push all scoped source changes.**
