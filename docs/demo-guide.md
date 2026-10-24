# Playground guide

[Open the playground](https://rexhinokovaci.github.io/contact-centre-migration-toolkit/). It loads Python 3.12 in your browser (a few seconds on first visit), then runs the `ccmt` package from this repo. A guided tour opens on first visit. Reopen it with **Take the tour**.

## Three-minute walkthrough

1. **Convert.** The sample partner IVR converts to 28 Connect blocks, lint-clean. Point out:
   - the dropped dead branch (`smart-meter-campaign`, left over from an old campaign)
   - `main-menu--retry1` and `--retry2` in the JSON, where retries are unrolled
   - the `gas-emergency--failed` block, which reads the number out if the transfer fails.
2. **Break it.** Change `"3": home-moves` to `"3": home-movs` and press *Convert*. You get a validation error and no flow. Then add a seventh menu option and get the "hard to remember" warning.
3. **Plan.** *Plan waves*: the Welsh line is the pilot (smallest, non-critical), payments and meter readings move together (same port group), and the two critical lines go last on separate Mondays. Add a bank holiday on a cutover date and re-run: the wave slides.
4. **Reconcile.** One number was never re-pointed (volume down 28%, *investigate*) and one has an abandonment spike (+8.9 points, *rollback*). The overall verdict is *rollback*.

## Your own data

The reconcile step accepts your own CSVs (`date,did,outcome,wait_seconds`). Files are processed in your browser and never uploaded.
