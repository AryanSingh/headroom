# CutCtx Privacy Policy

**Last updated:** June 2026

> **Important:** This policy is a draft template. It must be reviewed by qualified legal counsel before publication.

## 1. Overview

CutCtx Labs ("we," "us") builds privacy-first infrastructure for AI agents. CutCtx is designed to run entirely on your infrastructure — your prompts, code, and conversation data never leave your control.

This Privacy Policy describes the limited data we collect when you use CutCtx software and services.

## 2. Data We Do NOT Collect

CutCtx is self-hosted by design. We do **not** collect, store, or have access to:

- **Prompts or conversation content** sent to LLMs
- **Tool outputs, code, or file contents** processed by the compression engine
- **RAG chunks, search results, or logs** compressed by the proxy
- **Any data processed by the proxy, library, or CLI** during normal operation

Your data stays on your infrastructure. Period.

## 3. Data We DO Collect

### 3.1 Optional Aggregate Telemetry (When Enabled)

If you explicitly opt in to telemetry (via `HEADROOM_TELEMETRY=1` or license activation), we receive:

- Request counts and token savings (aggregate numbers only)
- Model distribution (which models are used, not what was sent)
- Compression algorithm performance metrics
- Error rates and types

**We never receive message content, tool outputs, code, or any payload data through telemetry.**

### 3.2 License and Billing Information

When you activate a paid license:

- **License key** and **machine fingerprint** (hardware identifier, not personal data) for license validation
- **Organization name** and **contact email** for billing and support
- **Payment information** is processed by Stripe and never touches our servers

### 3.3 Support Communications

If you contact us for support:

- Your email address and message content
- Relevant logs you choose to share (never automatically collected)
- Support communications are retained for 12 months for quality purposes

### 3.4 Website Analytics

When you visit cutctx.dev:

- Standard analytics: page views, referrer, browser type, IP address
- No tracking cookies or cross-site tracking
- Analytics data is retained for 90 days

## 4. How We Use Data

- **Aggregate telemetry:** To improve compression algorithms and prioritize development
- **License data:** To validate subscriptions and enforce entitlements
- **Support communications:** To resolve your issues and improve documentation
- **Website analytics:** To understand usage patterns and improve the website

## 5. Data Sharing

We do **not** sell your data to third parties. We may share data only:

- With service providers who assist in operating our services (Stripe for billing, analytics providers), bound by data processing agreements
- When required by law, valid legal process, or to protect our rights

## 6. Data Security

- All telemetry data is transmitted over TLS
- License data is encrypted at rest (Fernet encryption for local state)
- We maintain SOC 2 Type II readiness controls
- Access to production systems is logged and auditable

## 7. Data Retention

| Data Type | Retention Period |
|-----------|-----------------|
| Aggregate telemetry | 12 months |
| License/billing data | Duration of subscription + 12 months |
| Support communications | 12 months |
| Website analytics | 90 days |
| Your compressed data | Never leaves your infrastructure |

## 8. Your Rights

Depending on your jurisdiction, you may have the right to:

- **Access** the personal data we hold about you
- **Correct** inaccurate data
- **Delete** your data and account
- **Export** your data in a portable format
- **Object** to processing of your data

Contact hello@cutctx.dev to exercise any of these rights.

## 9. International Data Transfers

CutCtx Labs is based in the United States. If you are outside the US, your data may be transferred to and processed in the US. We rely on Standard Contractual Clauses (where applicable) and data processing agreements with our sub-processors.

## 10. Children's Privacy

CutCtx is not directed at individuals under 16. We do not knowingly collect data from children.

## 11. Changes to This Policy

We will notify you of material changes via email or prominent notice on our website. Continued use after changes take effect constitutes acceptance.

## 12. Contact

For privacy questions or data requests: hello@cutctx.dev

CutCtx Labs  
Wilmington, Delaware, United States
