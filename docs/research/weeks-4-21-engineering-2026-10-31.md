# Weeks 4–21: engineering delivered on 31 October 2026

Branch `feat/research-engineering-w4-w21` (stacked on `fix/review-and-isolation-policies`). Everything here
runs offline on the mock provider. No paid model run took place, and no human review is claimed.

| Week | Phase | Built and tested | Still needs |
| --- | --- | --- | --- |
| 4 | Protocol and environment freeze | `requirements/dev.lock` (hashed); CI `locked-install` job; frozen schedule and task package (Week 3) | Approved protocol; model, caps and budget (D13); spending authorization |
| 5 | Run instrumentation | Records carry summed agent seconds and union of active spans from the run log | Sub-second timing; human-minutes logging during real runs |
| 6 | Shared runtime limits | `vittics_builder/caps.py`: atomic admission with in-flight reservation; unknown cost refused; CLI refused under usage caps; time cap. `tests/test_caps.py` (9) | Numeric caps (Ramu); measured behaviour against a real provider |
| 7 | Matched baseline | `single_agent` condition (Week 3); `benchmark/audit.py` paired-input audit; passes on the 48 mock records and catches drift | Nikhil's review of the baseline interface (D11) |
| 8 | Pilot execution | Not run (no budget). Harness, caps, audit, report and rerun are ready | Budget and spending decision; a real model |
| 9 | Security boundaries | Docker: no-new-privileges, pids and memory limits, capabilities dropped, read-only `.git`; sign-in rate limit; injection boundary tests. `tests/test_hardening.py` | Sai's independent reproduction; Docker daemon test; hosted image (SEC-06); encryption at rest (SEC-12) |
| 10 | Reliability and recovery | Harness records provider outages and unexpected errors as `provider_unavailable` or `failed` with oracle results, without crashing the schedule | Fault injection against a real provider and a real Docker daemon |
| 11 | Analysis tooling | `benchmark/report.py`: conservative and optimistic acceptance, per-task table, false releases, unknown cost never zero | Real records; Ramu's metric approval |
| 12 | Results | Not possible without real records | Week 8 pilot |
| 13 | Demonstration | `scripts/demo_mock.py`: brief to signed-off, then one slot per condition judged by the oracle | Recording with a real model, if wanted |
| 14 | Manuscript | Methods content exists across the research docs; no results section can be written | Real results; authorship decided by contribution |
| 15 | Project website | `docs/site/index.html`, a local draft stating current status; not published | Publication decision |
| 16 | Individual portfolios | Not engineering; needs each member's own records | Each member |
| 17–18 | Independent review and feedback | Not possible without an outside reviewer | An outside reviewer |
| 19 | Repair and rerun control | `benchmark/rerun.py`: infrastructure-only reruns, original kept, deviation logged; outcome-driven reruns refused | — |
| 20 | External reproducibility | `scripts/reproduce.sh`: hashed install, suite, task validation, schedule check, mock slots, audit, report, freeze. Run once in a fresh clone on 31 October: all steps passed (454 passed, 8 skipped) | An attempt by someone outside the team |
| 21 | Evidence freeze | `scripts/freeze_evidence.py` freeze and verify (changed, missing and added files) | A real evidence set to freeze |
| 22–24 | Contribution evidence, counsel, final handover | Not engineering | The members; counsel |
