# 0002. Wave planning rules

- **Status:** Accepted
- **Date:** 2026-05-13

## Decision

Waves are planned by rules, not by hand:

1. Port groups move together, because the carrier won't split them.
2. The pilot is the smallest non-critical group.
3. Each wave is capped at 35% of daily volume (configurable).
4. Business-critical numbers go last, in their own waves.
5. Cutovers happen Monday to Thursday only, never on a bank holiday.
6. Five working days of bake time between waves.

## Why

Each rule is a lesson. Fridays leave no working days to fix a bad cutover before the weekend. Port groups split by a well-meaning plan get rejected by the carrier on the day. Critical lines in early waves mean the first problem is also the worst one.

## Consequences

The plan is reproducible and reviewable. Change a rule in code and the reason goes in the docstring.
