# CutCtx Cloudflare launch runbook

## Scope protection

This runbook applies only to `cutctx.com` and a new Cloudflare Pages project
named `cutctx`. Do not edit, delete, redeploy, or change DNS for
`pitchtoship.com` or any other existing Cloudflare zone, Worker, Pages project,
record, route, secret, or setting.

## Prerequisites

Before any public legal route or checkout button is published, the owner must
supply and approve all of the following:

1. Registered legal entity name.
2. Registered business address and applicable tax registration information.
3. Legal-support email address.
4. Privacy-contact email address.
5. Exact refund and cancellation policy accepted by the payment processor.
6. Governing-law jurisdiction.
7. Legal-page effective date.
8. Confirmed PitchToShip checkout base URL and Enterprise sales-contact URL.

Do not publish a public legal route or direct checkout button until every value
has been supplied and approved by the owner.

## Approved public legal details

- Legal entity: `PITCHTOSHIP (OPC) PRIVATE LIMITED`.
- Business address: Panch M Corp, Tola, V.C. Lane, Muzaffarpur, Bihar 842002,
  India.
- Public legal, privacy, billing, and support contact: `hello@aoexl.com`.
- Refund policy: a 14-day money-back guarantee for the first self-service paid
  purchase; renewals, partial billing periods, custom work, and completed
  services are non-refundable except where required by law.
- Governing law: India; courts in Muzaffarpur, Bihar, India.
- Legal-page effective date: 21 July 2026.

## Cloudflare zone

1. In the existing Cloudflare account, add `cutctx.com` as a new zone.
2. Copy the two authoritative nameservers Cloudflare assigns exactly.
3. Confirm that no existing `pitchtoship.com` zone, DNS record, Worker, or
   Pages project has been selected or changed.

## BigRock nameserver change

1. Record the existing `cutctx.com` authoritative nameservers before editing.
2. Replace only `cutctx.com` nameservers with the two assigned Cloudflare
   values.
3. Do not change `pitchtoship.com`, account defaults, email products, contact
   details, or RDDS/WHOIS consent.
4. Record the old values and exact timestamp below after the change.

| Field | Value |
| --- | --- |
| Previous BigRock nameservers | Not yet changed |
| Assigned Cloudflare nameservers | Not yet created |
| Nameserver-change timestamp | Not yet changed |
| Cloudflare activation status | Not yet created |

## Pages deployment

1. Create a new direct-upload Cloudflare Pages project named `cutctx`.
2. Upload only the contents of `website/` from this repository.
3. Confirm `_headers`, `_redirects`, `robots.txt`, and `sitemap.xml` are at
   the deployment root.
4. Verify the preview deployment before adding production custom domains.

## Custom domains

1. Attach `cutctx.com` to the dedicated `cutctx` Pages project after the zone
   is active.
2. Wait for domain validation and TLS issuance to succeed.
3. Attach `www.cutctx.com` to the same Pages project.
4. Confirm the static redirect sends `www.cutctx.com/*` to
   `https://cutctx.com/:splat`.

## Production verification

Verify `/`, `/pricing/`, `/docs/`, `/security/`, `/terms/`, `/privacy/`, and
`/refunds/` for HTTPS, canonical URL, title, description, footer links, and
working CTA destination. Verify the checkout links open the expected
PitchToShip plan context without submitting a payment.

## Rollback

If the Cloudflare zone cannot validate or Pages cannot serve the site, leave
the existing BigRock nameservers in place. If CutCtx DNS was delegated and a
rollback is necessary, obtain owner confirmation, then restore only the exact
BigRock nameservers recorded above. Do not use a rollback action against any
PitchToShip resource.
