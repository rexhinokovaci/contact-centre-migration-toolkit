# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [SemVer](https://semver.org/).

## [0.1.0] - 2026-10-24

### Added

- Normalised call tree model and YAML loader.
- Validation: missing targets, DTMF keys, E.164, input-free loops, unreachable nodes, menu size.
- Conversion to Connect Flow Language with unrolled retries, queue capacity handling and failed-transfer fallback.
- Flow lint matching amazon-connect-voice-platform.
- Cutover wave planner (port groups, pilot, volume caps, critical last, Mon-Thu, bake days).
- Traffic reconciliation with pass / investigate / rollback verdicts.
- `ccmt` CLI, synthetic samples, Pyodide playground with guided tour.

[0.1.0]: https://github.com/rexhinokovaci/contact-centre-migration-toolkit/releases/tag/v0.1.0
