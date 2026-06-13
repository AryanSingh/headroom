# Headroom Security Questionnaire Worksheet

## Purpose

Use this worksheet to answer common customer security review questions consistently.

## Hosting Model

**Question:** Where is the product hosted?  
**Answer:** Headroom is typically self-hosted in the customer environment. Customer data remains within customer-managed infrastructure except for requests sent to the customer-selected upstream model provider.

## Data Storage

**Question:** What customer data is stored?  
**Answer:** Headroom can store customer-managed local operational data such as CCR records, memory data, audit records, org metadata, fleet records, and SCIM provisioning data depending on enabled features and tier.

**Question:** Is prompt content centrally stored by Headroom Labs?  
**Answer:** Not by default in this self-hosted model.

## Access Control

**Question:** Does the product support centralized identity?  
**Answer:** Yes. Enterprise deployments support SSO-aware admin authentication and RBAC.

**Question:** Are admin actions auditable?  
**Answer:** Yes. Enterprise deployments include audit log query and export.

## Retention

**Question:** Can retention be configured?  
**Answer:** Yes. Enterprise deployments include retention controls for relevant local stores.

## Deployment

**Question:** Can the product run in Kubernetes?  
**Answer:** Yes. Kubernetes manifests and Helm packaging are available.

**Question:** Can the product run in air-gapped environments?  
**Answer:** Yes, with pre-staged dependencies and offline runtime flags.

## Compliance

**Question:** Is SOC 2 complete?  
**Answer:** Do not claim completed certification unless independently achieved and approved for disclosure.

**Question:** Is a DPA available?  
**Answer:** A draft can be prepared, but final contractual language requires legal review.
