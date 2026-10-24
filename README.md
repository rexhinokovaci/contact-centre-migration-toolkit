<h1>
  <img src="https://avatars.githubusercontent.com/u/55946528?v=4&s=80" width="36" height="36" align="left" alt="" />
  &nbsp;Contact-centre migration toolkit
</h1>

[![CI](https://github.com/rexhinokovaci/contact-centre-migration-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/rexhinokovaci/contact-centre-migration-toolkit/actions/workflows/ci.yml)
[![CodeQL](https://github.com/rexhinokovaci/contact-centre-migration-toolkit/actions/workflows/codeql.yml/badge.svg)](https://github.com/rexhinokovaci/contact-centre-migration-toolkit/actions/workflows/codeql.yml)
[![Playground](https://github.com/rexhinokovaci/contact-centre-migration-toolkit/actions/workflows/pages.yml/badge.svg)](https://rexhinokovaci.github.io/contact-centre-migration-toolkit/)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-black)
[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)

Tooling for moving an outsourced or legacy contact centre onto Amazon Connect. It converts the old IVR call tree into contact flows, plans which numbers move when, and checks traffic before and after each cutover.

**[Open the playground](https://rexhinokovaci.github.io/contact-centre-migration-toolkit/)**, the real package running in your browser via Pyodide · [Playground guide](docs/demo-guide.md)

## Commands

```bash
pip install -e '.[dev]'

ccmt validate  samples/partner-ivr.yaml                 # dead branches, bad keys, missing targets, input-free loops
ccmt convert   samples/partner-ivr.yaml -o main-ivr.json # Connect Flow Language, lint-clean
ccmt plan      samples/numbers.csv --start 2026-11-02 --holiday 2026-12-25
ccmt reconcile samples/legacy_cdr.csv samples/connect_ctr.csv   # exit 2 on rollback
```

```text
$ ccmt plan samples/numbers.csv --start 2026-11-02
Pilot      Mon 02 Nov 2026      85 calls/day ( 1.0%)
Wave 1     Mon 09 Nov 2026    1930 calls/day (21.8%)
Wave 2     Mon 16 Nov 2026    2330 calls/day (26.3%)
Critical 1 Mon 23 Nov 2026     320 calls/day ( 3.6%)
Critical 2 Mon 30 Nov 2026    4200 calls/day (47.4%)

$ ccmt reconcile samples/legacy_cdr.csv samples/connect_ctr.csv
+441134960005       129 -> 93       3.3 -> 4.1     27 -> 26    investigate  (volume -28.2% (routing leak or missed number?))
+441134960006       189 -> 187      5.6 -> 14.5    60 -> 95    rollback  (abandonment +8.9 pts; average wait +36s)
overall: rollback
```

## What it gets right

- **One input format.** Vendor exports go through a thin adapter into a [normalised call tree](docs/call-tree-format.md) ([ADR 0001](docs/adr/0001-normalised-call-tree.md)).
- **Retries that work.** `GetParticipantInput` has no retry counter, so menu retries are unrolled into separate blocks with a "sorry" prefix.
- **Safe failure paths.** Every queue handles capacity and errors. A failed transfer reads the number out rather than playing a generic error, which matters for emergency lines.
- **Same lint as the platform.** Generated flows pass the rules used in [amazon-connect-voice-platform](https://github.com/rexhinokovaci/amazon-connect-voice-platform) CI, and placeholders use the same `${...}` convention so they deploy through the same pipeline.
- **Wave rules from real cutovers.** Port groups together, smallest first, critical last, no Fridays or bank holidays, bake time between waves ([ADR 0002](docs/adr/0002-wave-rules.md)).
- **Reconciliation with a verdict.** Per number: volume, abandonment and wait against thresholds, rolled up into pass / investigate / rollback, with an exit code CI can gate on.

## Docs

- [Call tree format](docs/call-tree-format.md)
- [Cutover runbook](docs/cutover-runbook.md)
- [ADRs](docs/adr/)
- [Playground guide](docs/demo-guide.md)

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check . && .venv/bin/mypy && .venv/bin/pytest --cov=ccmt
python samples/generate.py        # synthetic CDRs, deterministic (seeded)
demo/build.sh && python3 -m http.server -d site 8080
```

CI runs ruff, mypy (strict) and pytest with a 90% coverage floor on Python 3.11 to 3.13, smoke-tests the CLI on the samples, and checks the samples regenerate byte for byte.

## Licence

MIT. The brand, numbers and traffic data are synthetic.
