# Civica — Harvard Research Model
*Project bible for Claude Code. Read this before touching anything.*
*Last updated: May 2026*

---

## NEXT TASK — Build county_generator.py

**`scoring_engine.py` is COMPLETE. `county_scores.csv` has 2,820 counties scored.**

### Coverage Decision (intentional — do not change)
- **2,816 of 3,144 counties are scored.** The 328 excluded counties all have population < 5,000.
- The threshold is `pop >= 5,000` in `scoring_engine.py` — this is a deliberate data quality decision.
- Counties under 5,000 have no Zillow data, suppressed QCEW employment figures, and often no FHFA HPI history. Their scores would be entirely median imputation — meaningless.
- Largest excluded county: Oneida County, ID (pop 4,953). Smallest: Loving County, TX (pop 43).
- On the front page, display: **"2,816 counties scored"** — not "all 3,143". Don't claim coverage you don't have.
- If a user searches for an unscored county, show: "This county has fewer than 5,000 residents. Civica requires sufficient housing market data to produce a reliable score."

### Scoring Engine Results (v1.2 — current, includes FBI NIBRS Dim4)
- Runtime: ~4 minutes; output: `county_scores.csv` (2,816 rows × 35 columns)
- Distribution: mean=50.0, std=7.68, range 21.11–73.54
- Top: Lake County IL (73.54 ACCELERATING)
- Labels: ACCELERATING (18), PEAKING (163), ESTABLISHED (549), EMERGING (1,219), FRONTIER (690), TURNING (163), SPECULATIVE (11), AVOID (3)
- Data vintage: Census Pop 2025, CBP 2023, BPS 2025, NOAA 2020–2024, BLS QCEW 2023 (2024 pending manual download)

### Next Step: `county_generator.py`

This script reads `county_scores.csv` and produces one HTML file per county using `harvard_county_profile.html` as the template. It uses Python string replacement (no Jinja2 needed — just replace placeholder tokens in the HTML).

**Steps:**
1. Read `county_scores.csv` with `dtype={'fips': str}` to preserve leading zeros
2. Get county names by joining with USDA RUCC (`civica_data/usda_rucc/ruralurbancodes2023.xlsx`, columns `FIPS` + `County_Name` + `State`)
3. For each row, replace tokens in the HTML template with real values
4. Write each file to `output/counties/{fips}.html` (create the folder if needed)
5. Write `output/index.json` — array of `{fips, name, state, score, label, dim1–dim6, median_home_value, avg_annual_wage}` for every county, sorted by score descending — the front page will load this to build the search/map

**Token map — replace these strings in the template:**

| Token | Value from CSV |
|---|---|
| `Jefferson County, CO` (h1) | `{county_name}, {state_abbr}` |
| `Metro Denver · RUCC Code 1 (Large Metro) · Pop. 582,910` | `RUCC {rucc} · Pop. {POPESTIMATE2023:,}` |
| `80` (score ring sh-num) | `{total_score:.0f}` |
| `stroke-dashoffset="52.02"` (hero ring) | computed: `289.02 * (1 - score/100)` |
| `stroke-dashoffset="57.8"` (banner ring) | same formula |
| `80` (banner ring SVG text) | `{total_score:.0f}` |
| `Top 14% Nationally` | `Top {pct:.0f}% Nationally` (derived from national_rank / 2820 * 100) |
| `vb-buy">BUY` | `vb-{verdict_class}">{verdict_text}` |
| `22.2x` (P/R pill) | `{pr_ratio:.1f}x` |
| `2.1 years` (breakeven pill) | `{breakeven_yrs:.1f} years` |
| `+3.7% / yr` (appreciation pill) | `{hpi_3yr_avg:+.1f}% / yr` |
| `$3,040` (monthly cost pill) | `${monthly_piti:,.0f}` |
| `+4,200 HH` (net migration pill) | `{NETMIG2023:+,.0f} HH` |
| `Strong structural buy...` (thesis text) | generated from label + top signals |
| dim score values in sbb-items (72, 84, 88...) | `{dim1/25*100:.0f}`, etc. (convert to 0–100 sub-scores) |
| `$527,000` (home value) | `${median_home_value:,.0f}` |
| `$1,980` (rent) | `${fmr_2br:,.0f}` |
| `5-Year Scenarios` values | bull=value×1.63, base=value×1.27, bear=value×0.93 |
| `County Research Report · 2025` (eyebrow) | `County Research Report · 2026` |
| `<title>Jefferson County, CO` | `<title>{county_name}, {state_abbr}` |

**Verdict logic:**
- score ≥ 58 → `vb-buy` / `BUY`
- score 38–57 → `vb-hold` / `HOLD`
- score < 38 → `vb-avoid` / `AVOID`

**Thesis text — one sentence per label:**
- PEAKING: `"Strong momentum market near its affordability ceiling. Best for buyers with short-to-medium hold horizons."`
- ESTABLISHED: `"Solid, balanced market with sustainable fundamentals and moderate appreciation."`
- EMERGING: `"Improving fundamentals with early-mover upside. Demand is building ahead of prices."`
- FRONTIER: `"Thin market data. Fundamentals are mixed — conduct additional local due diligence."`
- TURNING: `"Softening demand signals. Monitor for continued weakness before committing."`
- SPECULATIVE: `"Poor fundamentals. Current prices appear disconnected from underlying economics."`

**Dimension sub-scores for the banner (convert to 0–100):**
- dim1 raw is 0–25 pts → sub-score = `dim1 / 25 * 100`
- dim2 raw is 0–22 pts → sub-score = `dim2 / 22 * 100`
- dim3 raw is 0–20 pts → sub-score = `dim3 / 20 * 100`
- dim4 raw is 0–15 pts → sub-score = `dim4 / 15 * 100`
- dim5 raw is 0–12 pts → sub-score = `dim5 / 12 * 100`
- dim6 raw is 0–6 pts  → sub-score = `dim6 / 6  * 100`

After that: wire the front page (`civica.html` or a new `civica-v2.html`) to load `output/index.json` and link to the county reports.

---

## What Civica Is

Civica is an unbiased, data-driven platform that scores all 3,143 US counties for homebuyers. No agents, no listings, no advertising. Every score comes exclusively from free federal government data. This is the core brand promise — never compromise it.

**The one-paragraph pitch:**
Civica is the only platform where a homebuyer can look up any US county and get objective, data-backed answers to the questions that actually matter: Is this a good place? Are smart buyers choosing it? Is it getting better or worse? Every score is derived from free federal government data — no agents, no listings, no advertising, no conflict of interest. The first consumer real estate tool whose scores cannot be bought.

---

## The Chosen Model — Harvard-Style 6-Dimension Research Framework

**This is the locked-in design direction.** After exploring multiple UI/model approaches (simple 4-question buyer card, comprehensive 4-pillar v2, and the Harvard research model), the Harvard model was selected. Do not revert to earlier designs.

**Why this model was chosen:**
1. Uses 8 derived metrics (P/R ratio, breakeven horizon, real appreciation, permit gap) that no competitor publishes
2. Treats homebuyers like sophisticated investors — shows the WHY behind every score
3. The $95k+ target demographic wants analytical depth, not just stoplight colors
4. Bull/base/bear scenario analysis and risk matrix are genuinely differentiated features
5. 6-dimension breakdown provides more signal nuance than 4 pillars
6. The vs. Zillow/Redfin comparison table is a trust-building feature unique to Civica

---

## Design System — Lock These Values

*This is the Harvard county profile design. It is the only active design direction. Two earlier concepts (4-question buyer card and 4-pillar v2) were explored and discarded — do not revert to them.*

### CSS Variables (all 12 — use exactly these)
```css
:root {
  --blue:    #1a7ff0;   /* primary brand — CTAs, links, score ring, active tabs */
  --navy:    #1a3a5c;   /* hero background, headings, logo text, stat values */
  --green:   #16a34a;   /* positive signals, BUY verdict, ACCELERATING badge */
  --yellow:  #d97706;   /* caution signals, PEAKING/SPECULATIVE, flat delta */
  --red:     #dc2626;   /* negative signals, AVOID verdict, bear scenario */
  --purple:  #7c3aed;   /* supplemental accent — IRS migration signals */
  --bg:      #f0f2f5;   /* page background (light gray) */
  --card:    #ffffff;   /* card background */
  --border:  #e5e7eb;   /* dividers, table borders, card borders */
  --muted:   #9ca3af;   /* secondary labels, card-title text, meter range labels */
  --text:    #1f2937;   /* primary body text */
  --subtext: #6b7280;   /* secondary body text, card-intro, signal body */
}
```

### Typography
- **Font stack**: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` (system font — no external load)
- **Score ring number**: 34px, font-weight 900, color #fff (hero ring); 22px weight 900 in score banner SVG
- **"Top X% Nationally"**: 12px, font-weight 700, color #4ade80 (bright green, below ring)
- **H1 county name**: 28px, font-weight 900, line-height 1.1, color #fff
- **Eyebrow labels**: 11px, font-weight 700, letter-spacing .1em, uppercase, color rgba(255,255,255,.4)
- **Hero sub**: 13px, color rgba(255,255,255,.5)
- **Card title**: 11px, font-weight 700, uppercase, letter-spacing .08em, color var(--muted)
- **Card intro text**: 14px, color var(--subtext), line-height 1.65
- **Stat box value (`.sb-val`)**: 24px, font-weight 800, color var(--navy); `.big` variant = 32px
- **Stat box label**: 11px, color var(--muted), font-weight 500, line-height 1.3
- **Delta text**: 12px, font-weight 600 — `.up` green / `.down` red / `.flat` yellow
- **Body / signal text**: 13px, line-height 1.55, color var(--subtext)
- **Section headings inside cards**: 12px, font-weight 700, uppercase, letter-spacing .07em, color var(--muted)
- **Nav links**: 13px, color var(--blue); nav tag: 11px weight 700, bg #f1f5f9, color var(--subtext)
- **Footer**: 11px, color var(--muted), line-height 1.8, text-align center

### Logo — Never Alter
```html
<svg width="22" height="22" viewBox="0 0 30 30" fill="none">
  <rect width="30" height="30" rx="6" fill="#1a7ff0"/>
  <path d="M9 21L15 9L21 21" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <line x1="11" y1="17" x2="19" y2="17" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
</svg>
<span class="logo-text">civi<em>ca</em></span>
```
- Blue rounded-rect icon with white A-shape (inverted V + crossbar)
- Logotype: "civi" in var(--navy) #1a3a5c, "ca" in italic tag at var(--blue) #1a7ff0
- Font: 17px, font-weight 800

### Nav Bar
- White background, 52px height, sticky top z-index 200
- Border-bottom: 1px solid var(--border)
- Right side: "Research Report" tag chip + "← Back to map" link in blue

### Hero Section
- Background: var(--navy) `#1a3a5c`
- Padding: 28px 24px top, 0 bottom (tabs flush to bottom)
- Left side: eyebrow ("County Research Report · 2026") + H1 county name + sub (RUCC + pop)
- Right side: score ring (110×110px SVG) + verdict badge (BUY/HOLD/AVOID pill)
- Score ring: SVG circle r=46, cx=cy=55, circumference=289.02; track stroke rgba(255,255,255,.1); fill stroke #1a7ff0; `stroke-dashoffset = 289.02 × (1 − score/100)`; `stroke-linecap: round`; `transform: rotate(-90deg)` on svg so ring starts at top
- Verdict pill: `.vb-buy` bg #16a34a / `.vb-hold` bg #d97706 / `.vb-avoid` bg #dc2626; 13px weight 800, border-radius 100px, padding 8px 18px

### Hero Pills (data callouts on navy background)
```css
.hero-pill {
  background: rgba(255,255,255,.1);
  border: 1px solid rgba(255,255,255,.15);
  border-radius: 8px;
  padding: 8px 14px;
  display: flex; flex-direction: column; gap: 2px;
}
.hp-lbl { font-size:10px; color:rgba(255,255,255,.4); text-transform:uppercase; letter-spacing:.06em; font-weight:600; }
.hp-val { font-size:13px; font-weight:700; }
/* value colors: .hp-green=#4ade80  .hp-yellow=#fbbf24  .hp-red=#f87171  .hp-white=#fff  .hp-purple=#c4b5fd */
```
Pills wrap in a flex row, gap 8px, margin-top 18px, padding-bottom 20px.

### Tab Bar
- Background: rgba(0,0,0,.25) on top of navy hero — sits flush at hero bottom
- Tabs: 13px weight 600, color rgba(255,255,255,.5) inactive; #fff active; border-bottom 2px solid var(--blue) active
- Overflow-x: auto (hidden scrollbar) — mobile horizontal scroll
- On tab click: panels toggle `.active`, scroll to hero bottom - 52px (nav height)

### Page Layout
- max-width: 960px, margin: 0 auto, padding: 24px 16px
- Panels: `display:none` → `display:flex; flex-direction:column; gap:20px` when active

### Cards (`.card`)
- Background: #fff, border-radius: 14px, padding: 22px
- Box-shadow: `0 2px 8px rgba(0,0,0,.06)`
- No border

### Grid System
```css
.g2 { grid-template-columns: 1fr 1fr; gap: 16px; }
.g3 { grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
.g4 { grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px; }
/* @media(max-width:640px) → all collapse to 1fr 1fr */
/* @media(max-width:400px) → all collapse to 1fr */
```

### Stat Box (`.sb`)
- Background: #f8fafc, border-radius: 10px, padding: 14px
- Value: 24px weight 800 var(--navy). Delta: 12px weight 600 with `.up/.down/.flat` color

### Signal Cards (colored callout boxes)
```css
.sig-green  { background:#f0fdf4; border:1px solid #bbf7d0; }  /* body: #14532d */
.sig-yellow { background:#fffbeb; border:1px solid #fde68a; }  /* body: #78350f */
.sig-red    { background:#fef2f2; border:1px solid #fecaca; }  /* body: #7f1d1d */
.sig-blue   { background:#eff6ff; border:1px solid #bfdbfe; }  /* body: #1e3a5f */
.sig-purple { background:#f5f3ff; border:1px solid #ddd6fe; }  /* body: #4c1d95 */
```
Structure: `.signal` wrapper (flex, gap 12px) + `.icon` (20px emoji) + `.body` (13px text)

### Score Banner (Thesis tab, top of page)
```css
.score-banner {
  background: linear-gradient(135deg, #1a3a5c 0%, #0f2340 100%);
  border-radius: 14px; padding: 24px; color: #fff;
  display: flex; gap: 24px; align-items: center; flex-wrap: wrap;
}
```
- Left: 88×88 SVG score ring (same formula, but SVG includes text nodes for score number)
- Right: thesis heading (17px weight 800) + paragraph (13px rgba(255,255,255,.65)) + `.sbb-items` row
- `.sbb-item`: bg rgba(255,255,255,.1), border-radius 8px, padding 8px 12px, min-width 90px
- `.sbb-name`: 10px, rgba(255,255,255,.45), uppercase; `.sbb-val`: 15px weight 800 white; `.sbb-wt`: 10px rgba(255,255,255,.35)

### Valuation Meter Bars
```css
.meter-row { display:flex; align-items:center; gap:14px; padding:12px 0; border-bottom:1px solid #f3f4f6; }
.meter-lbl { font-size:13px; font-weight:600; color:var(--navy); width:160px; flex-shrink:0; }
.meter-track { flex:1; background:#f1f5f9; border-radius:100px; height:8px; position:relative; }
.meter-fill { height:100%; border-radius:100px; background:linear-gradient(to right,#16a34a,#d97706,#dc2626); opacity:.7; }
.meter-marker { position:absolute; top:-4px; width:2px; height:16px; background:var(--subtext); border-radius:1px; }
```
Range labels below track: 10px, color var(--muted), flex space-between.

### Scenario Cards
```css
.sc-bull { background:#f0fdf4; border:2px solid #bbf7d0; }   /* green */
.sc-base { background:#eff6ff; border:2px solid #bfdbfe; }   /* blue */
.sc-bear { background:#fef2f2; border:2px solid #fecaca; }   /* red */
```
Grid: 3 columns (1fr on mobile). Value: 24px weight 900. Label: 11px weight 700 uppercase.

### Bar Chart (industry mix, migration origins)
```css
.bar-lbl { font-size:12px; color:var(--subtext); width:140px; text-align:right; }
.bar-track { flex:1; background:#f1f5f9; border-radius:4px; height:10px; }
.bar-fill { height:100%; border-radius:4px; background:#1a7ff0; }
.bar-val { font-size:12px; font-weight:600; color:var(--text); width:60px; }
```

### Comparables Table
```css
.comp-table th { font-size:11px; font-weight:700; uppercase; letter-spacing:.06em; color:var(--muted); border-bottom:1px solid var(--border); }
.comp-table td { font-size:13px; padding:9px 10px; border-top:1px solid #f3f4f6; }
.comp-table .hl td { background:#eff6ff; }   /* highlighted "this county" row */
```
Tags: `.tag-g` bg #dcfce7 color #15803d / `.tag-y` bg #fef3c7 color #92400e / `.tag-r` bg #fee2e2 color #b91c1c

### CTA Buttons
```css
.cta-p { background:var(--blue); color:#fff; }         /* primary */
.cta-s { background:#fff; color:var(--navy); border:1.5px solid var(--border); } /* secondary */
/* Both: border-radius 10px, padding 13px, font-size 14px weight 700, flex:1 min-width:150px */
```

### Sparklines
- SVG polyline, stroke #1a7ff0 (nominal) or #16a34a dashed (real/adjusted)
- Gradient fill under nominal line using linearGradient with stop-opacity fade to 0
- Height: 72px for full charts, 45px for mini trend lines
- Labels below: 10px, color var(--muted), flex space-between

---

## Front Page Design (index.html)

**The county report pages use the Harvard template. The front page (index.html) must match the feel of the original Civica MA app screenshots.** Same brand colors and fonts — different layout pattern: marketing landing page, not a report.

### Overall Page Structure (top to bottom)

1. **Sticky white nav**
2. **Dark navy hero** — full-width, headline + search + floating score card preview
3. **"The Problem" section** — light gray bg, centered headline, 3-column feature cards
4. **"How It Works" section** — white bg, 3-step flow
5. **"What You Get" section** — light gray bg, 2-column feature cards with badge tags
6. **Top Counties table** — white bg, sortable, filterable
7. **Email capture / CTA strip**
8. **Footer**

---

### 1. Nav
- White background, no border-bottom (or very subtle), height ~52px, sticky
- Left: Civica logo (same SVG + logotype as county reports)
- Right: hamburger menu icon (☰) — mobile-first nav, no inline links at this stage
- Same nav as county reports — consistent across site

---

### 2. Hero Section
**Reference: Screenshot 1 (the MA app hero)**

- Full-width, background: var(--navy) `#1a3a5c`
- Max-width inner container: ~960–1100px, centered, padding 60px 24px
- Layout: two-column flex — left = text + search, right = floating score card

**Status pill** (above headline):
```
Now live · 2,820 counties scored
```
Small gray pill: bg rgba(255,255,255,.1), border rgba(255,255,255,.15), text rgba(255,255,255,.6), font 12px, border-radius 100px, padding 5px 14px

**Headline** — very large, font-weight 900, line-height 1.0:
```
Know before          ← color: #fff
you buy.             ← "you" in #fff, "buy." in var(--blue) #1a7ff0
```
Font-size: ~56–68px on desktop, scales down on mobile. The blue accent word is the key brand moment — never change it.

**Sub-headline**: 16–17px, color rgba(255,255,255,.65), line-height 1.6, max-width ~440px:
> "Civica scores every US county on affordability, economic strength, market dynamics, quality of place, climate risk, and population growth — the intelligence layer missing from every home search."

**Search bar**:
- White background, border-radius 100px (pill shape), height ~52px, width 100% of left column
- Left: 🔍 search icon (gray, inside the pill)
- Placeholder: "Search your county or state..."
- Box-shadow: `0 4px 20px rgba(0,0,0,.25)`
- On focus: border 2px solid var(--blue)
- Powered by `index.json` — autocomplete dropdown shows top 5 matching counties as user types

**Secondary CTA** (below search bar):
```
See all counties →
```
White bg, navy text, border-radius 100px, padding 12px 24px, font-weight 700, font-size 14px

**Floating Score Card** (right column):
- White card, border-radius 16px, box-shadow `0 8px 40px rgba(0,0,0,.3)`, padding 20px, min-width ~200px
- Shows a real top-scoring county (e.g., Hamilton County IN — the #1 county)
- Card structure:
  - County name (bold, 16px, var(--navy)) + state + pop
  - Small score ring (60px) in top-right corner showing score (e.g., 69)
  - Label badge pills: market label (e.g., "ACCELERATING" in green) + maybe 1–2 signal pills
  - 3 metric rows with colored bar and value: Affordability, Economic Vitality, Quality of Place
  - "View Full Report →" — blue pill button at bottom
- This card should feel like a teaser of what every county page looks like

---

### 3. "The Problem" Section
**Reference: Screenshots 1 bottom + Screenshot 2 top**

- Background: var(--bg) `#f0f2f5` (light gray)
- Padding: 80px 24px

**Eyebrow**: `THE PROBLEM` — 11px, font-weight 700, letter-spacing .12em, uppercase, color var(--muted), text-align center, margin-bottom 16px

**Headline** — very large, centered, font-weight 900, color var(--navy), font-size ~40–48px:
> "Home search tools tell you the price.  
> Nobody tells you if the county works."

**Sub-text**: centered, 15–16px, color var(--subtext), line-height 1.7, max-width 540px, margin auto:
> "You're about to make the biggest financial decision of your life. Your agent doesn't know if the local economy is growing. Zillow doesn't show you who's moving in. Nobody tells you the real climate risk — until after you close."

**3-column feature card row** (white cards, light border or slight shadow):
| Card | Emoji | Title | Body |
|---|---|---|---|
| 1 | 🏛️ | Is the local economy getting stronger? | Wage growth, sector quality, income growth — none of this appears on a listing. |
| 2 | 📈 | Is the housing market peaking or just starting? | FHFA appreciation trend, inventory tightness, permit pipeline. Civica shows the data. |
| 3 | 🔥 | What's the real climate and cost risk? | Flood claims, storm damage, wildfire exposure — the insurance crisis is already here in some counties. |

Card style: white bg, border-radius 12px, padding 22px, border 1px solid var(--border). Emoji: 28px. Title: 15px weight 700 var(--navy). Body: 13px var(--subtext) line-height 1.6.

---

### 4. "How It Works" Section

- Background: #fff
- Padding: 80px 24px

**Eyebrow**: `HOW IT WORKS`

**Headline**: "From search to decision in 3 steps" — large, centered, font-weight 900

**3-step horizontal flow**:
1. **Search your county** — type a county name or browse the map
2. **Read the 6-dimension breakdown** — affordability, economy, market dynamics, place quality, climate risk, population momentum
3. **Make a data-backed decision** — BUY / HOLD / AVOID verdict with full reasoning

Step style: centered column, number circle (40px, bg var(--blue), white text weight 800), title (16px weight 700), body (14px var(--subtext)).

---

### 5. "What You Get" Section
**Reference: Screenshot 3**

- Background: var(--bg) `#f0f2f5`
- Padding: 80px 24px

**Eyebrow**: `WHAT YOU GET`

**Headline**: "Everything your agent doesn't know" — large, centered, font-weight 900

**Sub**: "Six research dimensions. One composite score. Built for buyers who do their homework." — centered, var(--subtext)

**2-column card grid** (white cards with light border):

| Card | Icon | Title | Tag | Body |
|---|---|---|---|---|
| 1 | 📊 | Civica Score (0–100) | `CORE FEATURE` (green) | A single composite score derived from 6 weighted research dimensions. Instantly comparable across all 2,820 scored counties. |
| 2 | 🏠 | Affordability Analysis | `PROPRIETARY METRIC` (blue) | Price-to-rent ratio, buy-vs-rent breakeven horizon, and price-to-income — the metrics that tell you if the price is actually defensible. |
| 3 | 📈 | Market Dynamics | `FHFA DATA` (blue) | 3-year appreciation trend plus current momentum from FHFA. Two independent price signals to cross-validate whether the market is accelerating or topping. |
| 4 | 💡 | Investment Thesis | `NO SPIN` (gray) | Every county report opens with a plain-English summary of what the data says — the strengths, the risks, and the verdict. No agent spin. |

Tag badge style: 10px, font-weight 700, uppercase, border-radius 100px, padding 3px 10px:
- `CORE FEATURE`: bg #dcfce7, color #15803d
- `PROPRIETARY METRIC`: bg #dbeafe, color #1d4ed8
- `FHFA DATA`: bg #dbeafe, color #1d4ed8
- `NO SPIN`: bg #f3f4f6, color #4b5563

---

### 6. Top Counties Table

- Background: #fff
- Padding: 60px 24px
- **Eyebrow**: `TOP COUNTIES`
- **Headline**: "The best markets right now" — large, centered or left-aligned

Table: score, county, state, label badge, median home value, HPI 3yr, avg wage — sortable columns. Filter strip above: by label (ACCELERATING / PEAKING / ESTABLISHED / etc.) + state dropdown. Default sort: score descending, show top 25. "Load more" button or pagination.

---

### 7. Email Capture Strip

- Background: var(--navy) `#1a3a5c`
- Centered, padding 60px 24px
- Headline: "Get notified when scores update" (white, weight 800, 24px)
- Sub: "Quarterly re-score as new FHFA, BLS, and IRS data releases." (rgba(255,255,255,.65))
- Email input + "Notify Me" button inline (Formspree endpoint)

---

### 8. Footer

- Background: #111827 (near-black, darker than navy)
- 11px, color rgba(255,255,255,.4), line-height 1.8
- Data sources listed: IRS SOI · FHFA HPI · BLS QCEW · BEA · FBI NIBRS · FEMA NFIP · NOAA · USFS · USDA RUCC · HUD FMR · Census · Zillow ZHVI
- Disclaimer: "Scores are for informational purposes only. Not financial or investment advice."
- "civica" logotype in white + blue "ca"

---

### Front Page Typography Scale
- Hero headline: 56–68px, weight 900, line-height 1.0
- Section headline: 36–48px, weight 900, color var(--navy)
- Eyebrow labels: 11px, weight 700, letter-spacing .12em, uppercase, color var(--muted)
- Card titles: 15–16px, weight 700, color var(--navy)
- Body text: 13–15px, color var(--subtext), line-height 1.6–1.7
- Same font stack as county reports: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`

---

## The 6 Dimensions

### 1. Affordability & Value — 25 points
*Is the price defensible relative to what you're getting?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Price-to-Rent Ratio | 30% | Zillow ZHVI ÷ HUD FMR×12 | National norm: 15–18x |
| Price-to-Income Ratio | 30% | Zillow ZHVI ÷ BEA per capita income | Per-capita norm: ~2.5–3x (NOT the 4.2x household-income norm) |
| Buy vs. Rent Breakeven | 25% | Down payment (20%) ÷ (monthly PITI − HUD FMR) × 12 | Shorter = stronger buy case |
| Appreciation Quality | 15% | FHFA 3-yr avg annual HPI change | Penalizes deviation from 3–7% healthy range |

**Note:** Utility Burden (EIA) was the original spec'd metric for the 15% slot. The EIA data maps to utility territories, not county FIPS — a spatial join would be needed to aggregate to county level. Appreciation Quality from FHFA is used instead as a defensible federal-data substitute. The breakeven assumes 7% 30-yr fixed (2024 national rate), 1.2% property tax, 0.5% insurance, 20% down; capped at 30 years.

**P/I benchmark warning:** Civica uses BEA per capita personal income (~$67k national avg). The commonly cited "4.2x historical norm" uses median household income (~$80k). Civica's displayed P/I ratios will appear ~1.5–1.8× higher than standard benchmarks. County report pages must include a footnote: "P/I uses BEA per capita personal income; the commonly cited 4.2× norm uses median household income." Per-capita historical norm ≈ 2.5–3.0×. Scoring is unaffected (all counties use same base); display requires the caveat.

### 2. Economic Vitality — 22 points
*Is the local economy growing in real terms?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Wage Level | 35% | BLS QCEW avg annual wage | Higher wage = stronger labor market |
| Sector Quality | 25% | BLS QCEW employment-weighted NAICS quality score | Professional/Finance premium |
| Economic Diversity (HHI) | 25% | BLS QCEW NAICS Herfindahl Index | Lower HHI = more diversified |
| Income Growth | 15% | BEA CAINC1 per-capita income, 4-yr growth | Rising = improving real incomes |

**Note:** Business Formation Rate (Census CBP CAGR) and Fiscal Capacity (Census STC) were the original spec'd metrics for the 25%/15% slots. Census STC is published at the state level only — county-level fiscal capacity cannot be derived from it. CBP is a point-in-time count without a prior-year comparison in the downloaded file. BLS QCEW Sector Quality and BEA Income Growth are used as defensible federal-data substitutes.

**Sector quality weights by NAICS (applied to employment share in sector_quality score):**
- Professional/Scientific/Technical (NAICS 54): × 1.30
- Finance & Insurance (NAICS 52): × 1.30
- Healthcare (NAICS 62): × 1.00
- Education (NAICS 61): × 1.00
- All other private sectors: × 1.00 (neutral)
- Construction (NAICS 23): × 0.80 (leading indicator but cyclical)
- Retail (NAICS 44-45): × 0.60 (secular decline risk)
- Legacy Manufacturing (NAICS 31-33): × 0.60

**Important:** These multipliers are Civica editorial judgments, not sourced from a specific academic study or BLS framework. They reflect general US wage and employment-share trends. They should be clearly labeled as analytical choices, not established facts, in any external communication. See METHODOLOGY.md §14.6.

### 3. Housing Market Dynamics — 20 points
*What is the market actually doing?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| 3-Year Appreciation Trend | 35% | FHFA HPI 3-yr avg annual change | Sustained appreciation = strong underlying demand |
| Current Momentum | 15% | FHFA HPI latest annual change | Same FHFA source — two time horizons, not independent signals |
| Supply Tightness | 30% | Zillow active inventory (latest month) | Raw listing count — NOT months of supply (see limitation below) |
| Permit Pipeline | 20% | Census BPS new housing units permitted | Higher = supply responding to demand |

**Note:** Original spec called for Permit Gap Ratio (permits ÷ net new households), Supply Elasticity (permit trend vs. price trend), and Rent Trend (HUD FMR YoY change). HUD FMR is a single vintage file (FY2026) with no prior-year comparison in the download. The four metrics above use all available downloaded data and two independent FHFA price signals (trend + momentum) to cross-validate appreciation.

**Permit Pipeline limitation:** Higher permits = better is a known approximation. It double-counts demand signals already captured in the appreciation trend and inventory metrics, and inflates scores for Sun Belt build-heavy markets (Phoenix, Houston suburbs) regardless of whether that volume represents genuine absorption or overbuilding. The correct metric is permits ÷ projected household formation (a permit-gap ratio), but that requires ACS projections, which violates the no-survey-data policy. See METHODOLOGY.md §14.1 for full discussion.

**FHFA signal correlation:** hpi_3yr_avg and hpi_latest are correlated (~0.7–0.9) by construction — they are two time-horizon views of the same FHFA trend, not independent signals. Do not describe them as "two independent FHFA signals" in any copy or documentation.

**Inventory limitation:** The downloaded Zillow file is raw listing count, not months of supply. Large counties are penalized for having more listings even when turnover rate is identical to smaller counties. Fix requires a Zillow county sales-count file (not downloaded). See METHODOLOGY.md §7 and §14.

**Appreciation tension:** Dim1 penalizes deviation from 5% annual appreciation; Dim3 rewards raw appreciation magnitude. A market at 10% appreciation is penalized by Dim1 and rewarded by Dim3. The model slightly favors momentum over stability by design. See METHODOLOGY.md §14.2.

### 4. Quality of Place — 15 points
*Is it a good place to actually live?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Crime Rate | 35% | FBI NIBRS 2024 | Violent offenses per 100k residents (lower = better); counties without NIBRS coverage receive their RUCC-tier median |
| Urban Access | 40% | USDA RUCC 2023 | Percentile rank of continuum: 1 (large metro) → 9 (most rural) |
| Amenity Density | 25% | Census CBP 2023 | Private establishments per 1,000 residents |

**Note:** Original spec also called for School Adequacy (NCES — not downloaded) and Service Efficiency (Census STC — state-level only, no county FIPS). FBI NIBRS 2024 National Master File (5.8 GB fixed-width) was successfully parsed by empirically decoding the record layout: BH (agency header) segments contain state alpha at positions 4–6 (chars 3-4 of ORI) and county 3-digit FIPS at positions 269–272; 02 (offense) segments carry the NIBRS offense code at positions 33–36. This covers 21,068 agencies across 49 states and 2,869 counties. Counties not covered by participating agencies (predominantly rural) are imputed with their RUCC-tier median violent crime rate so non-reporting isn't mistaken for low crime.

### 5. Physical Risk — 12 points
*What are the climate and natural hazard costs?*

**Note: FEMA NRI was not downloadable. Physical Risk is scored using the three proxy datasets below — the same underlying data FEMA uses to build its NRI.**

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Flood Loss Proxy | 40% | FEMA NFIP paid claims ÷ Census population | 10-yr avg claims per capita |
| Storm Damage Proxy | 35% | NOAA Storm Events property damage ÷ population | 5-yr avg damage per capita |
| Wildfire Exposure | 25% | USFS Wildfire Risk to Communities score | County-level exposure index |

**Composite Physical Risk Index (for scoring engine):**
```
Physical Risk Index =
  NFIP loss ratio percentile (inverted)    × 0.40
+ NOAA storm damage per household pct      × 0.35
+ Wildfire risk score percentile           × 0.25
```
Lower score = safer. Invert the percentile so high-risk counties score low.

**Insurance cost output (for monthly cost model):**
National median homeowners insurance ≈ $159/mo. Apply county risk multiplier:
- Low-risk county (score 85): $159 × 0.72 = ~$115/mo
- High-risk county (score 22): $159 × 2.10 = ~$334/mo

### 6. Population Momentum — 6 points
*Are the right people moving in?*

| Metric | Weight | Source | Formula |
|---|---|---|---|
| Net Migration Rate | 60% | Census Population Estimates 2025 | RNETMIG2025 (aliased to RNETMIG2023 internally): net migration per 1,000 residents |
| Income Quality of In-Movers | 40% | IRS SOI Migration 2022-2023 | in-mover avg AGI ÷ out-mover avg AGI; ratio > 1.0 = higher-income arrivals |

**Note on framing:** Migration is a *corroborating* signal, not a leading indicator. The 6% weight is correct — migration confirms conclusions established by Dim1–Dim3, it does not independently predict them. Do not describe it as "the strongest leading indicator" anywhere in copy or documentation.

---

## The 8 Derived Metrics

These are Civica's proprietary analytical layer — computed from raw federal data, not available on any other consumer platform.

| Metric | Formula | National Norm | Source Data |
|---|---|---|---|
| **Price-to-Rent Ratio** | Zillow ZHVI ÷ (HUD FMR × 12) | 15–18x | Zillow + HUD |
| **Buy vs. Rent Breakeven** | Down payment (20%) ÷ ((monthly PITI − HUD 2BR FMR) × 12) | 3–7 years | Zillow + HUD; assumes 7% 30yr, 1.2% tax, 0.5% insurance; cap 30yr |
| **Appreciation Quality** | \|FHFA 3-yr avg annual HPI − 5%\| (deviation from healthy midpoint) | 0 deviation = ideal | FHFA HPI county |
| **Supply Tightness** | Zillow active inventory, latest month (percentile-inverted nationally) | Lower = tighter | Zillow |
| **Sector Quality Score** | Σ(employment share × NAICS quality weight) across private supersectors | 1.00 = neutral mix | BLS QCEW |
| **Employment Concentration (HHI)** | Σ(industry employment share²) × 10,000 across NAICS codes | <1,500 = diversified | BLS QCEW |
| **In-Mover Income Quality** | IRS in-mover avg AGI ÷ IRS out-mover avg AGI | 1.0 = neutral | IRS SOI Migration |
| **Physical Risk Score** | NFIP claims/capita (40%) + NOAA storm damage/capita (35%) + USFS wildfire rank (25%); all percentile-inverted | Lower = safer | FEMA NFIP + NOAA + USFS + Census |

---

## The 8 Market Labels

Every county gets exactly one label based on its 6-dimension score profile.

| Label | Score Profile | Buyer Guidance |
|---|---|---|
| **ACCELERATING** | Affd ≥60, Econ ≥65, MktDyn ≥70, QoP ≥60, Risk ≥50, Pop ≥65 | Strongest long-term hold. All signals positive. Window still open. |
| **PEAKING** | Strong scores but MktDyn declining (P/R >22x, permit gap <0.4) | Great now. Fundamentals softening. Buying the peak story. |
| **TURNING** | Affd + QoP strong, MktDyn + Pop reversing positively | Quality market that market hasn't re-discovered. Early signal. |
| **ESTABLISHED** | Strong Affd + QoP, low Momentum, stable | Solid and stable. Buy for lifestyle, not appreciation. |
| **EMERGING** | Econ + Pop strong, Affd + QoP below average | High-conviction early mover. Demand and fundamentals rising. Risk real. |
| **SPECULATIVE** | High MktDyn, weak fundamentals (P/R >25x, EAL high) | Demand outrunning quality. Classic trap. |
| **FRONTIER** | Pop + Econ signals early-positive, Affd + QoP weak | Everything early. High risk, high upside if fundamentals materialize. |
| **AVOID** | Multiple dimensions weak with no positive momentum | Nothing working in any direction. |

**Label trigger thresholds (total score cutoffs):** ACCELERATING ≥68, PEAKING ≥62, ESTABLISHED ≥55, EMERGING ≥46, FRONTIER ≥38, TURNING ≥30, SPECULATIVE ≥26, AVOID ≥0.

**Threshold calibration note:** Percentile normalization (mean≈50, std≈7.7, range 23–73) bounds scores within the actual data distribution. Original thresholds of 78 and 18 were unreachable: no county ever scored above 73.09 or below 22.85. The recalibrated thresholds above are derived from the empirical distribution and ensure all 8 labels fire with meaningful county counts.

---

## Monthly Cost Model (implemented in scoring engine)

The scoring engine computes `monthly_piti` for each county — the ownership cost used in the breakeven calculation.

| Component | Source | Method |
|---|---|---|
| Mortgage (P&I) | Zillow ZHVI median home value | 30-yr fixed at 7% (2024 national rate), 20% down |
| Property Tax | Hardcoded 1.2% annual rate | National median effective rate; NOT county-specific |
| Homeowner Insurance | Hardcoded 0.5% annual rate | National median; not risk-adjusted per county |

**Property tax is a known simplification.** Effective rates range 0.28% (HI) to 2.23% (NJ, IL, VT). At $400k, the monthly error is up to $340 vs. the hardcoded $400. Users in IL, NJ, TX, WI, NH should adjust mentally. State-level rates from the Lincoln Institute of Land Policy are a candidate improvement for v1.3. See METHODOLOGY.md §14.5.

**Note:** Full all-in cost breakdown (electricity, gas, maintenance) is intended for county report cards via `county_generator.py` and is not yet implemented. EIA electricity maps to utility service territories, not county FIPS. NOAA Climate Normals (station-level, no county FIPS) would require a spatial join to derive heating/cooling degree days. Both are documented future enhancements.

---

## Data Sources (18 Datasets on Disk)

| # | Dataset | File | Status | Used For |
|---|---|---|---|---|
| 1 | IRS SOI Migration | irs_migration/ | ✓ Active | Dim6: in-mover income quality ratio |
| 2 | FHFA HPI County | fhfa_hpi/hpi_at_county.xlsx | ✓ Active | Dim1: appreciation quality; Dim3: 3-yr trend + current momentum |
| 3 | BLS QCEW | bls_qcew/2023.annual.singlefile.csv (2024 pending) | ✓ Active | Dim2: wages, sector quality, HHI |
| 4 | BEA Local Area (CAINC1) | bea_income/CAINC1__ALL_AREAS_1969_2024.csv | ✓ Active | Dim1: price-to-income; Dim2: income growth |
| 5 | FBI NIBRS | fbi_crime/2024_NIBRS_NATIONAL_MASTER_FILE.txt | ✓ Active | Dim4: violent offenses per 100k (21,068 agencies, 49 states, 2,869 counties) |
| 6 | FEMA NFIP Claims | fema_nfip/fema_nfip_claims.csv | ✓ Active | Dim5: flood loss per capita (10-yr window) |
| 7 | NOAA Storm Events | noaa_storm_events/ (5 CSVs, 2020–2024) | ✓ Active | Dim5: storm damage per capita (5-yr window) |
| 8 | USFS Wildfire Risk | usfs_wildfire/wrc_download_20260415.xlsx | ✓ Active | Dim5: wildfire national risk rank |
| 9 | EIA Form 861 | eia_electricity/ (3 files) | ✗ Not used | Maps to utility service territories, not county FIPS; spatial join required |
| 10 | EIA Natural Gas | eia_gas/NG_PRI_SUM_DCU_NUS_A.xls | ✗ Not used | State-level prices only; no county-level decomposition in file |
| 11 | Census STC | census_stc/STC-Historical-DB.xlsx | ✗ Not used | State-level data only — no county FIPS in file |
| 12 | Census Population Estimates | census_population/co-est2025-alldata.csv | ✓ Active | Base county universe; migration rates; per-capita denominators |
| 13 | Census BPS | census_bps/co2025a.txt | ✓ Active | Dim3: new housing supply pipeline |
| 14 | Census CBP | census_cbp/cbp23co.txt | ✓ Active | Dim4: amenity density (establishments per 1,000 residents) |
| 15 | USDA RUCC | usda_rucc/ruralurbancodes2023.xlsx | ✓ Active | Dim4: urban access continuum (1=large metro, 9=most rural) |
| 16 | HUD Fair Market Rents | hud_fmr/FY26_FMRs_revised.xlsx | ✓ Active | Dim1: rent baseline, P/R ratio, breakeven |
| 17 | NOAA Climate Normals | noaa_climate_normals/ | ✗ Not used | Station-level temperature; no county FIPS; spatial join required |
| 18 | Zillow ZHVI | zillow/ | ✓ Active | Dim1: median home value; Dim3: active inventory |

**FEMA NRI was not downloadable. Physical Risk uses datasets 6, 7, 8 — the same underlying hazard data FEMA uses to build its NRI.**

**Active datasets: 11 of 18 (datasets 1–4, 5, 6–8, 12–16, 18). Total data cost: $0. No ACS survey data.**

**Note on Zillow:** Zillow ZHVI is not federal data. It is the only non-federal source in the model, used because no federal dataset provides county-level median home values at monthly granularity. FHFA HPI is used for all appreciation signals; Zillow is used only for the price level and inventory count.

---

## Known Data Limitations

| Issue | Dataset | Impact | Current Handling |
|---|---|---|---|
| FHFA covers ~2,800 of 3,143 counties | FHFA HPI | ~340 rural counties missing appreciation data | National median imputed; reduces score slightly for FHFA-absent counties |
| CBP has 18-month publication lag | Census CBP | Establishment data ~2 years behind | Accepted; no alternative county-level source available |
| Small county distortion | All | 1 employer can swing all metrics | 324 counties under 5,000 pop excluded entirely — no imputed scores |
| Zillow coverage gaps → ratio bias | Zillow ZHVI | Imputing national median home value (~$350k) into a rural county with $600 FMR rents creates P/R of 48.6x — far above the actual ratio if real home values are $120–150k | Known limitation; flagged in output; correct fix is to impute P/R directly from similar-RUCC counties, not the numerator alone |
| NIBRS coverage gaps | FBI NIBRS | ~251 counties lack a participating agency (rural) | RUCC-tier median violent crime rate imputed; non-reporters not penalized |
| NFIP only captures insured flood losses | FEMA NFIP | Uninsured flood damage not counted | NOAA Storm Events covers all storm types; combined with NFIP |
| Property tax hardcoded at 1.2% | Monthly cost model | Actual effective rates: 0.28% (HI) to 2.23% (NJ/IL); error up to $340/mo at $400k home value | Accepted simplification; displayed breakeven should carry a high-tax-state disclaimer |
| Appreciation target not inflation-adjusted | FHFA HPI (Dim1) | 5% nominal = −3% real at 8% inflation (2022); penalizes counties near healthy real target during high-inflation periods | Documented limitation; CPI adjustment is a candidate for v1.3 |
| Inventory is raw count not months of supply | Zillow inventory | Large counties penalized for having more listings even when market tightness is identical to smaller counties | Data gap — fix requires Zillow county sales-count file (not downloaded); document on county pages |
| P/I uses per capita income; norm uses household income | BEA + all Dim1 display | Displayed P/I ratios appear 1.5–1.8× higher than industry standard; confuses users comparing to "4.2× norm" | Add footnote on county report pages; scoring unaffected; per-capita norm ≈ 2.5–3.0× |
| IRS AGI includes capital gains; retirement bias | IRS SOI Migration | FL/AZ/NV/SC retirement counties show inflated in-mover income quality due to one-time capital gains realizations at retirement | Documented limitation; wage-only income is available in SOI and is a candidate fix for v1.3 |
| Zillow drives ~27% of total score | Zillow ZHVI + inventory | Single non-federal source has highest data concentration in model; methodology risk if Zillow changes access or format | Monitor file availability each run; no federal alternative at monthly county granularity |
| EIA and Census STC not county-level | EIA, STC | Utility burden and fiscal capacity not scored | Documented as not implemented; appreciation quality and income growth used instead |

---

## Scoring Algorithm

### What Is Defined
- 6 dimensions with precise weights (25/22/20/15/12/6 = 100 total)
- All metrics within each dimension with intra-dimension weights
- Formulas for all 8 derived metrics
- 8 market labels with qualitative trigger conditions
- Monthly cost calculation methodology

### What Is Resolved (scoring engine v1.1 COMPLETE)

1. **Normalization method** — percentile rank: `pct(s) = s.rank(pct=True) * 100`, inverted where lower=better (`pct_inv`)
2. **Label trigger thresholds** — ACCELERATING ≥68, PEAKING ≥62, ESTABLISHED ≥55, EMERGING ≥46, FRONTIER ≥38, TURNING ≥30, SPECULATIVE ≥26, AVOID ≥0 (all 8 labels fire)
3. **National distribution** — mean≈50.0, std≈7.7 by construction of percentile normalization; empirical range 23–73
4. **Edge cases** — missing data filled via left join from population base; counties with no FHFA or QCEW data receive NaN for those dimensions, which reduces their total score proportionally
5. **Sector weights** — only NAICS codes specified in the model (54, 52, 62, 61, 23, 44-45, 31-33); all other sectors neutral (1.00×)
6. **Dim3** — uses two independent FHFA HPI signals (3yr trend + latest) plus Zillow inventory and Census permits; `inmover_income_ratio` moved exclusively to Dim6 where it belongs
7. **Dim6** — net migration rate 60% + in-mover income quality 40%, matching spec intent exactly

---

## File Structure

```
Civica Harvard Model/
├── CLAUDE.md                          ← This file — project bible
├── LAUNCH_TODO.md                     ← Full launch checklist (security, SEO, features)
├── README.md                          ← GitHub readme
├── LICENSE                            ← MIT
├── .gitignore                         ← Excludes civica_data/ and county_scores.csv
├── harvard_county_profile.html        ← County report template (THE design)
├── harvard_model.html                 ← Methodology page (THE design)
├── civica_data_downloader_v4.py       ← Downloads all datasets to civica_data/
├── scoring_engine.py                  ← COMPLETE — scores all 2,820 counties
├── county_scores.csv                  ← COMPLETE — 2,820 rows × 36 cols (on disk, not in git)
├── civica_data/                       ← All datasets on disk (~7 GB, not in git)
│   ├── bea_income/
│   ├── bls_qcew/
│   ├── census_bps/
│   ├── census_cbp/
│   ├── census_population/
│   ├── census_stc/
│   ├── eia_electricity/
│   ├── eia_gas/
│   ├── fbi_crime/
│   ├── fema_nfip/
│   ├── fhfa_hpi/
│   ├── hud_fmr/
│   ├── irs_migration/
│   ├── noaa_climate_normals/
│   ├── noaa_storm_events/
│   ├── usda_rucc/
│   ├── usfs_wildfire/
│   └── zillow/
└── [next to build]
    ├── county_generator.py            ← Produces one HTML per county from template
    └── index.html                     ← Front page (search, filter, browse)
```

**Versioning rule:** Never overwrite existing HTML files. New versions get incremental names (county_profile_v2.html, etc.).

---

## The Data Pipeline

`civica_data_downloader_v4.py` was the final download run. All 18 datasets are on disk in `civica_data/`. No further downloads needed.

**All data is at:** `C:\Users\Brian\Desktop\Civica Harvard Model\civica_data\`

**FEMA NRI status:** Not downloaded — site blocked all automated and manual attempts. Physical Risk dimension uses FEMA NFIP + NOAA Storm Events + USFS Wildfire as proxies instead. These are the same source datasets FEMA uses internally to produce the NRI, so coverage is equivalent.

---

## Coding Rules

- Static HTML/CSS/JS — no backend required until payment layer
- Python for all data pipeline scripts
- Always set UTF-8 in Python: `sys.stdout.reconfigure(encoding='utf-8')`
- Never use `$matches` in PowerShell
- No mock data in production — every number must trace to a federal source
- Design system CSS variables must never be hardcoded inline
- Tab switching uses the `showTab(name)` pattern from harvard_county_profile.html

---

## Never Do These Things

- No agent advertising integrations — ever. This destroys the trust moat.
- No survey data (ACS excluded — administrative equivalents exist for everything)
- No proprietary data sources — every metric must be replicable from free federal data
- No overwriting existing versioned HTML files
- No Redfin, MLS, or agent-affiliated listing data — these introduce conflict of interest; Zillow ZHVI (home value index, not listings) is the sole exception and is used only where no federal equivalent exists at county level
- No hardcoded county-specific values in the template files (data must be injected)

---

## Competitive Positioning

| Feature | Civica | Zillow | Redfin | Niche |
|---|---|---|---|---|
| Federal-data-first (one non-federal source: Zillow ZHVI for price levels only) | Yes | No | No | Partial |
| No agent advertising | Yes | No | No | No |
| Price-to-rent ratio | Yes | No | No | No |
| Buy vs. rent breakeven | Yes | No | No | No |
| Real vs. nominal appreciation | Yes | No | No | No |
| Permit gap analysis | Yes | No | No | No |
| Bull/base/bear scenarios | Yes | No | No | No |
| Risk matrix with probabilities | Yes | No | No | No |
| All 3,143 US counties | Yes | Partial | Partial | Yes |

---

## Monetization (Do Not Deviate)

- Phase 1: Fully free. Build trust and reputation.
- Phase 2 (6-12 months): Lender referral partnerships. Transparent disclosure, no score influence.
- Phase 3 (12+ months): Premium tier — $99-149/yr or $9-14/report for full breakdown.
- Phase 4 (18+ months): B2B data licensing to relocation companies.

**Never:** Introduce agent advertising. It destroys the only thing that separates Civica from Zillow.
