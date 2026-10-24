# Call tree format

Every legacy platform exports its IVR differently. Each vendor gets a small adapter that outputs this YAML, and everything downstream (validation, conversion, review) works on one format.

```yaml
name: Brightwell Energy - residential (partner IVR)
timezone: Europe/London
hours: { weekdays: "08:00-20:00", saturday: "09:00-17:00", sunday: closed }
holidays: [2026-12-25, 2026-12-26]
entry: check-hours

nodes:
  check-hours: { type: hours, open: main-menu, closed: closed-message }
  main-menu:
    type: menu
    prompt: "For billing, press 1..."
    options: { "1": billing, "9": gas-emergency }
    timeout: general        # no input, or invalid input after retries
    retries: 2              # 3 attempts in total
  billing: { type: queue, queue: Billing }
  gas-emergency: { type: transfer, number: "+44800111999", prompt: "Connecting you..." }
  closed-message: { type: message, prompt: "...", next: hangup }
  hangup: { type: hangup }
```

| Type | Fields | Becomes in Connect |
|---|---|---|
| `menu` | `prompt`, `options` (DTMF key → node), `timeout`, `retries` (0-5) | One `GetParticipantInput` per attempt. Retries are unrolled, with "Sorry, I didn't get that." on repeats. |
| `queue` | `queue` | `UpdateContactTargetQueue` (`${QUEUE_<NAME>}` placeholder) + `TransferContactToQueue`, with capacity and error branches |
| `transfer` | `number` (E.164), optional `prompt` | Optional message, `TransferParticipantToThirdParty`, and a fallback that reads the number out if the transfer fails |
| `message` | `prompt`, `next` | `MessageParticipant` |
| `hours` | `open`, `closed` | `CheckHoursOfOperation` (`${HOURS_ARN}`). Lookup errors fail open. |
| `hangup` | — | `DisconnectParticipant` |

## Validation rules

| Rule | Severity |
|---|---|
| Entry or transition points at a missing node | error |
| Invalid DTMF key (not 0-9, `*`, `#`) | error |
| Menu without prompt or options | error |
| Transfer number not E.164 | error |
| Loop through messages/hours with no caller input | error |
| Menu without a timeout target | warning |
| More than 5 menu options | warning |
| Node unreachable from entry (dropped from the generated flow) | warning |

## What doesn't map automatically

Some legacy constructs need a human decision, not a converter: database dips mid-menu, speech grammars, skills-based routing rules, and time-of-day routing tables beyond open/closed. Model them as a `queue` or `transfer` placeholder, then build them properly with Lambda or Lex in the target flow.
