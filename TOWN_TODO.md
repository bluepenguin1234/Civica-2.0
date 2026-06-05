# Town Build — Start Here (laptop to-do)

*Pick this up when you're back at your local machine, where `civica_data/` lives.*
*Full spec is in `TOWN_HANDOFF.md`. This is just the running order.*
*Branch: `claude/town-level-data-restructure-SetnN`*

---

## Step 0 — Get on the branch (2 min)
```
git fetch origin
git checkout claude/town-level-data-restructure-SetnN
git pull
```
You should see: `TOWN_HANDOFF.md`, `TOWN_TODO.md`, `download_town_data.py`.

## Step 1 — Download the 3 new datasets (10 min)
```
python download_town_data.py
```
- Lands files in `civica_data/census_population/sub-est.csv`, `civica_data/irs_zip/*zpallagi.csv`, `civica_data/crosswalks/zcta_place_rel_2020.txt`.
- **Want 2 IRS years** (e.g. `22` + `21`) so town income *growth* works; one year still gives income *level*.
- If anything shows `XX` (a Census/IRS URL moved), tell Claude Code: *"fix the failing URL in download_town_data.py and re-run"*. Everything else (NIBRS, BEA, QCEW, etc.) is already on disk — no other downloads.

## Step 2 — Have Claude Code write the scripts (local session)
Open Claude Code locally and say:
> *"Read TOWN_HANDOFF.md and write `town_scoring_engine.py`. Reuse the working county
> loaders in `scoring_engine.py` verbatim; only add sub-est, IRS ZIP, the crosswalk,
> and the NIBRS town rewrite. Resolve the open items in §12 against the real data files."*

Watch the 3 risky bits (all in §12):
- **NIBRS agency-name field** must be located empirically in the BH record.
- **Confirm sub-est columns/SUMLEV** match the downloaded vintage.
- **CDP call** — launch is incorporated places only; confirm that's fine.

## Step 3 — Run scoring once + sanity check (10 min)
```
python town_scoring_engine.py
```
Confirm: ~19k towns, score mean ~50, **towns within the same county are NOT identical**
(crime + town income + growth should vary them), and town-resolved share ≈ 51%.
Then recalibrate the 4 label thresholds from the printed distribution.

## Step 4 — Template + generator
> *"Build `town_profile.html` from `harvard_county_profile.html` per §8b (one score ring,
> 4 dims, 4 labels, the 'ranks #N of M in county' line, remove all Zillow UI, add the
> data-coverage chip and the schools placeholder). Then `town_generator.py` per §8c with
> a `--state XX` flag."*

Generate one test state and open a file: check town name, 4 bars, verdict, rank line,
**no `{token}` leftovers, no "Zillow"**.

## Step 5 — Run the per-state loop (the long part)
Use the loop in `TOWN_HANDOFF.md` §9 (or your `/loop`): it builds one state per pass,
updates `output/towns/_progress.json`, commits + pushes, and stops when all 51 are done.

## Step 6 — Front page + finish
- Point `index.html` search at `output/town_index.json` (town + county + state to
  disambiguate "Springfield").
- Update the count pill to the real town total.
- Regenerate `sitemap.xml` from town URLs.
- Update `CLAUDE.md` / `METHODOLOGY.md` to the town model + the honesty caveats (§11).

---

## Run it efficiently (from the Claude prompting guide)
- Use **`xhigh` effort** in local Claude Code and **allowlist the loop commands** so it runs
  hands-off (it's an autonomous, multi-context-window job — exactly what xhigh + auto is for).
- **Tests first:** have it write `validate_town.py` + `init.sh` BEFORE generating pages
  (TOWN_HANDOFF.md §13). The validator is the gate that replaces eyeballing each state.
- **First window = framework** (validator, scoring, label calibration). **Loop windows =
  generation.** Paste the "don't stop early / save to ledger" preamble from §13c.
- Be **literal about scope** ("every town, every state in the ledger"); the loop is done
  only when `_progress.json` lists all 51 state FIPS.

## Remember (the why)
- **No home-value level anymore** — affordability = HUD rent vs IRS income + FHFA appreciation.
- **~51% town-driven, ~49% county-inherited** — say so plainly; it's honest.
- **100% federal now** — dropping Zillow removed the only non-federal source. Put that on the front page.
- **Town income & crime are real federal data, approximately *placed*** — keep the caveat labels.

Everything detailed lives in **`TOWN_HANDOFF.md`**.
