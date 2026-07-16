# UI/UX Review: Orchestration and Model Routing

Date: 2026-07-15
Evidence: `audit/screenshots/orchestrator-routing-desktop.png`, `audit/screenshots/orchestrator-routing-mobile.png`

## Executive assessment

The visual system is coherent and polished at a glance, but the Orchestrator surface is too dense, too infrastructure-led, and not sufficiently explanatory for a high-risk control plane. The mobile layout is not usable at 390×844 because the fixed desktop navigation consumes the viewport and the main content is effectively off-canvas.

## Findings

### P0 — Mobile reflow failure

At 390×844, the fixed sidebar remains desktop-width and the main routing content is not meaningfully visible. This fails the practical intent of WCAG 2.1 SC 1.4.10 (Reflow) and makes the control plane unusable on small screens.

Evidence: `audit/screenshots/orchestrator-routing-mobile.png`.

### P1 — Desktop content clipping and density

The six-tab orchestration strip and long explanatory copy clip or overflow at the captured desktop viewport. The page also stacks global routing mode, routing evidence, provider policy, and orchestration policy in one long surface without a clear hierarchy.

Evidence: `audit/screenshots/orchestrator-routing-desktop.png`.

### P1 — Two routing vocabularies collide

“Routing policy,” “Routing mode,” “Balanced,” “Role locked,” and “Fallback” appear in adjacent regions but describe different layers. The UI needs a visible decision pipeline and plain-language scope labels.

### P1 — Preview lacks trust signals

The preview has no draft/live indicator, no request scenario inputs, no candidate rejection table, no estimated cost/latency, and no explicit statement that it does not invoke a provider.

### P1 — Form controls lack contextual help

Timeout, retries, cooldown, strict/relaxed mode, and policy choices have labels but no inline explanation of operational consequences. WCAG 2.1 SC 3.3.2 (Labels or Instructions) is only partially satisfied in spirit because the controls are labeled but not sufficiently instructed for safe use.

### P2 — Tabs are semantically incomplete

The tablist and tab roles are present, but the implementation does not expose explicit `aria-controls`/tabpanel relationships or the expected single-tab-stop arrow-key behavior. This weakens keyboard predictability under WCAG 2.1 SC 2.1.1 (Keyboard), SC 2.4.3 (Focus Order), and the WAI-ARIA tabs pattern.

### P2 — Status is too color-dependent

Healthy/available/selected states rely heavily on pills and color. Text labels exist, but contrast and state hierarchy should be verified against WCAG 2.1 SC 1.4.3 (Contrast Minimum) and SC 1.4.11 (Non-text Contrast) in both themes.

### P2 — Loading and error states are inconsistent

The page can show “healthy” in the global shell while orchestration data is still loading or an endpoint is unavailable. The product needs one explicit control-plane state and stale-data labeling.

## Positive aspects

- Strong dark-theme visual identity.
- Clear top-level page title and system health indicator.
- Visible labels on native form controls.
- Keyboard-focusable buttons and tabs exist.
- Status copy generally does not rely on color alone.
- Empty and unavailable states are present in several tabs.

## Recommended redesign direction

Use a progressive-disclosure “Routing Studio” with:

1. Objective-first policy builder.
2. Role contracts as the primary object.
3. A visible deterministic decision pipeline.
4. Draft/live policy state.
5. Scenario-based preview with candidate evidence.
6. Evidence and canary promotion as the default next step.
7. Responsive navigation that collapses to a drawer or bottom bar.
