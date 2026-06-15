# Master Service Agreement (MSA)

**Effective Date:** [EFFECTIVE_DATE]

**Between:**

**Provider:** CutCtx ("Provider"), a software company operating the CutCtx platform at cutctx.dev.

**Customer:** [CUSTOMER_NAME] ("Customer"), a [ENTITY_TYPE] organized under the laws of [JURISDICTION].

---

## 1. Definitions

1.1 **"CutCtx"** means the context compression software platform, including the proxy, SDK, CLI tools, and associated documentation.

1.2 **"Customer"** means the entity identified above and its Authorized Users.

1.3 **"Authorized Users"** means employees, contractors, or agents of Customer who are authorized to use CutCtx under this Agreement, up to the number specified in the applicable Subscription Tier.

1.4 **"Subscription Term"** means the period during which Customer has paid for access to CutCtx, as specified in the applicable Order Form.

1.5 **"Order Form"** means the ordering document referencing this MSA that specifies the Subscription Tier, fees, and term.

1.6 **"Subscription Tier"** means the level of CutCtx access purchased: Builder (free), Team, Business, or Enterprise.

1.7 **"Software"** means the CutCtx binary, Python package, JavaScript SDK, Go SDK, and all associated components.

1.8 **"Documentation"** means the official CutCtx documentation, API references, and deployment guides.

---

## 2. Grant of License

2.1 **License Grant.** Subject to the terms of this Agreement and payment of applicable fees, Provider grants Customer a non-exclusive, non-transferable, non-sublicensable license to install and use CutCtx for the duration of the Subscription Term.

2.2 **Tier-Specific Rights.** Customer's use rights are limited to those associated with the purchased Subscription Tier:
- **Builder (Free):** Core compression features for individual use.
- **Team ($49/mo):** Team analytics, policy presets, budget controls.
- **Business ($149/mo):** Project model, rate limiting, compression hooks.
- **Enterprise (Custom):** SSO/SAML, RBAC, audit logs, retention controls.

2.3 **Seat Limits.** Enterprise and Business tiers are licensed per Authorized User. Customer shall not exceed the authorized user count without purchasing additional licenses.

---

## 3. Restrictions

3.1 Customer shall not:
- (a) Reverse engineer, decompile, or disassemble the Software, except to the extent permitted by applicable law.
- (b) Use CutCtx to develop a competing product or service.
- (c) Sublicense, rent, or lease the Software to third parties.
- (d) Remove or modify any proprietary notices on the Software.
- (e) Use the Software in violation of applicable laws or regulations.

3.2 **Open Source.** The core CutCtx engine is released under the Apache 2.0 license. Enterprise features (SSO, RBAC, audit logs) are proprietary and subject to this Agreement.

---

## 4. Payment Terms

4.1 **Fees.** Customer shall pay the fees specified in the Order Form. All fees are quoted in [CURRENCY] and are non-refundable except as expressly stated.

4.2 **Billing Cycle.** Subscriptions are billed monthly or annually as specified. Monthly subscriptions carry a 20% premium over annual pricing.

4.3 **Late Payment.** Overdue amounts accrue interest at 1.5% per month or the maximum rate permitted by law, whichever is lower.

4.4 **Auto-Renewal.** Subscriptions automatically renew for successive periods of the same duration unless either party provides 30 days' written notice of non-renewal.

4.5 **Taxes.** Fees are exclusive of all taxes. Customer is responsible for all applicable taxes, duties, and levies.

---

## 5. Data Processing

5.1 **Local-First Architecture.** CutCtx operates as a local-first system. All prompt data, context, and compression artifacts remain on Customer's infrastructure.

5.2 **No Prompt Data Collection.** Provider does not collect, store, or transmit any prompt data, user content, or LLM interactions processed by CutCtx.

5.3 **Telemetry.** CutCtx may transmit anonymized usage metrics (compression ratios, token counts, error rates) unless Customer opts out via configuration.

5.4 **Data Residency.** All Customer data processed by CutCtx remains within Customer's designated infrastructure and geographic region.

---

## 6. Confidentiality

6.1 Each party agrees to hold the other party's Confidential Information in strict confidence and not disclose it to third parties without prior written consent.

6.2 **Confidential Information** includes business plans, customer lists, pricing, and the terms of this Agreement.

6.3 These obligations survive for 3 years after termination of this Agreement.

---

## 7. Warranties and Disclaimers

7.1 **Warranty.** Provider warrants that CutCtx will perform materially as described in the Documentation during the Subscription Term.

7.2 **Disclaimer.** EXCEPT AS EXPRESSLY STATED, CUTCTX IS PROVIDED "AS IS" WITHOUT WARRANTIES OF ANY KIND, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

7.3 **No Guarantee of Results.** Provider does not guarantee specific compression ratios, cost savings, or performance improvements.

---

## 8. Indemnification

8.1 Provider shall indemnify Customer against third-party claims alleging that CutCtx infringes intellectual property rights, provided Customer:
- (a) Promptly notifies Provider of the claim.
- (b) Grants Provider sole control of the defense.
- (c) Cooperates as reasonably requested.

---

## 9. Limitation of Liability

9.1 **Cap.** Provider's total liability under this Agreement shall not exceed the fees paid by Customer in the 12 months preceding the claim.

9.2 **Exclusion.** Neither party shall be liable for indirect, incidental, special, consequential, or punitive damages, regardless of the cause of action.

---

## 10. Term and Termination

10.1 **Term.** This Agreement begins on the Effective Date and continues until all subscriptions expire or are terminated.

10.2 **Termination for Cause.** Either party may terminate with 30 days' written notice if the other party materially breaches this Agreement and fails to cure within 30 days.

10.3 **Effect of Termination.** Upon termination, Customer must cease all use of CutCtx and destroy all copies. Provider will provide a 30-day data export window for any locally stored analytics.

---

## 11. Governing Law

11.1 This Agreement is governed by the laws of [JURISDICTION], without regard to conflict of law principles.

11.2 Any disputes shall be resolved through binding arbitration in [ARBITRATION_LOCATION] under [ARBITRATION_RULES].

---

## 12. General Provisions

12.1 **Entire Agreement.** This MSA, together with any Order Forms, constitutes the entire agreement.

12.2 **Amendments.** Modifications must be in writing and signed by both parties.

12.3 **Assignment.** Neither party may assign this Agreement without prior written consent, except in connection with a merger or acquisition.

12.4 **Force Majeure.** Neither party is liable for delays caused by circumstances beyond reasonable control.

---

**Provider Signature:** _________________________ Date: _________

**Customer Signature:** _________________________ Date: _________

---

*This template is for reference purposes. Consult legal counsel before execution.*
