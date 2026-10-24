# Security policy

## Reporting a vulnerability

Please report privately through [GitHub security advisories](https://github.com/rexhinokovaci/contact-centre-migration-toolkit/security/advisories/new). Don't open a public issue. You'll get an acknowledgement within 3 working days.

## Scope notes

CDR and CTR exports contain caller numbers. Treat them as personal data:

- Never commit real exports. The samples are synthetic (`samples/generate.py`).
- The browser playground processes uploaded files locally. Nothing is sent anywhere.
- Report anything that could leak call data (logs, error messages, reports) as a security issue.
