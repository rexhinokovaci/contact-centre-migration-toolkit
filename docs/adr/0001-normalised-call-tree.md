# 0001. One normalised call tree format, adapters per vendor

- **Status:** Accepted
- **Date:** 2026-05-06

## Context

Outsourced partners run Genesys, Avaya, Cisco, or something home-grown. Converting each export straight to Connect flows means N converters, each with its own bugs.

## Decision

Define a small YAML call tree model (`calltree.py`). Vendor exports get a thin adapter that outputs this format. Validation and conversion only know the normalised model.

## Consequences

- One converter to test and trust. Generated flows are consistent across partners.
- The YAML is readable enough for floor managers to review ("is this really what callers hear?"), which catches hidden routing rules early.
- Constructs that don't fit (database dips, grammars) are deliberately not modelled. They need redesign, not translation.
