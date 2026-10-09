# Review fix 7: blocking Semgrep findings

The shared lint gate previously selected ERROR findings without asking Semgrep
to return a failing status. Both the Frappe ERROR scan and app-specific scan now
use `--error`. Advisory findings remain non-blocking; scanner failures still
stop verification.

`scripts/test_verify_semgrep.py` sources the actual shared gate in a temporary
app and runs the pinned scanner and pinned Frappe rules. Fixed clean, Frappe
ERROR, app ERROR, and advisory WARNING inputs verify both exit status and
whether later stages run. The normal lint gate runs this regression after its
scans. No site, credentials, or application data are used.

The domain model was reviewed; no mapped relationship or financial data flow
changes are required.

## Verification evidence

- Risk classification: security verification/CI gate correction.
- Required gates: lint and the gate regression; shared pre-push gate.
- Commands executed: `bash -n scripts/verify.sh`; Ruff check and format-check on
  `scripts/test_verify_semgrep.py`; `bash -c 'source scripts/verify.sh;
  run_semgrep'`; the four-case regression with the installed Semgrep binary
  and pinned Frappe rule checkout passed as command-line arguments.
- Exit statuses: shell syntax, Ruff checks, full Semgrep function and final
  four-case regression all exited 0.
- Tests passed: all four gate regression cases; both app rule tests. Full app
  blocking scans reported no findings.
- Tests failed: the deliberate negative control removing both `--error` flags
  exited 1 with exactly the two blocking-finding cases failing because the
  defective gate returned 0. Clean and advisory cases still passed.
- Coordinator command: `apps/bond_management/scripts/verify.sh pre-push`
  (current staged tree); exit 0, 323 server tests and four gate regression
  cases passed. Evidence: local `fix7-gate-current.log`.
- Tests not run: browser and fresh-install gates are not applicable to this
  scanner-only change.
- Blockers: no remaining focused-test blocker. Local Semgrep trust-store
  initialization requires the existing
  certifi CA bundle via `SSL_CERT_FILE`; sandbox runs also need writable
  `SEMGREP_LOG_FILE` and `SEMGREP_SETTINGS_FILE` paths.
- Unverified local/CI differences: macOS trust-store setup differs from Linux
  CI; CI uses the same pinned scanner, rules and shared lint script.
