# FlyGate CLI guide v2.0.0

The dashboard guide at https://project-flygate.vercel.app/#/cli includes native macOS Terminal captures and a 24-second, silent motion demo edited from an actual FlyGate session.

## Start

Run `./scripts/install_flygate.sh` from the repository, then `flygate` in a terminal. With non-interactive stdin, bare `flygate` prints help instead of opening chat.

Use `/login` to enter NVIDIA and optional Jev keys through hidden terminal input. A check mark means a key is configured, not that a fresh API connectivity test passed. Keys are never part of the published captures.

## Chat commands

- `/discover parp1`: retrieve saved PARP1 evidence after approval.
- `/signals NIRAPARIB --limit 5`: inspect saved signal statistics.
- `/triage`, `/grade`, `/critic`, `/kr-causality`, `/watch`: use `--help` for each tool's required inputs.
- `/help`, `/login`, `/last`, `/clear`, `/exit`: control the chat session.
- `/run <tool> <arguments>` remains compatible.

Direct shell commands such as `flygate discover parp1` return JSON without the chat approval prompt. For new docking, use `/discover --live --protein <PDB> --ligand-file <SDF-or-SMILES>` in chat, or the equivalent shell command. New docking needs NVIDIA API access and consumes service usage.

Enter sends; Alt+Enter or Ctrl+J inserts a newline. The composer starts at one row and grows to four explicit lines. Terminal colors are inherited, mouse scrolling remains native, and the example placeholder hides on focus.

## Media provenance

Files are in `web/public/media/cli/v2.0.0/`:

1. `01-start.png`: actual interactive CLI startup.
2. `02-command.png`: `/discover parp1` entered in the composer.
3. `03-approve.png`: real execution confirmation before running.
4. `04-result.png`: successful stored-evidence output with 19 evidence IDs.
5. `flygate-demo_v2.0.0.mp4`: four six-second scenes from those captures, with gentle zoom and fades. This is an edited walkthrough, not real-time video and not a new docking run.

Captured September 28, 2026. No synthetic model answers or fabricated analysis results are shown. The `/last` hint in the last scene explains the next action; it was not itself executed in the recorded sequence.

The previous page source and styling are preserved in `docs/releases/cli-guide_v1.1.0/`.
