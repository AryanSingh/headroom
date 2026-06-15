# Data Processing Addendum (DPA)

**Effective Date:** [EFFECTIVE_DATE]

**Referenced Agreement:** Master Service Agreement between [CUSTOMER_NAME] and CutCtx ("Provider") dated [MSA_DATE].

---

## 1. Scope and Purpose

1.1 This DPA applies when Provider processes personal data on behalf of Customer in connection with CutCtx services.

1.2 **"Personal Data"** means any information relating to an identified or identifiable natural person.

1.3 **"Processing"** means any operation performed on Personal Data, including collection, storage, use, and deletion.

---

## 2. Data Processing Details

2.1 **Subject Matter.** Provider processes anonymized usage metrics (compression ratios, token counts, error rates) to provide and improve CutCtx services.

2.2 **Duration.** Processing continues for the duration of the Subscription Term plus any applicable retention period.

2.3 **Nature and Purpose.** Processing is limited to:
- (a) Anonymized telemetry for service improvement.
- (b) License key management and validation.
- (c) Aggregate analytics for service health monitoring.

2.4 **Types of Personal Data.** Minimal: email address (for license management), IP address (for rate limiting), and usage metadata.

2.5 **Categories of Data Subjects.** Customer's Authorized Users who interact with CutCtx.

---

## 3. Customer Obligations

3.1 Customer warrants that it has a lawful basis for sharing Personal Data with Provider.

3.2 Customer shall ensure that Authorized Users are informed of the data processing described in this DPA.

3.3 Customer shall not instruct Provider to process Personal Data in a manner that violates applicable law.

---

## 4. Provider Obligations

4.1 **Processing Instructions.** Provider shall process Personal Data only on Customer's documented instructions.

4.2 **Confidentiality.** Provider shall ensure that personnel authorized to process Personal Data are bound by confidentiality obligations.

4.3 **Security.** Provider implements appropriate technical and organizational measures, including:
- Encryption of data in transit (TLS 1.2+) and at rest (AES-256).
- Access controls and audit logging.
- Regular security assessments.

4.4 **Sub-processors.** Provider shall not engage sub-processors without prior written consent from Customer. Currently approved sub-processors:
- Cloud infrastructure provider (for hosted deployments only).
- Email delivery service (for license key delivery).

4.5 **Data Subject Rights.** Provider shall assist Customer in responding to data subject requests within 30 days.

4.6 **Breach Notification.** Provider shall notify Customer within 72 hours of discovering a personal data breach.

---

## 5. International Transfers

5.1 Provider processes data in [PROCESSING_JURISDICTION].

5.2 For transfers outside the EEA, Provider relies on Standard Contractual Clauses (SCCs) or equivalent safeguards.

5.3 Customer may request a copy of the applicable transfer mechanism.

---

## 6. Data Retention and Deletion

6.1 Provider retains Personal Data only for as long as necessary to provide the services.

6.2 Upon termination, Provider shall delete all Personal Data within 30 days, except where retention is required by law.

6.3 Anonymized aggregate data may be retained indefinitely for service improvement.

---

## 7. Security Certifications

7.1 Provider maintains SOC 2 Type II readiness controls (see docs/security/SOC2_CONTROLS.md).

7.2 Provider shall provide evidence of compliance upon Customer's reasonable request.

---

## 8. Governing Law

8.1 This DPA is governed by the same law as the referenced MSA.

8.2 To the extent that EU/UK data protection law applies, this DPA is subject to the applicable jurisdiction's data protection authority.

---

## 9. Modifications

9.1 This DPA may only be modified in writing signed by both parties.

---

**Provider Signature:** _________________________ Date: _________

**Customer Signature:** _________________________ Date: _________

---

*This template is for reference purposes. Consult legal counsel before execution.*
