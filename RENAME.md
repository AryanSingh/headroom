# Product Rename: Headroom → CutCtx

## Summary
The product has been renamed from "Headroom" to "CutCtx" with corresponding package and branding updates completed on **2026-06-15**.

## Changes Completed

### Python Package
- **Package name**: `headroom-ai` → `cutctx-ai`
  - File: `/pyproject.toml`
  - Change: `name = "cutctx-ai"`
  - Status: ✅ Updated

- **CLI command**: `headroom` → `cutctx`
  - File: `/pyproject.toml`
  - Change: `[project.scripts]` entry updated from `headroom = "headroom.cli:main"` to `cutctx = "headroom.cli:main"`
  - Note: Python module path remains `headroom` (internal implementation detail)
  - Status: ✅ Updated

- **Contributors/Maintainers**: Updated to "CutCtx Contributors"
  - File: `/pyproject.toml`
  - Status: ✅ Updated

### TypeScript / Node.js Packages
- **SDK package name**: `headroom-ai` → `cutctx-ai`
  - File: `/sdk/typescript/package.json`
  - Status: ✅ Updated

- **OpenClaw plugin package name**: `headroom-openclaw` → `cutctx-openclaw`
  - File: `/plugins/openclaw/package.json`
  - Description updated to reference CutCtx
  - Dependency updated: `headroom-ai` → `cutctx-ai`
  - Status: ✅ Updated

- **OAuth2 plugin package name**: `headroom-oauth2` → `cutctx-oauth2`
  - File: `/plugins/headroom-oauth2/pyproject.toml`
  - Description updated to reference CutCtx proxy
  - Entry point updated: `[project.entry-points."headroom.proxy_extension"]` → `[project.entry-points."cutctx.proxy_extension"]`
  - Status: ✅ Updated

### Branding
- **README.md**: Updated title/heading references from "Headroom" to "CutCtx" in first 20 lines only
  - Internal code references (e.g., `headroom` Python module, library calls) left unchanged
  - Status: ✅ Updated

## Manual Actions Required

### Before Production Release

1. **PyPI Publishing** (Python)
   - Register `cutctx-ai` package on PyPI
   - Upload the new package version
   - Note: Old `headroom-ai` package should be deprecated with a notice pointing to `cutctx-ai`
   - Timeline: Coordinate with release process

2. **npm Publishing** (Node.js)
   - Register `cutctx-ai` package on npm
   - Register `cutctx-openclaw` plugin on npm
   - Upload new package versions
   - Note: Old `headroom-ai` packages should be deprecated with notices pointing to new packages
   - Timeline: Coordinate with release process

3. **GitHub Repository Rename**
   - Current: `github.com/chopratejas/headroom`
   - New: `github.com/chopratejas/cutctx` (or desired new URL)
   - Update all references in docs and CI/CD
   - Set up redirects for old repository

4. **Documentation Site Update**
   - Update domain if applicable (current: headroom-docs.vercel.app)
   - Update all internal links to match new package names
   - Update installation instructions: `pip install cutctx-ai` and `npm install cutctx-ai`
   - Update CLI command examples: `headroom` → `cutctx`

5. **CI/CD and GitHub Actions**
   - Update workflows that reference `headroom-ai` package
   - Update PyPI and npm publishing workflows
   - Update version and naming in CI/CD secrets and environment variables

6. **Docker Images** (if applicable)
   - Rebuild and republish Docker images with new product name
   - Update Docker Hub repository naming if needed

7. **URLs and Links**
   - Update all URLs in code comments, docs, and config files
   - Update PyPI project URL in pyproject.toml if repository URL changed
   - Update npm registry links
   - Update documentation links

8. **License and Legal**
   - Verify all license headers reference correct product name
   - Update NOTICE file if needed
   - Update any trademark or branding documents

9. **Analytics and Monitoring**
   - Update product name in analytics platforms
   - Update monitoring/observability dashboards
   - Update error tracking service configurations

10. **Communication**
    - Announce deprecation of old packages to users
    - Provide migration guide: `pip install cutctx-ai` / `npm install cutctx-ai`
    - Update Discord, documentation site, and community channels

## Files Modified
- `/pyproject.toml`
- `/sdk/typescript/package.json`
- `/plugins/openclaw/package.json`
- `/plugins/headroom-oauth2/pyproject.toml`
- `/README.md` (first 20 lines)

## Files NOT Modified (Intentional)
- Python module directory remains `headroom/` (internal implementation)
- Rust crate names and paths remain unchanged (internal implementation)
- All internal Python import statements remain `from headroom...` (backwards compatibility during transition)
- Plugin entry point names that reference the internal proxy remain as `cutctx.proxy_extension` (updated from `headroom.proxy_extension`)

## Testing Checklist
- [ ] `pip install cutctx-ai` installs successfully
- [ ] `cutctx --help` works (new CLI command)
- [ ] `npm install cutctx-ai` works
- [ ] `npm install cutctx-openclaw` works
- [ ] Python imports still work via `import headroom` (internal module)
- [ ] All tests pass with updated package names
- [ ] Documentation builds and renders correctly
- [ ] URLs in documentation point to correct locations

## Rollback Plan
If needed before public release, changes can be reverted by:
1. Restoring from git: `git checkout HEAD -- .`
2. Or manually reversing the substitutions documented above

## Notes
- The internal Python module name (`headroom`) was not changed to maintain backwards compatibility during the transition period and minimize internal refactoring
- The CLI command was changed to `cutctx` for user-facing consistency
- Entry points were updated to use the new product namespace (`cutctx.proxy_extension`)
- All public package names (PyPI, npm) have been updated to the new branding
