# Cutover runbook (per wave)

## T-5 working days

- [ ] `ccmt plan` output agreed with the partner and the carrier. Port window booked per port group.
- [ ] Generated flow deployed to the Connect **staging** instance, every branch tested with a real phone. DTMF is tested through the partner's SBC, not just the softphone.
- [ ] Holiday schedule loaded into Connect hours overrides.
- [ ] Baseline extract taken: 4 weeks of legacy CDRs for the wave's numbers, normalised.

## T-2

- [ ] Change freeze on the legacy IVR for the wave's numbers.
- [ ] `cdk diff` against prod is empty apart from the expected flow and queue changes.
- [ ] Rollback contact confirmed at the carrier (name and phone number, not an email address).

## Cutover day (Mon-Thu only)

1. Carrier re-points the numbers in the agreed window.
2. Test calls to every number in the wave, covering each top-level option.
3. Confirm CTRs are arriving for each number (dashboard → contacts by DID).
4. Watch for two hours: abandonment, queue wait, technical-error disconnects, emergency transfers.

**Roll back immediately** (carrier re-points to legacy) if:

- any emergency transfer fails, or
- technical-error disconnects go above 1% of contacts, or
- abandonment is more than 5 points above baseline for 30 minutes.

## Days 1-5

- [ ] `ccmt reconcile legacy.csv connect.csv` daily. `investigate` gets an owner the same day, `rollback` gets a call with the partner.
- [ ] Day 5: if every number passes, close the wave and start the next bake period.
