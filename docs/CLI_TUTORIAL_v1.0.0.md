# FlyGate CLI tutorial · v1.0.0

Live route: https://project-flygate.vercel.app/#/cli

The agent navigation includes a beginner tutorial using the existing navy, cyan and NVIDIA green interface.

## Learning path

1. Check Python and Git, clone the repository, install the CLI and verify `flygate --help`.
2. Select PARP1, Factor Xa or COX-2 and read saved discovery measurements without an API key.
3. Understand JSON, candidates, evidence IDs and human-review outcomes.
4. Configure NVIDIA credentials locally, run fresh DiffDock inference, inspect saved poses, and resume a pending job. An optional triage example follows.

The searchable catalog covers all seven CLI commands, their prerequisites and output interpretation. The page also includes copying, keyboard-operable steps, error guidance and links to implementation and deployment documentation. It never collects credentials or executes terminal commands in the browser.

## Scope

`discover <target>` reads saved measurements. `discover --live` submits fresh DiffDock inference; `--resume` polls an existing request. `watch` writes local notes and state; it does not schedule itself or submit reports. Online model operations may consume provider credits. The tutorial refers to the implementation in `agent/flygate.py` and installation script in `scripts/install_flygate.sh`.

## Verification

- Production TypeScript/Vite build.
- Actual `python3 agent/flygate.py discover parp1` and CLI help invocation.
- Desktop and 390px mobile inspection; no page horizontal overflow after responsive fixes.
- Step selection, target-dependent command, catalog selection/search and empty-state checks.
- Clipboard-denied manual-selection message; copying requires browser permission.
- Mocked live API success, pending/resume, ambiguous timeout, HTTP error and malformed-result tests.
- Actual NVIDIA DiffDock request completed with one saved SDF pose.
