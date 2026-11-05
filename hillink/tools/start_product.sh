#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${HILLINK_PYTHON:-$PWD/.venv/bin/python}"
"$PY" -c 'import sys,jsonschema; assert sys.version_info[:2] == (3,11), "Python 3.11 required"'
PORT="${HILLINK_PORT:-8994}"
[[ "$PORT" =~ ^[0-9]+$ ]] && [ "$PORT" -ge 1024 ] && [ "$PORT" -le 65535 ] || exit 2
export HILLINK_LLM_ENABLED=0 HILLINK_LLM_EXTERNAL_OPT_IN=0 HILLINK_AGENT_MODE=replay
export HILLINK_V12Z_COMMON=1 HILLINK_NATIVE_HYBRID=1 HILLINK_AUTONOMOUS_AGENT=1 HILLINK_HYBRID=replay
export HILLINK_GENERAL_FOOD_POLICY=A HILLINK_BREAKFAST_POLICY=BREAKFAST_INCLUDED_DEFAULT_V2 HILLINK_DEPLOY=local
if [ "${1:-}" = --live ]; then
 export HILLINK_LLM_ENABLED=1 HILLINK_LLM_EXTERNAL_OPT_IN=1 HILLINK_AGENT_MODE=live
 "$PY" -B -c 'import sys;sys.path.insert(0,"timeline/viewer");from visit_execution import live_status;ok,reason=live_status();assert ok,reason'
 [[ "${PYTHONPATH:-}" != *offline_test_guard* ]] || { echo 'Live mode cannot start under the offline network guard.'; exit 2; }
else
 [[ "${1:-}" = '' || "${1:-}" = --check ]] || { echo 'Usage: start_product.sh [--check|--live]'; exit 2; }
 export PYTHONPATH="$PWD/tools/offline_test_guard${PYTHONPATH:+:$PYTHONPATH}"
fi
if [ -z "${HILLINK_ISOLATED_REGISTRY:-}" ] && [ -f handover/data/bundle.json ]; then
 DATA_JSON="$("$PY" -B tools/bootstrap_data.py --json)"
 export HILLINK_ISOLATED_REGISTRY="$("$PY" -c 'import json,sys;print(json.loads(sys.argv[1])["path"])' "$DATA_JSON")"
 export HILLINK_ISOLATED_REGISTRY_SHA256="$("$PY" -c 'import json,sys;print(json.loads(sys.argv[1])["sha256"])' "$DATA_JSON")"
 if [ -z "${HILLINK_PROFILE_DISPLAY_REVIEW:-}" ]; then
  export HILLINK_PROFILE_DISPLAY_REVIEW="$("$PY" -c 'import json,sys;print(json.loads(sys.argv[1]).get("profile_display_review") or "")' "$DATA_JSON")"
 fi
fi
if [ -n "${HILLINK_ISOLATED_REGISTRY:-}" ]; then
 export HILLINK_ISOLATED_CUSTOMERS=1 HILLINK_REVIEWER_LOCAL=1
 "$PY" -B -c 'import sys;sys.path.insert(0,"timeline/experiments/persona_live/operator_choice/operator_world_v1_1");from isolated_registry import registrations;print("SHA validated customers:",len(registrations()))'
else
 export HILLINK_ISOLATED_CUSTOMERS=0 HILLINK_REVIEWER_LOCAL=0
fi
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
 export HILLINK_BUILD_SHA="$(git rev-parse HEAD)" HILLINK_BUILD_BRANCH="$(git branch --show-current)"
 [ -z "$(git status --porcelain --untracked-files=no)" ] || { echo 'Commit tracked source changes before serving a review build.'; exit 2; }
else
 "$PY" -B tools/verify_package.py
 export HILLINK_BUILD_SHA="$("$PY" -c 'import json;print(json.load(open("handover/package_manifest.json"))["source_head"])')"
 export HILLINK_BUILD_BRANCH=package
fi
REPLAY_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/hillink-product-replay.XXXXXX")"
export HILLINK_AGENT_CACHE="$REPLAY_PARENT/responses"
"$PY" -B timeline/viewer/visit_execution.py "$HILLINK_AGENT_CACHE"
printf '%s / %s / http://127.0.0.1:%s/ / provider=%s; rules and exact Replay selectable\n' "$HILLINK_BUILD_BRANCH" "$HILLINK_BUILD_SHA" "$PORT" "$HILLINK_AGENT_MODE"
[ "${1:-}" != --check ] || exit 0
exec "$PY" -B timeline/viewer/app.py --port "$PORT" --no-browser
