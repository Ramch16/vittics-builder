#!/bin/sh
# Clean-room reproduction (Week 20). Run from a fresh clone; uses only offline mock agents.
#   sh scripts/reproduce.sh [slots]        # default slots: 1-4 of the frozen schedule
# Prints one line per step and exits non-zero at the first failed step. Record the whole output.
set -eu
SLOTS="${1:-1-4}"
OUT="${REPRO_OUT:-repro-$(date -u +%Y%m%dT%H%M%SZ)}"
step() { printf '\n== %s\n' "$1"; }

step "environment"
git rev-parse HEAD
git status --porcelain | head -5
python3 --version
uname -a

step "install from the lock (hashes required) into .repro-venv"
python3 -m venv .repro-venv
. .repro-venv/bin/activate
pip install -q --require-hashes -r requirements/dev.lock
pip install -q --no-deps -e .
pip check

step "test suite"
python -m pytest -q -p no:cacheprovider

step "task package (every starter fails, every reference passes)"
python -m benchmark.oracle validate > "$OUT-task-validation.json"
python -c "import json,sys; m=json.load(open(sys.argv[1])); print('all_valid', m['all_valid']); sys.exit(0 if m['all_valid'] else 1)" "$OUT-task-validation.json"

step "schedule reproduces from its seed"
python -m benchmark.schedule --seed 20261031 | diff - benchmark/schedule-20261031.json
echo "schedule identical"

step "mock slots $SLOTS, paired-input audit, report"
python -m benchmark.harness --schedule benchmark/schedule-20261031.json --out "$OUT" --slots "$SLOTS"
python - "$OUT" <<'PY'
import json, sys
from benchmark.audit import audit
out = sys.argv[1]
sched = json.load(open("benchmark/schedule-20261031.json"))
recs = [json.loads(l) for l in open(f"{out}/records.jsonl")]
ids = {r["run_id"] for r in recs}
sched["slots"] = [s for s in sched["slots"] if s["run_id"] in ids]
res = audit(sched, recs)
print("paired-input audit passed:", res["passed"])
sys.exit(0 if res["passed"] else 1)
PY
python -m benchmark.report --records "$OUT/records.jsonl" --out "$OUT/report.md" > /dev/null
python scripts/freeze_evidence.py freeze "$OUT"
printf "\nreproduction finished: %s\n" "$OUT"
