# DATA PROCESSING ADDENDUM

**This Data Processing Addendum** ("DPA") is entered into as of [EFFECTIVE_DATE] and forms part of the Master Service Agreement ("MSA") between:

**Cutctx, Inc.**, with its principal place of business at [CUTCTX_ADDRESS] ("Cutctx"), and

**[CUSTOMER_NAME]**, with its principal place of business at [CUSTOMER_ADDRESS] ("Customer").

This DPA is incorporated into and governed by the MSA. In the event of a conflict between this DPA and the MSA with respect to data protection and privacy obligations, this DPA shall control. Capitalized terms not defined herein shall have the meanings ascribed to them in the MSA.

---

## 1. DEFINITIONS AND RELATIONSHIP OF THE PARTIES

**1.1 Definitions.** As used in this DPA:

**"Applicable Data Protection Law"** means all data protection and privacy laws and regulations applicable to the processing of Personal Data under this DPA, including without limitation the General Data Protection Regulation (EU) 2016/679 ("GDPR"), the UK GDPR, the California Consumer Privacy Act as amended by the California Privacy Rights Act ("CCPA/CPRA"), and any implementing or successor legislation.

**"Controller"** means the natural or legal person, public authority, agency, or other body that, alone or jointly with others, determines the purposes and means of the processing of Personal Data. Under this DPA, Customer is the Controller.

**"Processor"** means the natural or legal person, public authority, agency, or other body that processes Personal Data on behalf of the Controller. Under this DPA, Cutctx is the Processor with respect to any Personal Data Customer includes in messages processed by the Cutctx Software.

**"Personal Data"** has the meaning given under Applicable Data Protection Law and, for purposes of this DPA, refers specifically to any personal data or personally identifiable information that Customer or Authorized Users include within message content submitted through the Cutctx Software.

**"Processing"** (and "Process" and "Processed") has the meaning given under Applicable Data Protection Law.

**"Data Subject"** means an identified or identifiable natural person to whom Personal Data relates.

**"Security Incident"** means any confirmed unauthorized access to, acquisition, disclosure, or loss of Personal Data in Cutctx's possession or control.

**1.2 Roles of the Parties.** The parties acknowledge and agree that:

(a) Customer acts as the Controller with respect to Personal Data. Customer determines the purposes and means of processing Personal Data and is responsible for all decisions regarding what Personal Data is submitted through the Cutctx Software.

(b) Cutctx acts as the Processor with respect to Personal Data solely to the extent, if any, that Customer or Authorized Users include Personal Data within message content that is processed by the Cutctx Software. Given the local-first architecture of the Cutctx Software (described in Section 2.2 below), Cutctx's role as Processor is narrowly scoped to any transient local processing that may occur.

(c) For purposes of the CCPA/CPRA, Cutctx acts as a Service Provider with respect to any Personal Data of California residents, and processes such Personal Data only for the Business Purpose described in Section 2 of this DPA.

---

## 2. NATURE AND PURPOSE OF PROCESSING

**2.1 Purpose.** Cutctx processes Personal Data solely to the extent necessary to provide the context compression services described in the MSA (the "Business Purpose"). Cutctx shall not process Personal Data for any purpose other than the Business Purpose or as otherwise required by Applicable Data Protection Law.

**2.2 Local-First Processing — No Server-Side Storage.** The Cutctx Software performs all context compression processing locally on Customer's own infrastructure. Specifically:

(a) No Personal Data included in Customer's message content is transmitted to or stored on Cutctx's servers;

(b) All processing of message content, including any Personal Data therein, occurs entirely within Customer's own computing environment;

(c) Cutctx does not have access to, and does not receive copies of, Customer's message content or any Personal Data contained therein;

(d) Any local cache of compressed context data resides entirely on Customer's infrastructure and is subject solely to Customer's data retention and deletion policies.

**2.3 Prohibition on Cross-Context Use.** Cutctx shall not: (a) sell Personal Data; (b) retain, use, or disclose Personal Data for any purpose other than the Business Purpose; (c) retain, use, or disclose Personal Data outside the direct business relationship with Customer; or (d) combine Personal Data with personal information received from other sources.

---

## 3. CATEGORIES OF PERSONAL DATA

**3.1 Potential Categories.** Given the nature of the Cutctx Software as a context compression tool for AI model interactions, Personal Data processed may potentially include:

(a) **Names and email addresses** — if Customer or Authorized Users include the names or email addresses of individuals within message content submitted to the Cutctx Software;

(b) **Professional contact information** — if Customer includes employee, customer, or partner contact details within message content;

(c) **Other identifiers** — any other information that identifies or could identify a natural person that Customer elects to include in message content.

**3.2 No Special Categories.** Cutctx does not knowingly process, and Customer should not submit through the Cutctx Software, any Special Categories of Personal Data as defined under Article 9 of the GDPR (including health data, biometric data, racial or ethnic origin, political opinions, religious beliefs, genetic data, or data concerning a person's sex life or sexual orientation). Customer is solely responsible for ensuring that no Special Categories of Personal Data are included in message content.

**3.3 No Direct Collection.** Cutctx does not independently collect Personal Data from Data Subjects. Any Personal Data processed under this DPA is provided solely by Customer through the use of the Cutctx Software.

---

## 4. SUB-PROCESSORS

**4.1 No Sub-Processors by Default.** As of the Effective Date, Cutctx does not engage any sub-processors to process Personal Data on Customer's behalf in connection with the Cutctx Software. This is consistent with the local-first architecture described in Section 2.2, under which no Personal Data is transmitted to Cutctx's infrastructure or any third party.

**4.2 Sub-Processor List.** Cutctx maintains a current list of any approved sub-processors at: **cutctx.com/sub-processors**. Customer acknowledges that this list may be updated from time to time.

**4.3 Notice of Changes.** Cutctx shall provide Customer with at least thirty (30) days' prior written notice before engaging any new sub-processor that will process Personal Data. Such notice shall be provided by updating the sub-processor list at the URL above and, where Customer has subscribed to notifications, by email to [NOTICE_EMAIL]. Customer may object to a new sub-processor by providing written notice to Cutctx within fourteen (14) days of the notification. The parties shall work in good faith to resolve any reasonable objection.

**4.4 Sub-Processor Obligations.** Where Cutctx engages sub-processors, Cutctx shall impose data protection obligations on each sub-processor equivalent to those in this DPA and shall remain liable to Customer for the acts and omissions of its sub-processors.

---

## 5. DATA SUBJECT RIGHTS

**5.1 Customer Responsibility.** As the Controller, Customer is primarily responsible for responding to requests from Data Subjects exercising their rights under Applicable Data Protection Law (including rights of access, rectification, erasure, restriction of processing, data portability, and objection).

**5.2 Cutctx Assistance.** To the extent that Cutctx holds or controls any Personal Data (which, given the local-first architecture, is not expected), Cutctx shall provide reasonable assistance to Customer in fulfilling its obligations to respond to Data Subject requests. Such assistance shall include, where applicable:

(a) Promptly forwarding to Customer any Data Subject request received directly by Cutctx within five (5) business days;

(b) Providing Customer with information reasonably necessary for Customer to respond to Data Subject requests, to the extent such information is within Cutctx's possession or control;

(c) Implementing technical and organizational measures, as reasonably requested by Customer, to assist with fulfilling Data Subject rights.

**5.3 Cost of Assistance.** Cutctx shall provide routine assistance at no additional charge. If Customer requests assistance that requires substantial additional resources, the parties shall agree in writing on reasonable compensation before Cutctx is obligated to provide such assistance.

---

## 6. SECURITY MEASURES

**6.1 Technical and Organizational Measures.** Cutctx implements and maintains the following technical and organizational security measures designed to protect Personal Data against unauthorized access, disclosure, alteration, or destruction:

(a) **Encryption at Rest:** All locally cached context data is encrypted using Fernet AES-128 symmetric encryption. Encryption keys are managed per-user and stored separately from encrypted data.

(b) **Encryption in Transit:** All communications between Cutctx software components use TLS 1.2 or higher. Unencrypted transmission of Personal Data is not permitted.

(c) **Access Control:** HMAC-signed tokens are used to authenticate and authorize access to locally processed context data, preventing unauthorized components from accessing compressed context stores.

(d) **Access Logging:** Access to context data and proxy interactions is logged locally on Customer's infrastructure for audit and anomaly detection purposes. Logs are retained subject to Customer's own retention policies.

(e) **Least Privilege:** Cutctx Software components operate with the minimum permissions necessary to perform their functions.

(f) **Vulnerability Management:** Cutctx maintains a vulnerability disclosure program and releases security patches on a regular basis.

**6.2 Updates to Security Measures.** Cutctx may update these security measures from time to time, provided that any updates shall not materially reduce the overall level of protection afforded to Personal Data.

**6.3 Customer Responsibilities.** Customer is responsible for implementing appropriate security measures on its own infrastructure, including securing the devices and systems on which the Cutctx Software is installed and managing access credentials for Authorized Users.

---

## 7. INTERNATIONAL TRANSFERS

**7.1 No Transfers Outside Customer Infrastructure.** Given the local-first architecture of the Cutctx Software, Customer's Personal Data is processed exclusively within Customer's own infrastructure. Cutctx does not receive, store, or process Personal Data on its servers and therefore does not transfer Personal Data across international borders.

**7.2 No Cross-Border Transfer by Cutctx.** Cutctx does not transfer Personal Data to any country outside the country in which Customer's infrastructure is located. If Customer's infrastructure spans multiple jurisdictions, Customer is responsible for ensuring that its own internal data flows comply with Applicable Data Protection Law.

**7.3 Standard Contractual Clauses.** To the extent any transfer of Personal Data between Customer and Cutctx is found by a competent authority to be subject to transfer mechanism requirements under the GDPR or UK GDPR, the parties agree to execute the applicable standard contractual clauses ("SCCs") as required by the European Commission or UK Information Commissioner's Office, as applicable. The parties shall cooperate in good faith to implement such transfer mechanisms promptly upon request.

---

## 8. BREACH NOTIFICATION

**8.1 Notification Obligation.** In the event Cutctx becomes aware of a Security Incident affecting Personal Data, Cutctx shall notify Customer without undue delay and in any event within seventy-two (72) hours of becoming aware of the Security Incident.

**8.2 Content of Notification.** Cutctx's notification shall include, to the extent available at the time of notification:

(a) A description of the nature of the Security Incident, including the categories and approximate number of Data Subjects affected, and the categories and approximate volume of Personal Data records affected;

(b) The name and contact details of Cutctx's data protection contact point;

(c) A description of the likely consequences of the Security Incident;

(d) A description of the measures taken or proposed to address the Security Incident, including measures to mitigate its possible adverse effects.

**8.3 Supplemental Information.** Where Cutctx cannot provide all required information within the initial seventy-two (72) hour notification, it shall provide information in phases as it becomes available, without undue further delay.

**8.4 Customer Notification Obligations.** Customer remains solely responsible for determining whether a Security Incident triggers Customer's own notification obligations under Applicable Data Protection Law and for providing any required notifications to Data Subjects, supervisory authorities, or other parties. Cutctx shall provide reasonable cooperation to Customer in connection with such notifications.

**8.5 No Acknowledgment of Fault.** Cutctx's notification of a Security Incident does not constitute an acknowledgment of fault or liability.

---

## 9. DELETION AND RETURN OF PERSONAL DATA

**9.1 No Cutctx Retention.** Cutctx does not retain any Customer Personal Data on its servers or infrastructure. Consistent with the local-first architecture described in Section 2.2, no Customer Personal Data is transmitted to or stored by Cutctx.

**9.2 Local Cache Under Customer Control.** Any local cache of compressed context data generated by the Cutctx Software resides entirely on Customer's own infrastructure, under Customer's sole control. Customer retains full authority over the storage, retention, and deletion of such local cache data in accordance with Customer's own data retention policies.

**9.3 Post-Termination.** Upon termination or expiration of the MSA, Customer retains all authority over and responsibility for any locally cached data on Customer's infrastructure. Cutctx has no data to return or delete. Customer should uninstall the Cutctx Software and manage any residual local data in accordance with its own data governance policies.

**9.4 Certification.** Upon Customer's written request following termination, Cutctx shall provide written certification confirming that Cutctx does not hold any Personal Data belonging to Customer.

---

## 10. AUDIT RIGHTS

**10.1 Customer Audit Rights.** Customer may audit Cutctx's compliance with this DPA no more than once per calendar year (or more frequently if required by a supervisory authority or following a confirmed Security Incident) upon at least thirty (30) days' prior written notice to Cutctx.

**10.2 Scope of Audit.** Audits shall be limited to information and systems relevant to Cutctx's processing of Personal Data under this DPA. Audits shall be conducted during Cutctx's normal business hours and shall not unreasonably disrupt Cutctx's operations.

**10.3 Audit Costs.** All costs and expenses associated with any audit (including Customer's own costs and any reasonable costs incurred by Cutctx in facilitating the audit) shall be borne by Customer, unless the audit reveals a material breach of this DPA by Cutctx.

**10.4 Confidentiality of Audit.** Customer shall treat all information obtained during an audit as Confidential Information of Cutctx and shall not disclose audit findings to any third party without Cutctx's prior written consent, except as required by Applicable Data Protection Law or a supervisory authority.

**10.5 Third-Party Auditors.** Customer may conduct audits through a mutually agreed independent third-party auditor, provided such auditor executes a confidentiality agreement acceptable to Cutctx prior to commencing the audit.

---

## 11. GDPR AND CCPA SPECIFIC PROVISIONS

**11.1 GDPR Article 28 Compliance.** This DPA is intended to satisfy the requirements of Article 28 of the GDPR for a data processing agreement between a controller and processor. Cutctx shall:

(a) Process Personal Data only on documented instructions from Customer, including with regard to transfers of Personal Data to a third country;

(b) Ensure that persons authorized to process Personal Data have committed themselves to confidentiality or are under an appropriate statutory obligation of confidentiality;

(c) Take all measures required pursuant to Article 32 of the GDPR (security of processing);

(d) Assist Customer with its obligations under Articles 32-36 of the GDPR, including data protection impact assessments, where applicable;

(e) Make available to Customer all information necessary to demonstrate compliance with the obligations laid down in this Article and allow for and contribute to audits and inspections conducted by Customer or an auditor mandated by Customer.

**11.2 CCPA Service Provider Terms.** For purposes of the CCPA/CPRA, Cutctx certifies that it understands and will comply with the restrictions applicable to a Service Provider, including the prohibition on selling, retaining, using, or disclosing Personal Information (as defined under the CCPA) for any purpose other than the Business Purpose specified in this DPA.

---

## 12. GOVERNING LAW AND MISCELLANEOUS

**12.1 Governing Law.** This DPA shall be governed by the laws of [GOVERNING_LAW_STATE] / [JURISDICTION], consistent with the governing law provisions of the MSA.

**12.2 Order of Precedence.** In the event of a conflict between this DPA and the MSA regarding the processing of Personal Data, this DPA shall prevail to the extent of the conflict. In all other respects, the MSA shall govern.

**12.3 Amendments.** Cutctx may update this DPA from time to time to reflect changes in Applicable Data Protection Law or Cutctx's processing practices. Cutctx shall provide Customer with at least thirty (30) days' prior written notice of any material changes to this DPA.

**12.4 Entire Agreement on Data Processing.** This DPA, together with the MSA and any applicable SCCs, constitutes the entire agreement between the parties with respect to the processing of Personal Data and supersedes all prior agreements and understandings on the subject matter hereof.

---

**IN WITNESS WHEREOF**, the parties have executed this Data Processing Addendum as of the Effective Date.

**Cutctx, Inc.**

Signature: ___________________________
Name: ___________________________
Title: ___________________________
Date: ___________________________

**[CUSTOMER_NAME]**

Signature: ___________________________
Name: ___________________________
Title: ___________________________
Date: ___________________________
