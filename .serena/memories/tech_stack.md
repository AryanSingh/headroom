# Tech Stack
- Python 3.11 dev environment managed by uv; pytest is primary test runner.
- FastAPI proxy/API; Click CLI; React 19 + Vite dashboard; Playwright used from both Python and Node test surfaces.
- TypeScript SDK at `sdk/typescript`; plugins include OpenClaw and agent integrations.
- Rust workspace builds the native extension/wheels.