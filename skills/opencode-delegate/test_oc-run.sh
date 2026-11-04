#!/usr/bin/env bash
# Tests for oc-run.sh using a fake `opencode` on PATH.
set -u
HERE="$(cd "$(dirname "$0")" && pwd -P)"
SUT="$HERE/oc-run.sh"
T="$(mktemp -d /tmp/oc-run-test.XXXXXX)"; T="$(cd "$T" && pwd -P)"
trap 'find "$T" -delete' EXIT
mkdir -p "$T/bin" "$T/work"
cat > "$T/bin/opencode" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$FAKE_ARGS"
if [ -t 0 ]; then echo tty > "$FAKE_STDIN"; else cat > "$FAKE_STDIN"; fi
[ -n "${FAKE_SLEEP:-}" ] && sleep "$FAKE_SLEEP"
printf '\033[0m> build\033[0m\nhello\n'
FAKE
chmod +x "$T/bin/opencode"
export PATH="$T/bin:$PATH" FAKE_ARGS="$T/args" FAKE_STDIN="$T/stdin"
fail=0; ok() { echo "ok - $1"; }; ng() { echo "not ok - $1"; fail=1; }

# 1. default: model, dir, prompt passed; stdin empty; ANSI stripped
out="$(bash "$SUT" --dir "$T/work" "do it" 2>&1)"; rc=$?
[ $rc -eq 0 ] && ok "exit 0" || ng "exit 0 (got $rc: $out)"
grep -qx -- "-m" "$T/args" && grep -qx "opencode/deepseek-v4.1-flash-free" "$T/args" && ok "default model" || ng "default model"
grep -qx -- "--dir" "$T/args" && grep -qx "$T/work" "$T/args" && ok "dir passed" || ng "dir passed"
tail -1 "$T/args" | grep -qx "do it" && ok "prompt last" || ng "prompt last"
[ ! -s "$T/stdin" ] && ok "stdin closed" || ng "stdin closed ($(cat "$T/stdin"))"
printf '%s' "$out" | grep -q $'\033' && ng "ansi stripped" || ok "ansi stripped"

# 2. --plan and --model
bash "$SUT" --dir "$T/work" --plan --model opencode/x "q" >/dev/null 2>&1
grep -qx -- "--agent" "$T/args" && grep -qx "plan" "$T/args" && ok "--plan" || ng "--plan"
grep -qx "opencode/x" "$T/args" && ok "--model" || ng "--model"

# 3. refuses ~/records and $HOME
: > "$T/args"
bash "$SUT" --dir "$HOME/records" "q" >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && [ ! -s "$T/args" ] && ok "blocks ~/records" || ng "blocks ~/records (rc=$rc)"
bash "$SUT" --dir "$HOME/records/skills" "q" >/dev/null 2>&1; [ $? -eq 2 ] && ok "blocks ~/records subdir" || ng "blocks ~/records subdir"
bash "$SUT" --dir "$HOME" "q" >/dev/null 2>&1; [ $? -eq 2 ] && ok "blocks \$HOME" || ng "blocks \$HOME"

# 4. timeout
FAKE_SLEEP=5 bash "$SUT" --dir "$T/work" --timeout 1 "q" >/dev/null 2>&1; rc=$?
[ $rc -eq 124 ] && ok "timeout 124" || ng "timeout 124 (got $rc)"

# 5. missing prompt -> usage error
bash "$SUT" --dir "$T/work" >/dev/null 2>&1; [ $? -eq 2 ] && ok "no prompt rc=2" || ng "no prompt rc=2"
exit $fail
