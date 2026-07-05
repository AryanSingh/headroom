# Manual QA Audit Playbook

**Enterprise-Grade Quality Assurance Handbook for Commercial Product Releases**

---

## Introduction

This playbook provides a comprehensive, step-by-step methodology for conducting exhaustive manual quality assurance audits. It is designed for QA engineers, product teams, and release managers who need to verify product readiness before commercial launches.

### How to Use This Playbook

This document is organized into 22 sections that build a complete QA testing framework:

- **Sections 1-3:** Preparation and philosophy (mindset, environment, test data)
- **Sections 4-6:** Inventory and discovery (surfaces, flows, visual elements)
- **Sections 7-11:** Core QA dimensions (UX, functional, accessibility, security, performance)
- **Sections 12-16:** Platform and integration testing (browsers, mobile, offline, integrations)
- **Sections 17-20:** Specialized and release gates (AI, commercial checklist, standards, exit criteria)
- **Sections 21-22:** Resources and deliverables

### Execution Approach

This playbook is designed for **independent execution**. A qualified QA engineer should be able to:

1. Read this document start-to-finish before any testing
2. Set up the required environment (Section 2)
3. Prepare test data (Section 3)
4. Execute systematic inventories (Sections 4-5)
5. Run through all 11 quality dimensions (Sections 6-16)
6. Document findings using the standards in Section 19
7. Apply exit criteria (Section 20) to determine release readiness

### Estimated Effort

Executing this playbook thoroughly requires:

- **Preparation:** 2-4 hours (environment setup, test data creation)
- **Inventory and Discovery:** 4-6 hours (surfaces, flows, visual baseline)
- **Core QA Dimensions:** 8-12 hours (UX, functional, accessibility, security, performance)
- **Platform Testing:** 6-10 hours (browsers, mobile, integrations)
- **Specialized Testing:** 4-6 hours (AI workflows, error recovery, offline)
- **Documentation and Sign-off:** 2-4 hours

**Total: 26-42 hours for a comprehensive commercial release audit**

### Quality Assurance Team Roles

Recommended staffing for a commercial release:

| Role | Responsibility | Hours |
|------|-----------------|-------|
| QA Lead | Overall coordination, exit criteria evaluation, sign-off | 6-8h |
| QA Engineer (Core) | UX, functional, visual, cross-browser testing | 12-16h |
| QA Engineer (Platform) | Mobile, accessibility, offline, integration testing | 12-16h |
| Security Reviewer | Security QA, permission testing, data exposure | 4-6h |
| Product Manager (optional) | UX validation, flow verification, acceptance criteria | 4-6h |

---

## 1. QA Philosophy: Why Manual Testing Matters

Automated testing provides coverage and speed, but it operates within predefined assertions. Manual QA provides judgment, discovery, and validation of the holistic user experience.

### The Limits of Automation

Automated tests verify that code behaves as written. They cannot detect:

- **UX issues:** Confusing navigation, unclear labels, poor task flow
- **Visual problems:** Misaligned elements, inconsistent spacing, color contrast issues
- **Subtle performance issues:** Janky scrolling, sluggish interactions, delayed feedback
- **Accessibility gaps:** Screen reader navigation, keyboard discoverability, focus management
- **Human perception:** Whether something feels polished, professional, or trustworthy
- **Real-world edge cases:** Behavior with slow networks, unusual data, concurrent user actions
- **Inconsistency:** Mismatched behaviors across similar features or flows
- **Polish and delight:** Whether the product feels premium or rough

### The Human Judgment Layer

Manual QA applies expert judgment across three dimensions:

- **Product thinking:** Understanding what users are trying to accomplish and whether the product enables that
- **Quality standards:** Recognizing when something doesn't meet the bar for a commercial product
- **User empathy:** Simulating how real users will interact with the product, including mistakes, edge cases, and frustration points

### The QA Mindset

Effective QA engineers adopt these principles:

- **Assume nothing:** Test every visible feature and flow, even if it seems simple
- **Think like a user:** Use the product as a customer would, not as a developer
- **Search for inconsistency:** Two similar features should work the same way; if they don't, something is wrong
- **Stress test workflows:** Try unusual data, rapid interactions, interruptions, and recovery scenarios
- **Verify completeness:** Check that all promised features are present and functional
- **Evaluate fit and finish:** Consider whether the product feels polished and trustworthy
- **Document everything:** Record findings with precision so developers can reproduce and fix issues
- **Focus on impact:** Prioritize issues that affect users over edge cases with minimal real-world occurrence

### Quality Dimensions

Manual QA evaluates quality across multiple dimensions that automated tests cannot fully cover:

| Dimension | Definition | Examples |
|-----------|-----------|----------|
| Functional Correctness | Features work as intended; business logic is sound | Calculations accurate, data persists, workflows complete |
| UX Quality | Interface guides users intuitively; tasks are easy to complete | Clear labels, logical flow, discoverable features |
| Visual Polish | Appearance is professional, consistent, and attention-grabbing | Alignment, spacing, typography, color harmony |
| Performance Perception | Product feels fast and responsive even if technical speed is adequate | Smooth scrolling, quick feedback, progress indication |
| Accessibility | All users can access and use the product | Keyboard navigation, screen reader support, color contrast |
| Reliability | Product recovers gracefully from errors and edge cases | Error messages, data recovery, state management |
| Security | User data and operations are protected | Authorization enforcement, data encryption, input validation |
| Consistency | Similar features behave the same way across the product | Modal behaviors, button styles, data display formats |

---

## 2. Required Environment Setup

Before any testing begins, establish a complete testing environment with every system, tool, and configuration required for comprehensive manual QA.

### Operating Systems

- macOS (latest stable version + one prior major version)
- Windows 10 or Windows 11
- Linux (Ubuntu LTS or equivalent)

### Browsers and Versions

**Desktop Browsers:** Test on latest stable and one prior major version

- Google Chrome / Chromium (latest + N-1)
- Mozilla Firefox (latest + N-1)
- Apple Safari (latest + N-1, macOS only)
- Microsoft Edge (latest + N-1)

**Mobile Browsers:** Native mobile testing required

- iOS Safari (iOS 15+)
- Chrome on Android (latest + N-1)
- Samsung Internet (latest)

### Devices

- Desktop computer (minimum 2560x1440 resolution)
- Laptop (13–15 inch, typical 1080p or 1440p)
- Tablet (iPad, Android tablet, both portrait and landscape)
- Smartphone (iPhone latest, Android latest, both orientations)

### Screen Sizes to Test

| Category | Resolution | Device Type |
|----------|-----------|------------|
| 4K | 3840×2160, 2560×1600 (5K iMac) | Desktop |
| 2K | 2560×1440 | Desktop/Laptop |
| 1440p | 2560×1440 (laptop scaled) | Laptop |
| 1080p | 1920×1080, 1366×768 | Laptop, older desktop |
| Ultrawide | 3440×1440, 5120×1440 | Specialized monitor |
| Tablet (landscape) | 1024×768 to 2048×1536 | iPad, Android tablet |
| Tablet (portrait) | 768×1024 to 1536×2048 | iPad, Android tablet |
| Mobile (landscape) | 568×320 to 896×414 | iPhone, Android phone |
| Mobile (portrait) | 320×568 to 414×896 | iPhone, Android phone |

### Network Conditions

Test under various scenarios using browser DevTools throttling:

- **Fast:** Fiber/broadband (10+ Mbps)
- **Typical:** 4G LTE (~4 Mbps download)
- **Slow:** 3G (~1.5 Mbps)
- **Very Slow:** Edge/2G (~0.4 Mbps)
- **High Latency:** 500ms+ latency with fast speeds
- **Offline:** Complete network disconnection

### Test Accounts and Credentials

Prepare accounts covering all permission levels and states:

- Administrator account (full system access)
- Standard user account (normal permissions)
- Read-only account (view-only access)
- Guest account (if applicable)
- Trial account (limited features/duration)
- Expired/deactivated account
- Enterprise account (team/org level)
- Account with unusual characters in username/email
- Account with international characters (unicode)

### Feature Flags and Configuration

- All feature flags enabled
- All feature flags disabled
- Feature flags in mixed states (subset enabled)
- Beta features enabled/disabled
- Experimental features toggled
- Dark mode and light mode
- Different language configurations
- Different locale/timezone settings

### Required Developer Tools and Extensions

- **Browser DevTools:** (native, all browsers)
- **axe DevTools:** Accessibility auditing
- **WAVE:** WebAIM evaluation tool
- **Lighthouse:** Performance, accessibility, best practices
- **Accessibility Insights:** Microsoft comprehensive testing
- **Color Contrast Analyzer:** Verify color contrast
- **Pixel Perfect:** Visual alignment checking
- **Tag Assistant:** Google, for tracking/analytics validation
- **uBlock Origin:** Test with content blocking

### Testing Tools

- Playwright (for automated scenario recording)
- Bruno or Postman (API testing)
- Charles Proxy or Proxyman (network inspection)
- Screenshot tools (built-in OS tools, CleanShot, etc.)
- Screen recording (ScreenFlow, OBS, Camtasia)
- Figma (design comparison)
- NotePad/OneNote (issue documentation)

### Environment Validation Checklist

Before starting QA, verify:

- [ ] All required browsers installed and updated to latest versions
- [ ] Extensions installed and functional (axe, WAVE, Lighthouse, etc.)
- [ ] Test accounts created with proper permissions
- [ ] Test data loaded into staging environment
- [ ] Network inspection tools configured and working
- [ ] Screenshot/recording tools tested
- [ ] OAuth integrations working (can sign in successfully)
- [ ] Third-party services accessible (email, SMS, webhooks)
- [ ] Error tracking dashboard accessible
- [ ] Application logs visible and filterable
- [ ] Staging environment mirrors production configuration
- [ ] VPN configured (if required)
- [ ] Performance/monitoring tools have baseline data

---

## 3. Test Data Matrix

Comprehensive test data is essential for uncovering edge cases and boundary condition bugs.

### Data Validity Spectrum

| Category | Examples | Test Approach |
|----------|----------|----------------|
| Valid Data | Correct formats, appropriate values, expected ranges | Verify normal acceptance and processing |
| Boundary Values | Min/max values, empty strings, zero, very large numbers | Test at edge limits |
| Invalid Data | Wrong format, out-of-range, negative where impossible | Verify proper rejection and error messaging |
| Null/Empty | NULL values, empty strings, missing required fields | Verify required field validation |
| Duplicate Data | Duplicate entries, duplicate keys, duplicate IDs | Verify deduplication and conflict handling |
| Corrupted Data | Malformed JSON, truncated files, encoding issues | Verify graceful error handling |

### Text Data to Test

- Normal ASCII text (letters, numbers, punctuation)
- Minimum length (single character)
- Maximum length (field limit + 1 character)
- Empty strings
- Whitespace only (spaces, tabs, newlines)
- Special characters (!@#$%^&*)
- HTML tags (<script>, <img>, etc.)
- SQL injection attempts ('; DROP TABLE--)
- Unicode characters (é, ñ, ü, etc.)
- Emoji (😀, 🚀, etc.)
- Right-to-left text (Arabic, Hebrew)
- Mixed direction text
- Zero-width characters
- Very long strings (10,000+ characters)
- Line breaks and paragraph breaks

### Numeric Data to Test

- Zero (0)
- One (1)
- Negative numbers (-1, -100)
- Very large numbers (999999999999)
- Decimal/floating-point values (1.5, 3.14159)
- Very small decimals (0.0001)
- Percentages (0%, 50%, 100%, 150%)
- Numbers with leading zeros (007)
- Scientific notation (1e5, 2.5e-3)
- Infinity and NaN (if applicable)
- Hexadecimal (0xFF, 0x10)

### Date/Time Data to Test

- Current date/time
- Past dates (1970, historical dates)
- Future dates (2099)
- Leap year dates (Feb 29)
- Daylight saving time boundaries
- Timezone edge cases (UTC±11:00, etc.)
- Different date formats (MM/DD/YYYY, DD/MM/YYYY, ISO 8601)
- Time with and without seconds
- Midnight (00:00:00)
- 11:59:59 PM (23:59:59)
- Invalid dates (Feb 30, April 31)

### File Data to Test

- Images: PNG, JPG, GIF, WebP (various dimensions)
- Very large images (4K, 8K)
- Very small images (1x1 pixel)
- Images with unusual aspect ratios (1:10, 10:1)
- Transparent/alpha channel images
- Corrupted image files
- Documents: PDF, Word, Excel, CSV
- Large documents (>100 MB)
- Empty files (0 bytes)
- Extremely large files (1 GB+)
- Files with unusual names (spaces, special chars, unicode)
- Files with double extensions (.pdf.txt)
- Files with no extension
- Compressed files (ZIP, RAR, 7Z)
- Executable files (if applicable)

### Permissions and Access Data

- Admin/owner permissions
- Editor permissions
- Viewer/read-only permissions
- Guest access
- Expired permissions
- No permissions (access denied)
- Mixed team permissions
- Organization-level vs. individual permissions
- Inherited permissions
- Conflicting permissions

### International and Localization Data

- English (US, UK, AU)
- European languages (French, German, Spanish, Portuguese)
- Asian languages (Chinese, Japanese, Korean)
- Right-to-left languages (Arabic, Hebrew)
- Languages with special characters (ç, ñ, ü)
- Mixed-language content
- Different number formats (1,000.00 vs. 1.000,00)
- Different currency symbols ($ € £ ¥)
- Different time zones (UTC, EST, PST, JST, etc.)
- Different date formats

---

## 4. Complete Surface Inventory

Before testing functionality, create a complete visual inventory of every surface in the application to ensure no UI element is overlooked.

### How to Inventory All Surfaces

1. **Start from the entry point:** Home page, login screen, or dashboard
2. **Navigate every path:** Follow all navigation menus, links, and buttons
3. **Document each surface:** Screenshot and name each unique screen/page
4. **Trigger all states:** Visit each page with data, without data, with errors, loading, etc.
5. **Access every dialog/modal:** Open every popup, modal, drawer, and overlay
6. **Review all forms:** Document every input field type and validation state
7. **Check all states:** Empty, loading, success, error, disabled, focused, hovered
8. **Export the inventory:** Create a master list with screenshots

### Surfaces to Document

| Surface Type | What to Check | Screenshot |
|--------------|---------------|-----------|
| Landing Page | Hero, CTA, navigation, footer | ☐ |
| Marketing Pages | Features, pricing, about, help | ☐ |
| Dashboard | Widgets, charts, data summary | ☐ |
| Sidebar Navigation | Menu items, active states, icons | ☐ |
| Header/Topbar | Logo, notifications, user menu, search | ☐ |
| Forms | All input types, validation states | ☐ |
| Tables/Lists | Headers, rows, pagination, empty states | ☐ |
| Cards | All variations, actions, interactive states | ☐ |
| Dialogs/Modals | Header, content, actions, close button | ☐ |
| Dropdowns | Open/closed states, scrolling, selection | ☐ |
| Tooltips | Content, positioning, dismissal | ☐ |
| Notifications | Toast, banner, error, success, warning states | ☐ |
| Loading States | Spinners, skeletons, progress bars | ☐ |
| Empty States | No results, no data, first use | ☐ |
| Error Pages | 404, 500, permission denied, offline | ☐ |
| Settings Pages | Preferences, account, security, integrations | ☐ |
| Profile Page | User info, avatar, settings link | ☐ |
| Help/Documentation | FAQ, tutorials, support contact | ☐ |
| Footer | Links, copyright, social, company info | ☐ |

---

## 5. Flow Inventory: User Journey Mapping

Identify and document every key user workflow in the application to ensure comprehensive functional testing.

### Critical User Flows to Test

- **Onboarding:** Sign up → email verification → profile setup → first action
- **Authentication:** Login → password reset → two-factor auth → logout
- **Core Feature A:** Create → Read → Update → Delete (CRUD)
- **Core Feature B:** Browse → Filter → Search → View details
- **Data Sharing:** Invite → grant permissions → revoke access
- **Billing:** Subscribe → change plan → invoice → cancel
- **Settings:** Change preferences → save → verify changes apply
- **Integration:** Connect service → authorize → test → disconnect
- **Export:** Select data → format → export → verify file
- **Import:** Select file → map fields → validate → import
- **Notification Opt-in:** Enable → receive → disable → verify
- **Error Recovery:** Encounter error → retry → recover state

### Flow Variation Matrix

For each flow, test these variations:

| Variation | Scenario | Test |
|-----------|----------|------|
| Happy Path | Everything works normally | ✓ Basic functionality works |
| Missing Data | Required fields empty | ✓ Validation prevents submission |
| Invalid Data | Wrong format or out of range | ✓ Error message is clear |
| Duplicate Action | Perform action twice in succession | ✓ Handled gracefully (no double-submit) |
| Browser Back | Use browser back button mid-flow | ✓ State preserved or gracefully handled |
| Network Interruption | Network fails during submission | ✓ User can retry |
| Session Timeout | Session expires during flow | ✓ Redirected to login, can resume |
| Permission Denied | User lacks required permissions | ✓ Clear access denied message |

---

## 6. Visual QA Checklist: Pixel-Perfect Review

Visual QA ensures the application looks professional, consistent, and polished.

### Alignment and Spacing

- [ ] Elements aligned to visual grid (8px, 12px, or project standard)
- [ ] Consistent left/right padding across similar components
- [ ] Consistent top/bottom spacing between sections
- [ ] No random or off-by-one pixel gaps
- [ ] Proper alignment with responsive breakpoints
- [ ] Elements not clipping or overlapping unexpectedly
- [ ] Spacing scales proportionally on different screen sizes

### Typography

- [ ] Consistent font family throughout (no random fallbacks visible)
- [ ] Font sizes follow documented type scale
- [ ] Font weights appropriate for hierarchy (bold for headings, regular for body)
- [ ] Line height is readable (1.4-1.8 for body text)
- [ ] Letter spacing is consistent
- [ ] Text rendering is smooth (no blurriness on retina)
- [ ] Links are clearly distinguished (color, underline, hover state)
- [ ] Disabled text has appropriate styling (grayed out)
- [ ] All caps text has appropriate letter spacing
- [ ] Text doesn't get cut off or overflow unexpectedly

### Color and Contrast

- [ ] Colors match design specifications (use color picker to verify hex)
- [ ] Contrast ratio meets WCAG AA standard (4.5:1 for body text, 3:1 for large text)
- [ ] Color palette is consistent and intentional (no random colors)
- [ ] Gradients are smooth and don't have banding
- [ ] Dark mode has proper contrast (light text on dark backgrounds)
- [ ] Light mode has proper contrast (dark text on light backgrounds)
- [ ] Status colors are distinguishable (not relying on color alone for meaning)
- [ ] No pure black (#000000) or pure white (#FFFFFF) unless intentional

### Icons and Images

- [ ] All icons are crisp and properly sized
- [ ] Icons are consistent in style and weight
- [ ] Images have no artifacts, compression noise, or pixelation
- [ ] Missing images show placeholder or alt text appropriately
- [ ] Images scale proportionally without distortion
- [ ] Broken image indicators are not visible to users
- [ ] SVG icons render crisply at all zoom levels
- [ ] Image backgrounds are transparent where needed

### Interactive Element States

- [ ] **Hover state:** Buttons, links, cards change appearance on hover
- [ ] **Focus state:** Keyboard focus is clearly visible (outline or highlight)
- [ ] **Active state:** Currently active nav item or selected item is visually distinct
- [ ] **Disabled state:** Disabled buttons/inputs are clearly not interactive (grayed out)
- [ ] **Loading state:** Loading indicator is visible and animated
- [ ] **Error state:** Error message is visible with appropriate styling
- [ ] **Success state:** Success message is visible with appropriate styling

### Animations and Transitions

- [ ] Transitions are smooth (not stuttering or jumpy)
- [ ] Animation duration is appropriate (not too fast, not sluggish)
- [ ] Animations are purposeful (draw attention, don't distract)
- [ ] Loading animations are clear and not confusing
- [ ] Page transitions are smooth without flash of unstyled content
- [ ] Modal/dialog entrance and exit animations are smooth
- [ ] Scroll animations don't cause janky scrolling
- [ ] Animations respect prefers-reduced-motion setting

### Responsive Behavior

- [ ] Layout reflows correctly at all breakpoints
- [ ] No horizontal scrolling on mobile (unless intentional)
- [ ] Text is readable at mobile sizes
- [ ] Touch targets are at least 44x44 pixels on mobile
- [ ] Navigation is accessible on mobile (drawer, hamburger, etc.)
- [ ] Modals work on small screens
- [ ] Tables have mobile-friendly layout (stacked or scrollable)
- [ ] Form inputs are appropriately sized for mobile keyboards

### Consistency Across Pages

- [ ] Button styles are consistent (primary, secondary, danger colors match)
- [ ] Form input styles are consistent
- [ ] Card styles are consistent
- [ ] Modal styles are consistent
- [ ] Spacing patterns are consistent
- [ ] Typography hierarchy is consistent
- [ ] Color usage is consistent across pages
- [ ] Icon styles match across pages

### Dark Mode / Light Mode

- [ ] Colors are adjusted appropriately for dark mode
- [ ] Text contrast is maintained in dark mode
- [ ] Images look good in both themes (no weird color casts)
- [ ] Gradients work in both themes
- [ ] No pure white text on light backgrounds or vice versa
- [ ] Icons and logos display correctly in both themes
- [ ] Accent colors work in both themes
- [ ] Switch between themes works smoothly (no flash)

### Polish and Premium Feel

- [ ] No visible browser defaults (form inputs styled, radios/checkboxes custom)
- [ ] Shadows are subtle and appropriate depth
- [ ] Borders are consistent weight and color
- [ ] Whitespace feels intentional, not accidentally empty
- [ ] Micro-interactions feel delightful (smooth feedback)
- [ ] Overall visual hierarchy guides user attention appropriately
- [ ] No jarring visual changes between states
- [ ] Product feels cohesive and intentionally designed

---

## 7. UX Audit: Usability and User Experience

Beyond functionality, evaluate whether the product is intuitive, learnable, and delightful to use.

### Ease of Use

- [ ] First-time users can complete primary task without help
- [ ] Navigation is intuitive (menus, buttons, links make sense)
- [ ] Workflow steps are in logical order
- [ ] No confusing or redundant steps
- [ ] Advanced features don't interfere with basic usage
- [ ] Can complete task in minimum steps

### Clarity and Labels

- [ ] All buttons clearly describe their action ("Save" not "OK")
- [ ] Form field labels are clear and specific
- [ ] Help text explains non-obvious fields
- [ ] Error messages explain what went wrong and how to fix it
- [ ] Success messages confirm the action completed
- [ ] Modal titles clearly state the purpose
- [ ] No unclear abbreviations or acronyms
- [ ] Language is user-friendly, not technical

### Feedback and Confirmation

- [ ] User actions receive immediate feedback (hover, click, focus)
- [ ] Form submissions show loading state
- [ ] Success is confirmed (toast, modal, visual change)
- [ ] Errors are clearly communicated
- [ ] Destructive actions require confirmation (delete, logout, etc.)
- [ ] Users know whether action succeeded or failed
- [ ] No silent failures or unclear states

### Undo and Recovery

- [ ] Destructive actions have undo (if feasible)
- [ ] Deleted items can be recovered (trash/recovery window)
- [ ] Form data is preserved if navigation interrupted
- [ ] Can recover from errors without re-entering data
- [ ] Browser back button works intuitively
- [ ] Session timeout allows data recovery

### Consistency

- [ ] Similar actions work the same way across the product
- [ ] Buttons with same appearance have same function
- [ ] Terminology is consistent (don't call it "add" in one place and "create" in another)
- [ ] Icons represent actions consistently
- [ ] Workflows follow same patterns
- [ ] Navigation structure is consistent across pages

### Discoverability

- [ ] Core features are visible without searching
- [ ] Advanced features are easy to find
- [ ] Settings are organized logically
- [ ] No hidden features or "secret" clicks
- [ ] Search works when looking for functionality
- [ ] Help is readily available
- [ ] Feature announcements are visible

### Performance Perception

- [ ] Application feels fast even if backend is slow
- [ ] Loading states are visible and reassuring
- [ ] Progress is communicated during long operations
- [ ] No apparent lag between click and response
- [ ] Pagination/infinite scroll loads smoothly
- [ ] Search results appear quickly
- [ ] No stuck or frozen feeling states

### Trust and Confidence

- [ ] Product appears secure (HTTPS, no warning signs)
- [ ] No broken links or 404 errors
- [ ] Data appears to be saved reliably
- [ ] Permissions work as expected
- [ ] Product doesn't feel abandoned (no outdated content)
- [ ] Error messages don't blame user
- [ ] No phishing-like or deceptive patterns

---

## 8. Functional QA: Feature-by-Feature Verification

Systematically verify that every feature works correctly under various conditions.

### Feature Test Case Template

```
Feature: [Feature Name]
Purpose: [What does this feature do?]

Test Case 1: Happy Path
  Preconditions: [Initial state]
  Steps:
    1. [Action 1]
    2. [Action 2]
  Expected Result: [What should happen?]
  ✓ Pass / ✗ Fail / ⚠ Blocked

Test Case 2: [Scenario Name]
  Preconditions: [Initial state]
  Steps: [Steps]
  Expected Result: [Outcome]
  ✓ Pass / ✗ Fail / ⚠ Blocked

Edge Cases: [List boundary conditions]
Regression Risk: [Impact if broken]
Evidence: [Screenshots/video]
```

### Functional Testing Dimensions

| Dimension | Test Cases | Focus |
|-----------|-----------|-------|
| CRUD Operations | Create, Read, Update, Delete complete | Data persists, no data loss |
| Search & Filter | Search exact, partial, wildcard; filter by all fields | Results accurate, performance acceptable |
| Validation | Required fields, format validation, ranges | Invalid data rejected, error messages clear |
| Permissions | Admin can do X, user cannot; various roles | Authorization enforced, no privilege escalation |
| Integrations | Third-party APIs, webhooks, data sync | Data flows correctly, errors handled |
| Calculations | Math, formulas, conversions are accurate | Rounding, precision correct |
| Data Display | Lists, tables, charts show correct data | Formatting, sorting, pagination correct |
| State Management | App state changes correctly as user acts | No stale data, no inconsistent states |

---

## 9. Accessibility Audit: WCAG 2.1 Compliance

Ensure the product is usable by all people, including those with disabilities. This audit follows WCAG 2.1 Level AA standards.

### Keyboard Navigation

- [ ] All interactive elements (buttons, links, inputs) are keyboard accessible
- [ ] Tab key navigates through interactive elements in logical order
- [ ] Tab order is visible (focus indicator visible on all elements)
- [ ] Can reach all features using only keyboard (no mouse required)
- [ ] Dropdown menus can be navigated with arrow keys
- [ ] Modal dialogs trap focus (tab doesn't escape modal)
- [ ] Skip navigation link present (link to main content)
- [ ] No keyboard traps (can't get stuck on any element)
- [ ] Can dismiss modals with Escape key

### Screen Reader Compatibility

- [ ] Semantic HTML used (button, nav, main, etc.)
- [ ] Form labels properly associated with inputs (for="" attribute)
- [ ] Images have alt text (descriptive, not "image")
- [ ] Decorative images have empty alt (alt="")
- [ ] Icons that convey meaning have labels or aria-labels
- [ ] Dynamic content updates announced to screen readers (aria-live)
- [ ] Error messages associated with form inputs
- [ ] Required fields marked (required attribute or aria-required)
- [ ] Headings use proper hierarchy (h1, h2, h3 in order)
- [ ] No important information conveyed by color alone

### Visual Accessibility

- [ ] Color contrast ratio at least 4.5:1 (WCAG AA) for body text
- [ ] Color contrast ratio at least 3:1 for large text (18pt+)
- [ ] Information not conveyed by color alone (use patterns, shapes, or text)
- [ ] Focus indicator visible and has sufficient contrast
- [ ] Text can be resized up to 200% without loss of functionality
- [ ] No content is lost when zoomed to 200%
- [ ] No fixed font sizes that prevent resizing
- [ ] No flashing content (no more than 3 flashes per second)

### Motion and Animation

- [ ] Animations respect prefers-reduced-motion setting
- [ ] No auto-playing videos with sound
- [ ] Animations can be paused/stopped
- [ ] No animation causes disorientation or seizure risk

### Forms and Input

- [ ] Form labels visible and associated with inputs
- [ ] Error messages linked to form fields
- [ ] Error suggestions provided (spell checker, allowed formats)
- [ ] Form can be submitted via keyboard (no drag-and-drop-only)
- [ ] Clear instructions for complex inputs
- [ ] Required fields clearly marked

### Testing Tools

Use these tools for automated accessibility scanning:

- **axe DevTools:** Automated accessibility testing (Chrome/Firefox)
- **WAVE:** WebAIM evaluation tool
- **Lighthouse:** Chrome built-in accessibility audit
- **Accessibility Insights:** Microsoft comprehensive tool
- **Color Contrast Analyzer:** Verify color contrast ratios
- **Screen Reader:** NVDA (free, Windows), JAWS (paid, Windows), VoiceOver (Mac/iOS)

---

## 10. Security QA: Manual Security Testing

Verify that sensitive data is protected and the application follows security best practices.

### Authentication and Authorization

- [ ] Cannot access admin features without admin role
- [ ] Cannot view other users' data (isolated by user/org)
- [ ] Cannot view data from other organizations
- [ ] Session expires after inactivity period
- [ ] Logging out properly clears session
- [ ] Cannot use expired tokens to make requests
- [ ] API keys/tokens are never visible in plain text
- [ ] Password reset token has expiration
- [ ] Password requirements are enforced
- [ ] Account lockout after N failed login attempts

### Data Protection

- [ ] All communication uses HTTPS (not HTTP)
- [ ] No sensitive data in URLs (passwords, tokens, PII)
- [ ] Passwords not shown in plaintext (masked input)
- [ ] Sensitive data (tokens, API keys) hidden in UI
- [ ] No sensitive data in console logs
- [ ] No sensitive data in error messages shown to users
- [ ] No sensitive data in browser history
- [ ] No sensitive data in autocomplete suggestions
- [ ] Deleted data is actually deleted (not just hidden)
- [ ] Data cannot be accessed via direct URL manipulation

### Input Validation

- [ ] HTML injection attempts are escaped or removed
- [ ] Script injection (<script> tags) is handled safely
- [ ] SQL injection attempts are safe (parameterized queries)
- [ ] File uploads validate file type and size
- [ ] File uploads don't execute arbitrary code
- [ ] User-provided content is sanitized before display
- [ ] API accepts only expected data types
- [ ] Large payloads are rejected with appropriate limits

### API Security

- [ ] API requires authentication (no public data leaks)
- [ ] Rate limiting prevents brute force and DoS
- [ ] CORS properly configured (not allowing *)
- [ ] API doesn't expose unnecessary data in responses
- [ ] API rejects invalid request methods (DELETE on GET endpoint, etc.)
- [ ] Error responses don't leak system information

### Session Security

- [ ] Session cookies have HttpOnly flag (not accessible via JS)
- [ ] Session cookies have Secure flag (HTTPS only)
- [ ] Session cookies have SameSite attribute (CSRF protection)
- [ ] Session IDs are not guessable
- [ ] Cannot fixate sessions (steal someone else's session)

---

## 11. Performance Perception: User Experience of Speed

Even if backend metrics are good, users perceive speed based on feedback, animations, and responsiveness.

### Perceived Performance Checklist

- [ ] Page is interactive quickly (not white screen for long)
- [ ] Loading state appears within 100ms of action
- [ ] Skeleton screens match final layout (no layout shift)
- [ ] Animations are smooth (60fps, no stuttering)
- [ ] Interactions have immediate visual feedback (<100ms)
- [ ] No cumulative layout shift (CLS) during page load
- [ ] Scrolling is smooth and responsive
- [ ] Modal opens instantly (no delay)
- [ ] Dropdown opens without noticeable lag
- [ ] Search results appear quickly (sub-second)
- [ ] Form submission feels instantaneous (even if backend is slow, show loading)
- [ ] Navigation between pages feels fast

### Core Web Vitals (Lighthouse)

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| Largest Contentful Paint (LCP) | < 2.5s | 2.5s - 4s | > 4s |
| First Input Delay (FID) / Interaction to Next Paint (INP) | < 100ms | 100ms - 300ms | > 300ms |
| Cumulative Layout Shift (CLS) | < 0.1 | 0.1 - 0.25 | > 0.25 |

### How to Test Perceived Performance

1. **Use Lighthouse:** Chrome DevTools → Lighthouse → Performance
2. **Throttle network:** Chrome DevTools → Network → Slow 4G
3. **Throttle CPU:** Chrome DevTools → Performance → Slow CPU
4. **Clear cache:** Simulate first-time visitor
5. **Monitor visuals:** Watch for jank, delays, layout shifts
6. **Use WebPageTest:** webpagetest.org for real-world conditions

---

## 12. Cross-Browser Testing: Compatibility Matrix

Verify the application works consistently across different browsers and browser versions.

### Browsers to Test

| Browser | Latest Version | N-1 Version | OS | Status |
|---------|----------------|------------|-----|--------|
| Chrome | ✓ Latest | ✓ N-1 | Win/Mac/Linux | ☐ |
| Firefox | ✓ Latest | ✓ N-1 | Win/Mac/Linux | ☐ |
| Safari | ✓ Latest | ✓ N-1 | Mac | ☐ |
| Edge | ✓ Latest | ✓ N-1 | Win/Mac | ☐ |

### Cross-Browser Test Cases

- [ ] Layout renders correctly (no misalignment)
- [ ] CSS displays consistently (colors, spacing, fonts)
- [ ] JavaScript works (no console errors)
- [ ] Forms submit correctly
- [ ] API calls succeed
- [ ] Animations are smooth
- [ ] Images display correctly
- [ ] Videos play correctly (if applicable)
- [ ] SVG renders crisp
- [ ] Web fonts load and display
- [ ] LocalStorage/SessionStorage works
- [ ] Cookies are set and sent correctly
- [ ] No console errors or warnings
- [ ] Performance is acceptable

### Known Compatibility Issues to Check

- [ ] CSS Grid support in older browsers
- [ ] CSS variables (@property support)
- [ ] Fetch API (vs. older XMLHttpRequest)
- [ ] Promise/async-await syntax
- [ ] Optional chaining (?.) support
- [ ] ES6 module syntax
- [ ] Intersection Observer API
- [ ] ResizeObserver API
- [ ] Web Components support

---

## 13. Mobile QA: Touch, Gestures, and Mobile-Specific Issues

Mobile presents unique challenges: touch interactions, limited screen space, various browsers, and different networks.

### Mobile-Specific Test Cases

- [ ] Layout reflows correctly in portrait and landscape
- [ ] Text is readable without pinch-to-zoom
- [ ] Touch targets are at least 44x44 pixels
- [ ] No tiny buttons or close touch targets
- [ ] Double-tap zoom doesn't break layout
- [ ] Pinch-to-zoom works where appropriate
- [ ] Horizontal scrolling only for data tables (not content)
- [ ] Form inputs expand when focused (not hidden behind keyboard)
- [ ] Virtual keyboard doesn't cover submit button
- [ ] Mobile Safari notch doesn't cover important content
- [ ] Safe area respected (not behind home indicator)
- [ ] Status bar doesn't interfere with content

### Touch Interactions

- [ ] Tap registers on buttons and links (no 300ms delay)
- [ ] Swipe gestures work as expected (if implemented)
- [ ] Long press triggers correct action (if implemented)
- [ ] Pinch-to-zoom magnifies content correctly
- [ ] Scroll momentum feels natural (not too fast or slow)
- [ ] Rubber band effect on scroll edges (if applicable)
- [ ] Tap doesn't accidentally trigger adjacent buttons
- [ ] Touch feedback visible (highlight on press)

### Mobile Navigation

- [ ] Navigation accessible on mobile (drawer, hamburger, bottom nav)
- [ ] Navigation doesn't hide primary content
- [ ] Hamburger menu icon clear and findable
- [ ] Can close menu easily (tap outside, back button, X)
- [ ] Back button works intuitively
- [ ] No left/right swipe navigation conflicts with browser navigation
- [ ] Breadcrumbs visible and tappable (if present)

### Mobile Forms

- [ ] Form inputs are appropriately sized (not too small)
- [ ] Input type attribute is correct (tel, email, number, etc.)
- [ ] Correct keyboard appears (number pad for phone, email keyboard for email)
- [ ] Can easily tab between fields
- [ ] Form labels visible and not hidden by keyboard
- [ ] Error messages visible and not behind keyboard
- [ ] Submit button at bottom, not covered by keyboard
- [ ] Autocomplete suggestions helpful

### Mobile Networks

- [ ] Works on slow 4G connection (1.5 Mbps)
- [ ] Works on 3G connection (1 Mbps)
- [ ] Works offline (cached content available)
- [ ] Gracefully recovers from network interruption
- [ ] Loading states visible during slow load
- [ ] Images compressed for mobile (not loading desktop-sized images)
- [ ] Can resume long operations if connection drops

### Mobile Orientation Changes

- [ ] Layout adapts correctly when rotating device
- [ ] Content doesn't shift dramatically
- [ ] Form data preserved when rotating
- [ ] Scroll position preserved (or reasonable defaults)
- [ ] Modal/popup reflows on rotate
- [ ] Video/fullscreen content adapts

### iOS-Specific Testing

- [ ] Notch/safe area respected
- [ ] Home indicator doesn't cover content
- [ ] Address bar doesn't push content unexpectedly
- [ ] Safari web features work (Web Clips, etc.)
- [ ] VoiceOver screen reader works
- [ ] Haptic feedback (if implemented) works
- [ ] iOS 15+ features supported (if applicable)

### Android-Specific Testing

- [ ] Notch styles supported
- [ ] Gesture navigation compatible (if back/home gestures used)
- [ ] TalkBack screen reader works
- [ ] Haptic feedback works
- [ ] Dark mode adaptation works
- [ ] Chrome DevTools remote debugging works

---

## 14. Error Recovery: Intentional Failure Testing

Deliberately break things to verify the application recovers gracefully.

### Network Failure Scenarios

- [ ] Turn off WiFi/disable network during load
- [ ] Disconnect network mid-request (use Charles Proxy or DevTools throttling)
- [ ] Simulate slow network (Chrome DevTools: Slow 3G)
- [ ] Trigger timeout (request takes >30s)
- [ ] Reconnect after disconnect (verify data syncs)
- [ ] Verify error message is helpful (not "network error")
- [ ] Verify retry button present and works

### API Error Scenarios

- [ ] Mock 400 Bad Request (invalid input)
- [ ] Mock 401 Unauthorized (token expired)
- [ ] Mock 403 Forbidden (permission denied)
- [ ] Mock 404 Not Found (resource deleted)
- [ ] Mock 500 Server Error (backend failure)
- [ ] Mock 503 Service Unavailable (maintenance)
- [ ] Mock timeout (no response within timeout period)
- [ ] Mock malformed response (invalid JSON)
- [ ] Verify user can retry failed operation
- [ ] Verify data isn't lost on error

### Session and Auth Failures

- [ ] Simulate session timeout (clear cookies, reload)
- [ ] Simulate token expiration (edit JWT expiry)
- [ ] Simulate permission loss (user role removed)
- [ ] Simulate account deletion (user account removed)
- [ ] Simulate browser closing and reopening mid-session
- [ ] Verify redirect to login is smooth and preserves intent
- [ ] Verify can re-authenticate and continue

### Data Integrity Failures

- [ ] Simulate database connection loss (API still responds, DB fails)
- [ ] Simulate constraint violation (duplicate key, foreign key)
- [ ] Simulate race condition (submit form twice rapidly)
- [ ] Simulate concurrent edit (two users editing same item)
- [ ] Simulate corrupted data (invalid response)
- [ ] Verify data consistency after failures
- [ ] Verify no partial updates

### Browser-Level Failures

- [ ] Disable JavaScript (some features won't work, but basic nav should)
- [ ] Disable cookies (session may fail)
- [ ] Disable localStorage (cached data won't persist)
- [ ] Disable images (alt text should be readable)
- [ ] Disable CSS (page should still be readable)
- [ ] Disable Web Fonts (fallback fonts should work)
- [ ] Simulate out-of-memory (large datasets)
- [ ] Simulate storage quota exceeded (large files)

---

## 15. Offline Testing: Network Disconnection Scenarios

Modern applications should handle offline gracefully.

### Offline Functionality

- [ ] Cached content displays without network
- [ ] User can view previously loaded pages
- [ ] Forms can be filled out (even if submission fails)
- [ ] Local data is preserved (not lost)
- [ ] Offline indicator is visible to user
- [ ] Offline message is clear and helpful
- [ ] Can queue actions for sync when online

### Offline to Online Transition

- [ ] Detects when connection returns
- [ ] Syncs queued actions automatically
- [ ] Resolves conflicts (offline edits vs. server changes)
- [ ] Updates UI with fresh data
- [ ] No duplicate submissions
- [ ] User is notified of sync completion
- [ ] No data loss in sync process

### How to Test Offline

1. **Chrome DevTools:** Network tab → Offline checkbox
2. **Firefox DevTools:** Network tab → Offline mode
3. **System level:** Airplane mode, disconnect WiFi
4. **Charles Proxy:** Tools → Throttle Settings → No Network

---

## 16. Integration QA: Third-Party Services

Verify that integrations with external services work correctly and fail gracefully when unavailable.

### Integration Test Categories

| Integration | Test Cases | Failure Modes |
|-------------|-----------|---------------|
| OAuth (Google, GitHub, etc.) | Sign in, link account, unlink | OAuth provider down, user denies permission |
| Payment (Stripe, PayPal) | Checkout, payment processing, receipts | Payment declined, processor down, invalid card |
| Email | Send email, receive verification, digest | SMTP down, bounced email, spam filtering |
| SMS | Send SMS, verification codes, alerts | Service down, invalid number, rate limited |
| Analytics | Events tracked, data flows to dashboard | Script fails, data missing, latency |
| CDN | Static assets load quickly, images cached | CDN down, fallback to origin |
| Storage (AWS S3, GCP, etc.) | Upload, download, delete files | Quota exceeded, permissions error, timeout |
| API (third-party) | API calls succeed, data correct | API down, rate limited, invalid response |

### Integration Testing Checklist

- [ ] Service connection succeeds with valid credentials
- [ ] Service connection fails with invalid credentials (clear error)
- [ ] Data flows correctly to/from external service
- [ ] Can disconnect/revoke integration
- [ ] Data persists after reconnection
- [ ] Rate limiting is handled (retry logic)
- [ ] Service downtime doesn't crash application
- [ ] No API keys/secrets exposed in logs or UI
- [ ] Webhooks from external service are received and processed
- [ ] Webhook payloads are validated and sanitized

---

## 17. AI Workflow QA: Testing AI-Powered Features

If the application uses AI/ML features, these require specialized testing.

### Conversation Quality

- [ ] Responses are relevant to user input
- [ ] Responses are grammatically correct
- [ ] Responses maintain context across conversation
- [ ] Tone is appropriate (professional, friendly, etc.)
- [ ] No offensive or inappropriate content
- [ ] Handles follow-up questions correctly
- [ ] Indicates uncertainty when uncertain (not false confidence)

### Hallucinations and Accuracy

- [ ] Factual accuracy verified (especially for business-critical info)
- [ ] No made-up citations or references
- [ ] Hallucinations are minimized with appropriate prompting
- [ ] AI admits when it doesn't know (vs. guessing)
- [ ] Disclaimers present where appropriate

### Memory and Context

- [ ] Conversation history is maintained correctly
- [ ] Previous context is referenced appropriately
- [ ] Memory doesn't cause context confusion
- [ ] Long conversations don't degrade quality
- [ ] Memory can be cleared/reset
- [ ] Conversation history is privacy-protected

### Streaming and Cancellation

- [ ] Streaming responses appear progressively (not waiting for full response)
- [ ] User can cancel/stop response mid-stream
- [ ] Cancellation is clean (no partial messages left)
- [ ] Retry works after cancellation

### Tool Calling and Integration

- [ ] AI correctly calls appropriate tools/functions
- [ ] Tool outputs are correctly incorporated into response
- [ ] Tool failures don't crash AI (handled gracefully)
- [ ] Tool results are accurate and timely
- [ ] Multiple tools can be chained correctly

### Performance and Cost

- [ ] First response latency is acceptable (<5 seconds typically)
- [ ] Streaming latency is good (tokens appear quickly)
- [ ] Long conversations don't cause excessive latency
- [ ] Token usage is within expected bounds (cost controlled)
- [ ] Rate limiting and quotas are enforced

### Safety and Content Filtering

- [ ] Harmful requests are declined appropriately
- [ ] Jailbreak attempts are handled
- [ ] Content filtering is applied (no violence, hate speech, etc.)
- [ ] Privacy is respected (no sensitive data leaks)
- [ ] User input is sanitized before sending to AI

---

## 18. Commercial Release Checklist

Before the product goes live to customers, verify every element of commercial readiness.

### Product Completeness

- [ ] All promised features are implemented and working
- [ ] No placeholder text or TODOs visible
- [ ] All help documentation is complete and accurate
- [ ] Onboarding flow is complete
- [ ] Tutorial or guided tour works
- [ ] No debug code or debugging features exposed

### Performance and Scalability

- [ ] Page load time < 3 seconds on typical connection
- [ ] Core interactions < 100ms latency
- [ ] Database queries optimized (no N+1 queries)
- [ ] Can handle expected concurrent users
- [ ] Can handle expected data volume
- [ ] No memory leaks on long sessions
- [ ] Cache headers configured correctly

### Monitoring and Observability

- [ ] Error tracking service configured and working
- [ ] Performance monitoring in place
- [ ] User analytics configured and working
- [ ] Logs are flowing to aggregation service
- [ ] Alerts are configured for critical errors
- [ ] On-call rotation is in place
- [ ] Runbooks for common issues are documented

### Security and Compliance

- [ ] Security audit passed (or documented exceptions)
- [ ] HTTPS enforced site-wide
- [ ] No known security vulnerabilities
- [ ] Compliance requirements met (GDPR, HIPAA, etc.)
- [ ] Privacy policy is clear and accurate
- [ ] Terms of service are in place
- [ ] Data retention policies defined
- [ ] Backup and recovery procedures tested

### Infrastructure and Deployment

- [ ] Production environment is separate from staging
- [ ] Database is backed up regularly
- [ ] Backup restore has been tested
- [ ] Disaster recovery plan is documented
- [ ] Rollback procedure exists and is tested
- [ ] DNS is configured and propagated
- [ ] SSL certificate is valid and not expiring soon
- [ ] CDN is configured and caching correctly
- [ ] Load balancing is configured (if applicable)

### Accessibility Compliance

- [ ] WCAG 2.1 Level AA compliance verified
- [ ] Keyboard navigation works
- [ ] Screen reader support tested
- [ ] Color contrast meets standards
- [ ] No flashing content
- [ ] Accessibility statement published

### Browser Support

- [ ] All supported browsers verified working
- [ ] Supported browser list published (e.g., "Chrome 80+, Firefox 75+...")
- [ ] Graceful degradation for unsupported browsers
- [ ] No incompatibility warnings for supported versions

### Internationalization and Localization

- [ ] All UI text is properly translatable
- [ ] Translations are accurate and complete
- [ ] RTL languages render correctly (if supported)
- [ ] Date/time formats localized correctly
- [ ] Currency formatting correct for each locale
- [ ] No hardcoded strings in code

### Support Readiness

- [ ] Support documentation is complete
- [ ] FAQ covers common issues
- [ ] Contact method for support is clear
- [ ] Support team is trained on product
- [ ] Bug reporting process is documented
- [ ] Response time SLAs are defined
- [ ] Escalation procedures are in place

### Marketing and Communication

- [ ] Launch announcement is prepared
- [ ] Pricing is finalized and clearly communicated
- [ ] Feature list is accurate and complete
- [ ] Demo or trial access is available (if applicable)
- [ ] Video demos or tutorials are ready
- [ ] Social media posts are prepared
- [ ] Press release is drafted (if applicable)

---

## 19. Bug Reporting Standards

Effective bug reports enable quick fixes. Use this standard format for all defects.

### Bug Report Template

```
Title: [Brief, clear summary]
Severity: [Critical / High / Medium / Low]
Priority: [P0 / P1 / P2 / P3]

Environment:
- Browser: [Name and version]
- OS: [OS and version]
- Device: [Desktop / Mobile / Tablet]
- URL: [Affected page]
- Account: [Test account used]

Preconditions:
[What must be true before the bug occurs?]

Steps to Reproduce:
1. [Action 1]
2. [Action 2]
3. [Action 3]

Expected Result:
[What should happen]

Actual Result:
[What actually happened]

Evidence:
- Screenshot: [Attach screenshot]
- Video: [Attach video if complex]
- Console errors: [Copy any JS errors]
- Network errors: [Copy any API errors]

Additional Notes:
[Any other relevant information]

Regression Risk: [Impact if bug is NOT fixed]
Workaround: [Is there a workaround for users?]
```

### Severity Levels

| Severity | Definition | Example |
|----------|-----------|---------|
| Critical | Feature completely broken or data loss possible | Users cannot save work, data deleted unexpectedly |
| High | Feature severely broken or workaround difficult | Login fails for certain users, calculation is wrong |
| Medium | Feature has issues but workaround exists | Button misaligned, error message unclear, slow |
| Low | Minor cosmetic or UX issue | Typo, minor color issue, inconsistent spacing |

### Evidence Collection

Always include:

- **Screenshots:** Show the exact state when bug occurs
- **Videos:** For complex interactions, record the flow
- **Console logs:** Chrome DevTools → Console → Copy errors
- **Network errors:** Chrome DevTools → Network → Failed requests
- **Browser/system info:** OS, browser, version
- **Exact steps:** Reproducible in every detail
- **Expected vs. actual:** Make the difference crystal clear

---

## 20. Exit Criteria: Defining Release Readiness

Establish clear criteria for when QA testing is complete and product is ready for release.

### Release Readiness Matrix

| Category | Ready for Beta | Ready for Release | Ready for Enterprise |
|----------|---------------|-------------------|----------------------|
| Critical Bugs | 0 blocking features | 0 critical severity | 0 critical severity |
| High Priority Bugs | < 5 | 0 | 0 |
| Medium Priority Bugs | < 20 | < 5 | 0 |
| Feature Completeness | 75%+ | 95%+ | 100% |
| Accessibility (WCAG 2.1 AA) | 70%+ compliant | 85%+ compliant | 95%+ compliant |
| Cross-browser Testing | Chrome, Firefox | Chrome, Firefox, Safari, Edge | All major browsers |
| Mobile Testing | iOS + Android | iOS + Android, landscape/portrait | All major devices, orientations |
| Performance | Acceptable | LCP < 2.5s, CLS < 0.1 | Optimized, all metrics green |
| Security | No obvious vulnerabilities | Security audit passed | Third-party security audit + SOC 2 |
| Documentation | Basic help present | Complete docs + FAQ | Comprehensive docs + API docs |

### Release Blocking Issues

Any of these automatically block release:

- [ ] Critical feature doesn't work at all
- [ ] Data loss occurs under any circumstance
- [ ] Security vulnerability exists
- [ ] Compliance requirement not met
- [ ] Application crashes in any core flow
- [ ] Promised feature is not implemented
- [ ] Accessibility is severely broken (keyboard navigation, screen readers)
- [ ] Performance is unacceptable (> 10 second page load)
- [ ] Essential integration is broken

### Sign-Off Document

```
QA Sign-Off Document

Product: [Product Name]
Version: [Version Number]
Release Date: [Planned Date]

Testing Summary:
- Total test cases: [X]
- Passed: [X]
- Failed: [X]
- Blocked: [X]
- Pass rate: [%]

Bug Summary:
- Critical: [X]
- High: [X]
- Medium: [X]
- Low: [X]

Known Issues and Workarounds:
[List any known issues not being fixed, with workarounds]

Tested Configurations:
- Operating systems: [List]
- Browsers: [List]
- Devices: [List]

QA Certification:
This product has been thoroughly tested and meets the acceptance criteria for [Beta / Release / Enterprise] deployment.

Sign-off by: [QA Lead]
Date: [Date]
Contact: [Contact info for issues post-launch]
```

---

## 21. Resources and References

### Browser DevTools and Extensions

- **Chrome DevTools:** Built-in to Chrome, free. Inspect elements, debug JS, monitor network, check performance.
- **Firefox Developer Edition:** Free. Similar to Chrome DevTools with some unique features.
- **Safari Web Inspector:** Built-in to Safari. Requires enabling in Preferences.
- **axe DevTools:** Free, Chrome/Firefox. Automated accessibility scanning.
- **WAVE Browser Extension:** Free, Chrome/Firefox. WebAIM accessibility evaluation.
- **Lighthouse:** Free, built into Chrome. Performance, accessibility, SEO audits.
- **Accessibility Insights:** Free, Microsoft tool for comprehensive accessibility testing.
- **Color Contrast Analyzer:** Free tool for checking color contrast ratios.

### API and Network Tools

- **Bruno:** Free, lightweight API testing tool.
- **Postman:** Free/paid, comprehensive API testing platform.
- **Charles Proxy:** Paid, network proxy for intercepting and modifying traffic.
- **Proxyman:** Paid, modern alternative to Charles Proxy.
- **mitmproxy:** Free, command-line proxy for advanced users.

### Performance and Monitoring

- **Lighthouse:** Chrome built-in performance auditing.
- **WebPageTest:** Free online tool for real-world performance testing (webpagetest.org).
- **GTmetrix:** Free online performance analysis.
- **Sentry:** Error tracking service (free/paid).
- **Datadog:** Paid monitoring platform with APM and logs.
- **Grafana:** Free/paid visualization and monitoring platform.

### Visual and Screenshot Tools

- **Figma:** Design tool with collaboration features.
- **Percy:** Paid, visual regression testing.
- **Chromatic:** Paid, visual testing for Storybook components.
- **Applitools:** Paid, AI-powered visual testing.
- **PixelPerfect:** Browser extension for pixel-perfect design verification.
- **CleanShot X:** Paid (Mac), advanced screenshot and screen recording.

### Testing and Automation

- **Playwright:** Free, modern browser automation and testing framework.
- **Cypress:** Free, developer-friendly end-to-end testing.
- **Selenium:** Free, mature cross-browser testing framework.
- **BrowserStack:** Paid, real device testing cloud.
- **LambdaTest:** Paid, cross-browser testing platform.

### Security Testing

- **Burp Suite Community:** Free, comprehensive security testing (portswigger.net).
- **OWASP ZAP:** Free, automated security scanning.
- **OWASP Top 10:** Standard list of web security risks (owasp.org).
- **OWASP ASVS:** Application Security Verification Standard (comprehensive checklist).

### Accessibility Standards and Resources

- **WCAG 2.1:** Web Content Accessibility Guidelines (official standard).
- **A11y Project:** Community-driven accessibility resources (a11yproject.com).
- **WebAIM:** Web Accessibility In Mind (webaim.org) - comprehensive guides and tools.
- **Deque University:** Free/paid accessibility training.
- **Nielsen Norman Group:** Paid reports and research on UX (nngroup.com).

### Documentation and Best Practices

- **Google Developer Guide:** Quality testing practices (developers.google.com).
- **MDN Web Docs:** Comprehensive web standards reference (mdn.org).
- **Material Design:** Google's design system and guidelines.
- **Apple Human Interface Guidelines:** Apple's design standards.
- **Stripe Documentation:** Example of world-class API documentation.
- **Linear Documentation:** Example of excellent product documentation.

### QA and Testing Communities

- **Test Automation University:** Free courses on testing (testautomationu.applitools.com).
- **Ministry of Testing:** QA training and resources.
- **QA Reddit:** r/QualityAssurance community.
- **Test Bash:** Annual conference for testing professionals.

---

## 22. Deliverables and Daily QA Workflow

### QA Deliverables for Each Release

- [ ] **Test Plan:** Document outlining testing scope, approach, and schedule
- [ ] **Test Cases:** Detailed steps for every feature and workflow
- [ ] **Test Results:** Matrix showing pass/fail for each test case
- [ ] **Bug Reports:** Detailed reports for every defect found
- [ ] **Accessibility Audit Report:** WCAG 2.1 compliance assessment
- [ ] **Performance Report:** Lighthouse scores, Web Vitals, benchmarks
- [ ] **Cross-Browser Compatibility Report:** Testing matrix showing results per browser
- [ ] **Mobile Testing Report:** iOS and Android testing results
- [ ] **Security Assessment:** Summary of security testing and findings
- [ ] **QA Sign-Off:** Final approval document
- [ ] **Known Issues List:** Any known issues and their workarounds
- [ ] **Release Notes:** Summary of changes and known limitations

### Daily QA Workflow

#### Pre-QA (1-2 days before testing)

1. Receive product specification and acceptance criteria
2. Review code changes and technical documentation
3. Set up test environment and verify all tools working
4. Prepare test data and test accounts
5. Create test plan and identify key test scenarios
6. Coordinate with development on any blockers

#### Day 1-2: Inventory and Discovery

1. Screenshot every page and surface (Section 4)
2. Document every user flow (Section 5)
3. Create visual baseline for regression testing
4. Note any obvious issues (broken links, missing content, etc.)

#### Day 3-4: Core QA Testing

1. Execute functional test cases (Section 8)
2. Conduct visual QA audit (Section 6)
3. Perform UX evaluation (Section 7)
4. Test accessibility (Section 9)
5. Log all bugs in tracking system

#### Day 5: Platform Testing

1. Cross-browser testing (Section 12)
2. Mobile testing (Section 13)
3. Performance evaluation (Section 11)
4. Network condition testing (Section 2)

#### Day 6: Specialized Testing

1. Error recovery testing (Section 14)
2. Offline testing (Section 15)
3. Integration testing (Section 16)
4. Security testing (Section 10)
5. AI workflow testing if applicable (Section 17)

#### Day 7: Final Verification

1. Regression testing (verify previously found bugs are fixed)
2. Smoke testing (critical paths)
3. Commercial checklist review (Section 18)
4. Compile all results and create deliverables

### Bug Triage and Communication

**Daily (during testing):**

- Log bugs immediately when found (don't batch)
- Mark severity clearly
- Include reproduction steps and evidence
- Communicate blocking issues to dev team same day

**Weekly (if extended testing):**

- Status meeting with development and product
- Review open bugs, prioritization, fixes
- Discuss blockers and timeline adjustments
- Update test coverage metrics

### Testing Metrics to Track

| Metric | Purpose | Target |
|--------|---------|--------|
| Test Case Pass Rate | % of test cases that pass | > 95% before release |
| Bug Detection Rate | Bugs found per test case executed | Track for future estimation |
| Critical Bugs Remaining | Open P0/critical severity bugs | 0 before release |
| Feature Coverage | % of features tested | 100% |
| Browser Coverage | % of supported browsers tested | 100% |
| Platform Coverage | % of platforms tested (mobile, desktop, etc.) | 100% |
| Bug Fix Rate | % of reported bugs fixed | > 90% before release |

### Release Day Checklist

- [ ] All critical and high-severity bugs fixed and verified
- [ ] Final smoke test passed
- [ ] All documentation updated
- [ ] Release notes finalized
- [ ] QA sign-off document signed
- [ ] Known issues documented with workarounds
- [ ] Support team trained and briefed
- [ ] Monitoring and alerting verified
- [ ] Rollback plan reviewed and ready
- [ ] On-call rotation assigned

### Post-Release Monitoring (24-48 hours)

- [ ] Monitor error tracking service for new issues
- [ ] Check analytics for unexpected behavior
- [ ] Monitor performance metrics
- [ ] Check support channels for user-reported issues
- [ ] Be ready to support hotfix deployment if needed
- [ ] Document any issues found in production
- [ ] Post-release retrospective (what went well, what to improve)

---

## Conclusion

This comprehensive Manual QA Audit Playbook provides everything needed to systematically verify product quality before commercial release. By following this methodology, QA teams can identify issues that automated testing misses and ensure the product meets the high standards expected by customers.

The key to success is treating this as a systematic process, not a checklist to rush through. Each section builds on the previous ones, and the collective findings inform the final release decision.

**Remember:** The goal of QA is not to find bugs—it's to ensure quality. QA is complete when the product is ready to delight customers, not when all tests are finished.
