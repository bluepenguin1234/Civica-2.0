# START HERE

**You (Claude Code) are building the town-level version of Civica. This file is the one
entry point — read it, then execute the whole build start to finish.**

Run at **xhigh effort**. Act, don't suggest — make the changes, run the scripts, commit as
you go. Only stop at the decision points listed in §D below; for everything else, proceed.

---

## A. First, confirm you can run (30 seconds)
1. You're in the Civica repo on branch `claude/town-level-data-restructure-SetnN`
   (`git checkout claude/town-level-data-restructure-SetnN` if not).
2. `civica_data/` exists locally with the county datasets (BEA, QCEW, FHFA, NIBRS, etc.).
   If it's missing, STOP and tell the user — the ~7 GB of data must be on this machine.

## B. Read these two, in order, before coding
- `TOWN_TODO.md` — the step-by-step running order.
- `TOWN_HANDOFF.md` — the full spec (data, geography, the 4-dimension scoring, the
  Zillow removal, output schema, and §13 build-execution guidance). When the TODO and the
  HANDOFF agree, follow the HANDOFF's detail.

## C. Then do this, in order
1. **Download the 3 new datasets:** `python download_town_data.py`. If any show `XX`, fix
   the moved Census/IRS URL in that script and re-run. (sub-est, IRS ZIP ×2 years, ZCTA→place.)
2. **Framework first (one context window):** write `validate_town.py` and `init.sh`
   (HANDOFF §13a/§13b), then write `town_scoring_engine.py` — reuse the county loaders in
   `scoring_engine.py` verbatim; add sub-est + IRS ZIP + crosswalk + the NIBRS town rewrite;
   **drop Zillow entirely** (no `load_zillow()`, remove every Zillow field — affordability is
   rent-vs-income + appreciation, HANDOFF §6).
3. **Score once + validate:** run `town_scoring_engine.py` → `town_scores.csv`; run
   `validate_town.py` (must be green); recalibrate the 4 labels from the printed distribution.
4. **Template + generator:** build `town_profile.html` (one score ring, 4 dims, the
   "ranks #N of M in county" line, no Zillow UI) and `town_generator.py --state XX`.
5. **Generate all town pages:** run `town_generator.py` to generate **every town in every
   state in one pass** (it's a fast Python loop — no per-state prompting needed). Write each
   state's result to `output/towns/`, update `output/towns/_progress.json` as you go, and
   commit in batches (e.g. every few states) so commits stay reasonable. Run
   `validate_town.py` over the output. If the session is ever interrupted, resume from the
   ledger — generate only states not yet in `done`. Done only when `done` contains all 51
   state FIPS.
6. **Finish:** wire `index.html` search to `output/town_index.json`, update the count pill,
   regenerate `sitemap.xml`, and update CLAUDE.md/METHODOLOGY.md to the town model.

> Your context window auto-compacts, so keep working indefinitely — do not stop early over
> token budget. Save progress to `_progress.json` before each state. Generate **every town
> in the state and every state in the ledger.**

## D. The only places to ask the user (use the recommended default if they say "don't ask")
1. **A download URL moved** and you can't resolve it → ask for the current link.
2. **NIBRS agency→town mapping** looks wrong/low-coverage → show a sample, confirm approach.
   (Recommended fallback: towns with no matched agency inherit county/RUCC-tier crime rate.)
3. **CDPs** → recommended: launch with incorporated places only; confirm.
4. **Label thresholds** after first run → recommended: set so all 4 buckets are non-trivial.

Everything else: proceed and keep going.

## E. Definition of done
All 51 states in `_progress.json` → `done`; `validate_town.py` green; front-page search +
sitemap updated; everything committed and pushed to
`claude/town-level-data-restructure-SetnN`. Then summarize what was built for the user.
