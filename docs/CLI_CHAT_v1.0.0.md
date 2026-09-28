# FlyGate terminal chat · v1.0.0

Run `./scripts/install_flygate.sh`, then `flygate` in an interactive terminal. `flygate chat` explicitly opens the same session; `flygate chat --plain` disables colors. Existing analysis commands still produce JSON. With non-interactive stdin, bare `flygate` prints help instead of waiting for input.

The start screen uses filled Unicode block lettering, an offset shadow and cyan-to-lime 24-bit ANSI colors. A wing/gate mark appears on wide terminals; narrower terminals receive a compact banner. The framed dashboard shows a wing emblem, model, credential configuration, working directory and session ID on the left, and the seven tools plus repository skill names on the right. `NO_COLOR` disables color.

## Connect accounts

On first interactive launch without an NVIDIA key, the official NVIDIA Build key page opens. Sign in there, generate/copy a key and paste it into the terminal's hidden prompt. A short inference request verifies connectivity. This is browser-assisted API-key setup, not OAuth or automatic key extraction.

The next hidden prompt accepts an optional TypeSafe AI / Jev key. Enter skips either provider and preserves any existing credential. NVIDIA powers chat and fresh DiffDock inference; Jev powers selected pharmacovigilance judgments. `/login` or `flygate login` reopens setup.

Each successfully checked key can optionally be saved in the OS secure credential store. Supported backends are macOS Keychain, Windows Credential Locker, Secret Service and KWallet through Python keyring. Without an available secure backend, the key remains in the current process environment only. The CLI does not write keys into .env, logs or source files. Existing environment/.env credentials take precedence over stored keys. If hidden input is unavailable, setup stops rather than echoing a key.

NVIDIA setup source: https://docs.nvidia.com/ai-workbench/user-guide/latest/how-to/integrations/nvidia-integrations.html

## Talk and run tools

- Ask: `PARP1 후보의 저장된 근거를 보여줘`.
- FlyGate proposes a concrete command. Answer `y` to run it, or Enter to decline.
- Results appear in a compact view; `/last` displays the full output.
- Ask a follow-up to interpret the result. Conversations and input history are kept in memory, not on disk.

`/help`, `/model`, `/clear`, `/login`, `/last`, `/exit` are available. `/run discover parp1` invokes a tool directly after confirmation. Up/down arrows use session history where readline is available. Ctrl+C cancels current input or work; Ctrl+D exits.

Natural-language chat requires a NVIDIA key. The assistant may propose only the seven FlyGate analysis subcommands, never arbitrary shell commands. Execution uses argv with shell=False. Model/tool terminal control sequences are stripped. Remote inference already submitted may continue after a local interruption.

## Verification

Interactive terminal startup and exit were checked. An actual NVIDIA model returned a `discover parp1` proposal; declining it did not run a tool. Automated tests cover approval/decline, follow-up context, secret-pattern rejection, control-character stripping, provider skip/validation/storage, and existing CLI and live-docking behavior.
