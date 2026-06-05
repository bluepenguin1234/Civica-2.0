# Civica — Town-Level Restructure: Implementation Handoff

*Hand this file to Claude Code. It contains every decision made and enough
technical detail to write the scripts without re-deriving anything.*
*Branch: `claude/town-level-data-restructure-SetnN`*
*Status: design locked, code not yet written.*

---

## 0. TL;DR — what you're building

Convert Civica from ranking **counties** to ranking **towns** (US Census incorporated
places). Reuse the existing county datasets and the working loaders in
`scoring_engine.py` — but:

- **Drop Zillow entirely** (no more home-value level). Affordability is rebuilt on
  rent-vs-income + appreciation.
- **Collapse 6 dimensions → 4**: Affordability, Economy, Safety & Place, Growth.
- **Two new same-source data inputs** (Level B): Census **sub-est** (town population)
  and IRS SOI **ZIP-code AGI** (town income), plus a ZIP→place crosswalk.
- **~51% of each town's score is town-resolved** (crime, town income, town growth,
  town scale); the other ~49% is inherited from the town's parent county (wages,
  appreciation, climate risk, migration, permits) — because those genuinely operate
  at the regional scale and faking them per-town would be dishonest.
- **One headline Civica Score (0–100)**, plus a plain-English **"ranks #N of M towns
  in [County]"** line. No second gauge shown to users.

Deliverables: `town_scoring_engine.py`, `town_generator.py`, `town_profile.html`,
`output/towns/_progress.json`, updated `index.html` search. Plus a per-state loop so
the whole country can be generated incrementally.

> **Execution constraint:** `civica_data/` (~7 GB, gitignored) is NOT in the cloud
> container. Write the scripts there, but they must be *run* locally where the data
> lives. Don't assume you can execute them in a web session.

---

## 1. Decisions locked (do not re-litigate)

| Question | Decision |
|---|---|
| What is a "town"? | **US Census incorporated places** (see §3 caveat on CDPs) |
| Town population source | **Census sub-est** (sub-county Population Estimates, same program as the county file already used) |
| Replace Zillow how? | **Drop price-to-rent / price-to-income / breakeven.** Affordability = rent-burden + appreciation quality |
| Scoring complexity | **4 dimensions** (down from 6) |
| Data ambition level | **Level B** — add IRS SOI ZIP AGI for town income + ZIP→place crosswalk |
| Score presentation | **Single Civica Score** + in-county rank line. Town/county sub-scores computed internally only |
| Schools | Out of scope for now; user may add later. Leave a clean slot in the template |

---

## 2. Data inventory

### 2a. Already on disk — reuse the existing loaders verbatim
All of these are in `scoring_engine.py` and work today. Keep them; just join their
output to towns via the town's **primary county FIPS** (§3). Each returns a county-keyed
DataFrame on 5-digit `fips`.

| Loader | Gives | Used in town model |
|---|---|---|
| `load_bea()` | per-capita income, 4-yr income growth | Economy (income growth, C) |
| `load_fmr()` | HUD 2BR FMR | Affordability (rent, C) |
| `load_hpi()` | FHFA 3-yr avg + latest appreciation | Affordability (appreciation, C) |
| `load_qcew()` | avg wage, sector quality, HHI | Economy (wage/sector/HHI, C) |
| `load_cbp()` | establishments | Safety & Place (amenity density, C) |
| `load_bps()` | permits | Growth (permits, C) |
| `load_irs()` | in-mover income ratio (migration) | Growth (in-mover quality, C) |
| `load_nfip()` | flood claims | Safety & Place (physical risk, C) |
| `load_noaa_storm()` | storm damage | Safety & Place (physical risk, C) |
| `load_usfs()` | wildfire rank | Safety & Place (physical risk, C) |
| `load_rucc()` | rural-urban code | optional context; replaced as a metric by town scale |
| `load_nibrs_crime()` | **violent** offenses by county | **rewrite** → town-level + add property (§4) |
| `load_population()` | county population | denominators; superseded by town pop for town metrics |

**Do NOT reuse `load_zillow()`.** Delete its call. Remove every Zillow-derived field
(`median_home_value`, `inventory`, `pr_ratio`, `price_income`, `breakeven_yrs`,
`monthly_piti`, `home_appreciation_total_3yr`, `zhvi_imputed`).

### 2b. New inputs to add (all free, same agencies)
| Input | File | Purpose | Notes |
|---|---|---|---|
| Census sub-est | `civica_data/census_population/sub-est2025.csv` (download into existing folder) | town population + town→county crosswalk + town growth | see §3 |
| IRS SOI ZIP AGI | `civica_data/irs_zip/YYzpallagi.csv` for **two** years (e.g. `21zpallagi.csv` + `22zpallagi.csv`) | town income level + town income growth | see §5 |
| ZIP→place crosswalk | Census 2020 **ZCTA-to-Place relationship file** | allocate ZIP AGI to places | see §5 |

> The downloader scripts (`civica_data_downloader_v4/v5.py`) can be extended to fetch
> these, OR the user downloads them manually. Confirm with the user which.

---

## 3. Geography: building the town universe (sub-est)

The Census **sub-est** file uses `SUMLEV` to mark record types:

| SUMLEV | Meaning | Use |
|---|---|---|
| 162 | incorporated place (whole) | **town universe + total town population** |
| 157 | place-within-a-county part | **crosswalk place→county + straddle handling** |
| 061/071 | minor civil division / MCD-place part | ignore for v1 |
| 040/050 | state / county | ignore |

**Town FIPS** = `STATE`(2) + `PLACE`(5) = **7-digit place FIPS**. Preserve leading
zeros (`dtype={'STATE':str,'PLACE':str,'COUNTY':str}`).

**Population columns:** `POPESTIMATE2020` … `POPESTIMATE2025`. Use 2025 as current.

**Build steps:**
1. Universe = all `SUMLEV==162` records with `POPESTIMATE2025 >= 1,000` (town threshold —
   confirmed with user; document it like the existing county ≥5,000 rule).
2. Crosswalk: from `SUMLEV==157` records, group by place FIPS; the **primary county** is
   the county part with the largest `POPESTIMATE2025`. Store `primary_county_fips`
   (5-digit) per town. Places spanning multiple counties → largest share wins.
3. Town growth features (all town-resolved):
   - `town_growth_5yr = POPESTIMATE2025 / POPESTIMATE2020 - 1`
   - `town_growth_1yr = POPESTIMATE2025 / POPESTIMATE2024 - 1` (recent momentum)
   - `town_growth_vol = std(annual pct changes 2020→2025)` (stability; lower = steadier)
   - `town_pop_share = POPESTIMATE2025 / county_total_2025` (centrality within county)
   - `town_scale_pct` = national percentile of `POPESTIMATE2025` (urban-character proxy)
4. `town_growth_rel_county` = `town_growth_5yr − county_growth_5yr` (pure town "alpha";
   compute county_growth_5yr from the `SUMLEV==050` records or the existing county file).

> **⚠ CDP caveat — surface this to the user.** The Population Estimates Program
> (sub-est) covers **incorporated places and MCDs only — NOT census designated places
> (CDPs).** So the town universe will be incorporated places (~19,000). If the user
> wants CDPs too, that requires decennial 2020 place population (a different file) and
> CDPs would have **no annual growth signal**. Recommend: ship incorporated places now;
> treat CDPs as a later add. Do not silently drop CDPs without noting it.

---

## 4. Town crime (NIBRS rewrite — highest technical risk)

Today `load_nibrs_crime()` extracts **county** FIPS from the BH header and counts only
violent offenses. For towns you must (a) map each agency to a **place**, and (b) also
count **property** offenses.

**Two changes:**

1. **Add property crime codes.** Current violent set is
   `{09A,09B,11A,11B,11C,11D,120,13A}`. Add property:
   `{200 (arson), 220 (burglary), 23A–23H (larceny/theft), 240 (motor vehicle theft)}`
   — verify exact NIBRS codes against the file. Count violent and property separately.

2. **Map agency → place.** The BH record contains an **agency name** (e.g.
   "Plano Police Department"). The existing parser reads `ori=line[2:11]`,
   `state_alpha=line[4:6]`, `county3=line[269:272]`. **Empirically locate the agency-name
   field** in the BH record (same empirical approach used to find the county field), then:
   - Normalize the agency name (strip "Police Department", "PD", "Sheriff", etc.).
   - Match to `SUMLEV==162` place names **within the same state**, preferring places whose
     `primary_county_fips` equals the agency's county.
   - Use a deterministic match first (exact normalized name), then a fuzzy fallback
     (`difflib`/rapidfuzz, accept ≥ ~0.9).

**Denominator:** town crime rate = offenses ÷ `POPESTIMATE2025` × 100k.

**Fallback (no penalty for non-reporting — keep today's philosophy):** towns with no
matched agency get the **parent county's** violent/property rate; if the county also has
no NIBRS data, use the RUCC-tier median (reuse the existing tiering logic). Set a
`crime_imputed` flag in the output.

> Sheriff/county-wide agencies cover unincorporated area, not a single town — when an
> agency is a county sheriff, attribute it to the county pool, not to one place.
> Document this approximation; it's the weakest link and the user should know it.

---

## 5. Town income (IRS ZIP AGI + crosswalk)

**IRS `zpallagi`** (`YYzpallagi.csv`): one row per (zipcode, `agi_stub` income bracket).
Key columns: `STATEFIPS`, `zipcode`, `agi_stub`, `N1` (# returns), `A00100` (total AGI,
**in thousands of dollars**).

- ZIP income level: `zip_agi_per_return = sum(A00100)*1000 / sum(N1)` across brackets per ZIP.
- ZIP income growth: same metric from **two** years (e.g. 2021 vs 2022) → pct change.
  If only one year is available, drop income growth and fall back to BEA county income
  growth for that component (document).
- Drop `zipcode` totals (`agi_stub==0` and ZIP `0`/`99999`).

**ZIP→place allocation** (Census ZCTA-to-Place relationship file gives ZCTA↔place with
overlap population):
- `town_income = Σ(zip_agi_per_return × overlap_pop) / Σ(overlap_pop)` over ZCTAs
  overlapping the place.
- Same allocation for income growth.

> **Caveat to document (like the existing per-capita P/I footnote):** ZIP ≠ ZCTA, and
> ZIPs don't nest in places — town income is an **address-share approximation**. It
> varies town-to-town for real, but it is not a survey-grade town median. Label it
> clearly in `town_profile.html` and METHODOLOGY.

---

## 6. The scoring model (4 dims, T = town-resolved, C = county-inherited)

Percentile-rank every metric **nationally across the town universe** (reuse `pct` /
`pct_inv` from `scoring_engine.py`). Weights within each dim shown; dim point caps shown.

| Dim | Pts | Metric | Wt | Source | Layer |
|---|--:|---|--:|---|:--:|
| **1 Affordability** | 28 | Rent burden = `fmr_2br*12 / town_income` | 60% | HUD + IRS ZIP | **T** |
| | | Appreciation quality = `|hpi_3yr_avg − 5|` (lower better) | 40% | FHFA | C |
| **2 Economy** | 28 | Avg annual wage | 35% | QCEW | C |
| | | Sector quality | 25% | QCEW | C |
| | | Diversity (HHI, inverted) | 20% | QCEW | C |
| | | Town income growth | 20% | IRS ZIP | **T** |
| **3 Safety & Place** | 26 | Violent crime / 100k (inverted) | 30% | NIBRS | **T** |
| | | Property crime / 100k (inverted) | 20% | NIBRS | **T** |
| | | Town scale (pop percentile) | 20% | sub-est | **T** |
| | | Amenity density = est / 1k pop | 15% | CBP | C |
| | | Physical risk (flood+storm+fire, inverted) | 15% | NFIP+NOAA+USFS | C |
| **4 Growth** | 18 | Town pop growth 5-yr | 35% | sub-est | **T** |
| | | Town growth vs county + 1-yr momentum | 25% | sub-est | **T** |
| | | Net migration rate | 20% | Census | C |
| | | In-mover income quality | 10% | IRS mig. | C |
| | | Permits | 10% | BPS | C |

Dim score = `Σ(metric_pct × wt) / 100 × dim_pts`. Reuse the dim-function pattern from
`scoring_engine.py` (`score_dim1`…). Physical risk composite = reuse existing
`score_dim5` internals (NFIP 40% / storm 35% / wildfire 25%) as the sub-metric.

**Town-resolved share ≈ 51 / 100** (16.8 + 5.6 + 18.2 + 10.8). This is the answer to
"why isn't it 80% county" — verify it lands near 51% after implementation by summing the
T contributions.

### 6a. The two internal sub-scores + single headline
- `town_local_score`  = (Σ earned **T** points / Σ possible **T** points) × 100
- `county_market_score` = (Σ earned **C** points / Σ possible **C** points) × 100
- `civica_score` (headline, shown) = sum of all 4 dims, clipped 0–100
- `rank_in_county` = rank of `town_local_score` among towns sharing `primary_county_fips`
  (also store `towns_in_county` count) → drives the "#N of M" line.

`town_local_score` and `county_market_score` are **internal columns only** (sorting/debug),
not shown as gauges.

### 6b. Labels (collapsed from 8 → 4; recalibrate after first run)
Start with: **Strong Buy ≥ 62 · Buy ≥ 52 · Hold ≥ 44 · Caution ≥ 0.** Percentile
normalization makes the distribution ~mean 50 / std ~8; after the first national run,
print the distribution and adjust thresholds so all four buckets fire meaningfully
(same calibration discipline as the county model's threshold note in CLAUDE.md).

---

## 7. Output: `town_scores.csv`
One row per town. `dtype={'fips':str}` (7-digit place FIPS). Columns:

```
fips, place_name, state_abbr, primary_county_fips, county_name,
POPESTIMATE2025,
civica_score, market_label, national_rank,
town_local_score, county_market_score, rank_in_county, towns_in_county,
dim1, dim2, dim3, dim4,
# Affordability
fmr_2br, town_income, rent_burden, hpi_3yr_avg,
# Economy
avg_annual_wage, sector_quality, hhi, town_income_growth,
# Safety & Place
violent_per100k, property_per100k, town_scale_pct, est_per_1k,
nfip_per_cap, storm_per_cap, wildfire_rank, crime_imputed,
# Growth
town_growth_5yr, town_growth_1yr, town_growth_rel_county,
RNETMIG2023, inmover_income_ratio, total_permits,
# flags
income_imputed
```

---

## 8. Scripts to write

### 8a. `town_scoring_engine.py`
Fork `scoring_engine.py`. Reuse all county loaders in §2a. Add:
`load_subest()`, `load_irs_zip()`, `load_zip_place_crosswalk()`, rewritten
`load_nibrs_town()`. Build town universe (§3), join county data via
`primary_county_fips`, score 4 dims (§6), write `town_scores.csv` (§7). One-time national
run (percentiles are national). Print distribution + label counts + top/bottom 25.

### 8b. `town_profile.html`
Fork `harvard_county_profile.html`. Keep the full design system in CLAUDE.md (colors,
fonts, cards). Changes:
- **One** score ring (headline `civica_score`); 4 dimension bars, not 6.
- 4-label verdict (Strong Buy / Buy / Hold / Caution) mapped to the existing
  `vb-buy/vb-hold/vb-avoid` pill styles (Strong Buy + Buy → green/blue; Hold → yellow;
  Caution → red).
- Add the **"Ranks #N of M towns in [County] — [plain phrase]"** line under the hero.
- **Remove** all Zillow / price-to-rent / price-to-income / breakeven / monthly-PITI UI.
- Add a small **data-coverage chip**: `Town-level: crime · income · growth — County-level:
  economy · appreciation · climate`.
- Add a footnote: town income is a ZIP-allocated approximation (see §5).
- Leave a clean, commented **"Schools (coming soon)"** placeholder block.
- Token-replacement style (no Jinja) like `county_generator.py`.

### 8c. `town_generator.py`
Fork `county_generator.py`. Reads `town_scores.csv`, joins `place_name`/`county_name`,
writes `output/towns/{place_fips}.html`. Support `--state XX` to generate one state at a
time (for the loop). Append that state's towns to `output/town_index.json`
(`{fips, name, state, county, score, label, dim1-4, rank_in_county}` per town, for search).

### 8d. Front page + sitemap
- Point `index.html` search/autocomplete at `output/town_index.json`; show
  "town, county, state" to disambiguate duplicate names (Springfield problem).
- Update status pill copy: "≈19,000 towns scored" (after first run, use the real count).
- Regenerate `sitemap.xml` from town URLs once all states are built.

---

## 9. The per-state loop (run locally where data lives)

One-time setup (run once): download §2b inputs, run `town_scoring_engine.py` →
`town_scores.csv`, build `town_profile.html`, create
`output/towns/_progress.json` = `{"done": [], "all": [<51 state FIPS>]}`.

Loop body (idempotent, one state per iteration):
1. Read `_progress.json`; `PENDING = all − done`.
2. If `PENDING` empty → rebuild `town_index.json` (sort by score), regenerate
   `sitemap.xml`, wire `index.html` search, commit/push, **STOP**.
3. Else `NEXT = first pending state FIPS`.
4. `python town_generator.py --state NEXT`.
5. Validate: file count == town_scores rows for that state; open one file, confirm name,
   4 bars, verdict, rank line, **no `{token}` leftovers, no "Zillow"**.
6. Append `NEXT` to `done` in `_progress.json`.
7. Commit `output/towns + town_index.json + _progress.json`; push `-u origin
   claude/town-level-data-restructure-SetnN` (retry 2/4/8/16s on network error).
8. Report "State NEXT done (N towns); remaining: <count>". End iteration.

Done condition: `done` contains all 51 state FIPS.

---

## 10. UX changes agreed with the user
1. Plain-English verdict sentence leads the report, score ring secondary.
2. 4 dimensions / 4 labels / 4 colors (not 6/8).
3. Town-name search with county+state disambiguation.
4. "Compared to its county" rank line (turns inheritance into a feature).
5. Jargon (HHI, RUCC, ZIP-income caveat) moved to an expandable "How we scored this"
   drawer; default view stays plain.
6. Honest town/county data-coverage chip.
7. Mobile-first single column; tab bar collapses to accordion.

---

## 11. Honesty caveats that MUST appear (methodology + report footnotes)
- ~49% of the score is county-inherited (wages, appreciation, climate, migration,
  permits) — these are regional by nature; we do not claim town-level wages/home prices.
- Town income is a ZIP→place address-share approximation, not a survey median.
- Crime→town mapping via agency name is approximate; county sheriffs cover unincorporated
  area; non-reporting towns inherit county/RUCC-tier rates and are flagged, not penalized.
- No home-value level exists post-Zillow; affordability is rent-vs-income + appreciation.
- Universe = incorporated places (CDPs excluded unless decennial data is added later).

---

## 12. Open items to confirm before/while coding
1. **Download method** for sub-est, IRS zpallagi (×2 yrs), ZCTA-place crosswalk — extend
   `civica_data_downloader_v*.py` or manual? (ask user)
2. **Exact sub-est filename/columns** — verify against the actual download (SUMLEV codes
   and POPESTIMATE column names confirmed above, but check vintage).
3. **NIBRS agency-name field position** — must be located empirically in the BH record.
4. **IRS year pair** — confirm latest two `zpallagi` years available for growth.
5. **CDP decision** — confirm incorporated-places-only is acceptable for launch.
6. **Threshold** — town pop ≥ 1,000 confirmed; revisit after seeing the distribution.
7. Recalibrate the 4 label thresholds after the first national scoring run.

---

*Everything in this doc reflects decisions already made with the user. When in doubt,
prefer reusing the working county loaders in `scoring_engine.py` over rewriting them, and
flag any data-quality approximation in the UI rather than hiding it — that honesty is the
core Civica brand promise (see CLAUDE.md).*

---

## 13. Build-execution guidance (read before coding)

This build spans many context windows (one-time scoring + a 51-state generation loop).
The following keeps it efficient and prevents drift across fresh context windows. Run
Claude Code at **`xhigh` effort** and allowlist the repetitive loop commands so it runs
autonomously with minimal approvals.

### 13a. Tests-first — write `validate_town.py` BEFORE generating
Create the validator as the FIRST coding step, and treat its checks as immovable (do not
weaken a check to make a run pass). It asserts, against `town_scores.csv` and the output:
- Town count is in the expected band (~15–19k incorporated places ≥ 1,000 pop).
- Score distribution sane: mean ~50, std ~6–9, range within 0–100.
- **Towns within the same county are NOT identical** — group by `primary_county_fips`,
  assert score variance > 0 for multi-town counties (proves crime/income/growth vary them).
- Town-resolved share ≈ 51% (recompute from the T-weights; assert 0.45–0.57).
- `fips` is a 7-digit zero-padded string; no nulls in `civica_score`/`market_label`.
- For generated HTML: **zero** occurrences of `Zillow`, `price-to-rent`, `{`+token braces,
  or `stroke-dashoffset` left at template defaults; town name + 4 bars + rank line present.
- All 4 labels fire with non-trivial counts after threshold calibration.

Run `validate_town.py` after scoring and after each state's generation. A red check = stop
and fix, don't proceed.

### 13b. Setup script — `init.sh`
Write a small `init.sh` that a fresh context window can run to get oriented without
rediscovering commands: `python download_town_data.py` (if data missing) → `python
town_scoring_engine.py` (if `town_scores.csv` missing) → `python validate_town.py`. Keep
it idempotent. This prevents repeated setup work across context windows.

### 13c. Loop preamble — paste this into the per-state loop prompt
> *Your context window auto-compacts as it fills, so you can keep working indefinitely.
> Do not stop early over token-budget concerns. After each state, save progress to
> `output/towns/_progress.json` before continuing. Generate every town in the state and
> work through every state in the ledger; the task is done only when `done` contains all
> 51 state FIPS. If a context window is about to refresh, persist state to the ledger
> first, then continue from it.*

State scope **literally**: "every town in the state, every state in the ledger" — Opus 4.8
follows instructions literally and will not infer unstated scope. Conversely, avoid
ALL-CAPS "CRITICAL/MUST" phrasing in the build prompts; on current models it overtriggers.
Prefer "do X" over "don't do Y" except in the validator's explicit reject-list.

### 13d. Order of operations (first context window vs. loop)
1. **First context window = framework only:** write `validate_town.py`, `init.sh`,
   `town_scoring_engine.py`; run scoring once; recalibrate the 4 label thresholds from the
   printed distribution; confirm `validate_town.py` is green. Do NOT start mass HTML
   generation here.
2. **Subsequent windows = the loop:** `town_generator.py --state XX`, validate, update
   ledger, commit/push, repeat. Starting a fresh window beats compaction for the loop —
   the ledger carries all needed state.
