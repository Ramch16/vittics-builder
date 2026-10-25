"""The synthetic schema-v2 requirements example (docs/research/examples/requirements-v2, AI-assisted draft).

Its check commands are planned, not implemented, so these tests never claim a product check passed: they
check the contract's structure and the variants' outcomes, and they show the requirement/check mapping
semantics by swapping each command for a synthetic stand-in that exits 0 or 1.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from vittics_builder.tools import Workspace
from vittics_builder.validation import read_contract, requirement_results, verify_product

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "research" / "examples" / "requirements-v2"
REJECTED = ["unknown-check-id", "requirement-without-checks", "duplicate-requirement-id", "bad-risk", "v2-without-registry"]


def load(ws: Workspace, source: Path, outcomes: dict | None = None) -> dict:
    data = json.loads(source.read_text())
    data.pop("_variant_note", None)
    if outcomes is not None:                     # synthetic stand-ins: exit 0 for pass, 1 for fail
        for check in data["checks"]:
            code = 0 if outcomes.get(check["id"], True) else 1
            check["command"] = f'"{sys.executable}" -c "import sys; sys.exit({code})"'
    ws.write_file("product.json", json.dumps(data))
    ws.write_file("README.md", "# Synthetic\n")
    ws.write_file("docs/OPERATIONS.md", "Synthetic example; no services.\n")
    return data


def test_example_is_a_valid_v2_contract_with_planned_commands(tmp_path):
    ws = Workspace(tmp_path)
    load(ws, EXAMPLE / "product.json")
    contract = read_contract(ws)
    assert contract["schema_version"] == 2 and len(contract["requirements"]) == 6 and len(contract["checks"]) == 8
    assert all(c["command"].startswith("PLANNED-NOT-IMPLEMENTED:") for c in contract["checks"])


def test_planned_commands_are_never_reported_as_passing(tmp_path):
    ws = Workspace(tmp_path)
    load(ws, EXAMPLE / "product.json")
    report = verify_product(ws, record=False)
    assert not report["passed"] and not report["release_eligible"]
    assert all(r["status"] == "unverified" for r in report["requirements"])


@pytest.mark.parametrize("name", REJECTED)
def test_broken_variants_are_rejected(tmp_path, name):
    ws = Workspace(tmp_path)
    load(ws, EXAMPLE / "variants" / f"{name}.json")
    with pytest.raises(ValueError):
        read_contract(ws)


def test_agent_claimed_verified_status_is_ignored(tmp_path):
    ws = Workspace(tmp_path)
    load(ws, EXAMPLE / "variants" / "agent-claims-verified.json", {"balance-floor": False})
    report = verify_product(ws, record=False)
    status = {r["id"]: r["status"] for r in report["requirements"]}
    assert status["REQ-004"] == "unverified" and not report["release_eligible"]


def test_weak_check_is_accepted_by_the_validator(tmp_path):
    """Documented limit: structure validation cannot detect an always-passing check."""
    ws = Workspace(tmp_path)
    load(ws, EXAMPLE / "variants" / "trivial-always-pass-check.json")
    assert next(c for c in read_contract(ws)["checks"] if c["id"] == "manager-scope")["command"] == "true"


def test_mapping_semantics_on_synthetic_outcomes(tmp_path):
    ws = Workspace(tmp_path)
    load(ws, EXAMPLE / "product.json", {})                              # every stand-in passes
    report = verify_product(ws, record=False)
    assert report["passed"] and report["release_eligible"] and report["coverage"] == "explicit"
    load(ws, EXAMPLE / "product.json", {"decide-request": False})        # one shared check fails
    status = {r["id"]: r["status"] for r in verify_product(ws, record=False)["requirements"]}
    assert status == {"REQ-001": "verified", "REQ-002": "verified", "REQ-003": "unverified",
                      "REQ-004": "verified", "REQ-005": "unverified", "REQ-006": "verified"}
    load(ws, EXAMPLE / "product.json", {})
    partial = verify_product(ws, record=False, ids=["submit-request"])  # a subset is never release evidence
    assert partial["passed"] and not partial["release_eligible"]
