---
name: opencode-delegate
description: Delegate a coding task, code read, or quick question to opencode running DeepSeek V4.1 Flash (free on OpenCode Zen), then check the result. Use when the user says "opencodeで", "DeepSeekにやらせて", "deepseek flashで", "use opencode", or wants a cheap second model for a task. Works from Claude Code and Codex.
---

# opencode delegate

Run one task in opencode without opening its TUI. The default model is `opencode/deepseek-v4.1-flash-free`. It needs no login, has a 200K context limit, and is free for a limited time. DeepSeek V4 Flash is retired; the old ID is served by V4.1 Flash (`~/research/opencode-deepseek-v4-flash/`).

## Run

```bash
the records checkout/skills/opencode-delegate/oc-run.sh --dir <project dir> "<prompt>"
```

| Option | Use |
|---|---|
| `--dir DIR` | Project to work in. Defaults to the current dir |
| `--plan` | Read-only agent. Use it for questions and reviews, so nothing gets edited |
| `--model P/M` | Another model. For example `deepseek/deepseek-flash` once a DeepSeek key is connected with `/connect` (1M context) |
| `--timeout SEC` | Default 300. Exit 124 on timeout |

Exit codes: 0 means done, 2 means a usage error or a refused directory, 124 means a timeout, and anything else is opencode's own code.

## Rules

- **Never in `the records checkout` or `$HOME`.** The script refuses both. The provider receives every file opencode reads. Don't work around this by copying private files into another dir.
- Write a self-contained prompt that includes file paths, the goal, and how to verify. opencode does not see this conversation.
- For edits, the default `build` agent edits files and runs commands with no approval prompt. Point `--dir` at a git repo or a scratch copy.
- **Check the result yourself.** Run `git diff` / `git status --untracked-files=all` in `--dir` and rerun the tests. Don't trust the model's own summary.
- On a timeout or an empty answer, rerun once. If it still fails, check the end of `~/.local/share/opencode/log/opencode.log` before reporting.
- To reply to the user, show what opencode did, and what you checked, separately.
