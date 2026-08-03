# Chapter 5 -- Dashboard & UI Audit Playbook

## Objective

Audit every dashboard surface to ensure it is functional, intuitive,
accessible, consistent, and commercially polished. Rendering alone is
not sufficient---every interactive element must produce the expected
backend behaviour.

## Scope

Review all:

-   Dashboard routes
-   Navigation menus
-   Tabs
-   Cards
-   Tables
-   Forms
-   Dialogs
-   Wizards
-   Search
-   Filters
-   Bulk actions
-   Settings pages
-   Analytics views
-   Enterprise-only screens
-   Empty, loading, success and error states

## UI Inventory

Create a complete inventory before testing.

  Screen   Route   Owner   Priority   Tested   Evidence
  -------- ------- ------- ---------- -------- ----------

## Navigation

Verify:

-   Primary navigation
-   Secondary navigation
-   Breadcrumbs
-   Deep links
-   Browser back/forward
-   Refresh
-   Direct URL access
-   Unauthorized access handling

## Forms

For every form test:

-   Required fields
-   Optional fields
-   Validation
-   Invalid values
-   Large values
-   Unicode
-   Keyboard-only submission
-   Save
-   Cancel
-   Reset
-   Unsaved changes warning
-   Duplicate submission prevention

## Tables

Verify:

-   Sorting
-   Filtering
-   Pagination
-   Column resize/reorder (if supported)
-   Bulk actions
-   Selection persistence
-   Export
-   Empty state
-   Large datasets
-   Performance

## Interactive Controls

Exercise every:

-   Button
-   Toggle
-   Checkbox
-   Radio button
-   Dropdown
-   Context menu
-   Tooltip
-   Date picker
-   Slider
-   File upload
-   Copy action

Confirm:

-   UI response
-   API request
-   Backend state change
-   Persistence after refresh
-   Persistence after restart (where applicable)

## Workflow Testing

Validate complete user journeys:

1.  Onboarding
2.  Authentication
3.  Provider setup
4.  Enterprise setup
5.  Core feature execution
6.  Error recovery
7.  Import/export
8.  Session resume
9.  Administrative workflows

## Accessibility

Review:

-   Keyboard navigation
-   Focus order
-   Focus visibility
-   ARIA labels
-   Screen reader support
-   Contrast
-   Responsive layout
-   High DPI
-   Zoom (200%)
-   Reduced motion

## Visual Quality

Inspect for:

-   Misalignment
-   Overflow
-   Layout shifts
-   Truncated text
-   Broken icons
-   Incorrect spacing
-   Inconsistent typography
-   Theme issues
-   Loading flicker

## API Correlation

For significant UI actions verify:

-   Correct endpoint
-   Payload
-   Response
-   Error handling
-   Retry behaviour
-   Optimistic updates
-   Rollback on failure

## UX Review

Evaluate:

-   Discoverability
-   Information architecture
-   Terminology
-   Defaults
-   Feedback
-   Learnability
-   Enterprise usability
-   Overall commercial polish

Separate correctness defects from UX improvements.

## Evidence

Capture:

-   Screenshots
-   Network traces
-   Console logs
-   API payloads
-   Reproduction steps
-   Before/after comparisons where relevant

## Deliverables

1.  Screen inventory
2.  UI coverage matrix
3.  Accessibility report
4.  UX improvement report
5.  API correlation report
6.  Visual defect register
7.  Functional defect register
8.  Evidence index

## Exit Criteria

Dashboard audit is complete only when:

-   Every discovered screen has been opened.
-   Every interactive control has been exercised.
-   Backend effects have been verified.
-   Accessibility review is complete.
-   Major workflows succeed end-to-end.
-   Critical and High findings include reproducible evidence.
