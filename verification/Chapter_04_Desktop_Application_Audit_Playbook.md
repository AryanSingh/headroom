# Chapter 4 -- Desktop Application Audit Playbook

## Objective

Verify that the desktop application is reliable, secure, intuitive, and
functionally consistent with the CLI, APIs, and dashboard.

## Scope

Audit:

-   Installation and upgrades
-   First launch
-   Authentication
-   Enterprise licensing
-   Window management
-   Navigation
-   Settings
-   Provider configuration
-   Model configuration
-   Background services
-   Notifications
-   Updates
-   Crash recovery
-   Offline behavior
-   IPC (if applicable)
-   Accessibility
-   Performance

## Installation & Upgrade

Verify:

-   Clean installation
-   Upgrade from previous version
-   Downgrade handling
-   Corrupt installation recovery
-   Uninstall and cleanup
-   User data preservation

## Startup

Measure:

-   Cold start
-   Warm start
-   Splash/loading behavior
-   Startup errors
-   Missing dependencies
-   Automatic recovery

## Authentication

Test:

-   First login
-   Existing session
-   Session expiration
-   Logout/login
-   Invalid credentials
-   Multiple accounts
-   Enterprise accounts

Verify secure credential storage.

## Enterprise Verification

Using the installed Minted Enterprise license verify:

-   License detection
-   Feature availability
-   Gated UI
-   Backend enforcement
-   Persistence after restart
-   Graceful behavior when entitlement changes

## Navigation

Open every:

-   Window
-   Dialog
-   Modal
-   Tab
-   Wizard
-   Settings page
-   Context menu

Verify:

-   Navigation consistency
-   Deep links
-   Keyboard navigation
-   Back/forward behavior
-   Focus management

## Settings & Configuration

Verify:

-   Provider setup
-   Model selection
-   Routing rules
-   Import/export
-   Reset to defaults
-   Invalid values
-   Persistence across restart

## Functional Workflows

Execute realistic workflows:

1.  Configure providers
2.  Create a session
3.  Run a multi-step task
4.  Switch providers
5.  Restart application
6.  Resume work
7.  Replay session
8.  Change enterprise settings
9.  Verify synchronization with CLI/dashboard

## IPC & Background Services

If applicable verify:

-   IPC security
-   Request validation
-   Error propagation
-   Background workers
-   Scheduled tasks
-   Notifications

## Reliability

Test:

-   Application restart
-   Crash recovery
-   Power interruption (where safe)
-   Network loss
-   Provider outage
-   Invalid configuration
-   Duplicate actions
-   Long-running sessions

## Accessibility

Review:

-   Keyboard-only usage
-   Focus order
-   Screen reader compatibility
-   Contrast
-   Scaling
-   High DPI
-   Reduced motion
-   Large text

## Performance

Measure:

-   Startup time
-   Memory usage
-   CPU usage
-   Large project handling
-   UI responsiveness
-   Search latency
-   Window rendering

## Cross-Surface Consistency

Verify:

-   Dashboard changes appear in Desktop
-   Desktop changes affect CLI where expected
-   Configuration remains synchronized
-   Enterprise permissions are consistent
-   Routing behaves identically

## Evidence

Capture:

-   Screenshots
-   Screen recordings (when helpful)
-   Logs
-   Crash reports
-   Console output
-   API traces
-   Reproduction steps

## Deliverables

1.  Installation report
2.  Authentication report
3.  Enterprise verification report
4.  Desktop workflow report
5.  Accessibility review
6.  Performance observations
7.  Desktop defect register
8.  Evidence index

## Exit Criteria

Desktop audit is complete only when:

-   Every desktop workflow has been exercised.
-   Every settings screen has been verified.
-   Enterprise features have been tested.
-   Cross-surface consistency has been confirmed.
-   Critical workflows succeed with real execution.
