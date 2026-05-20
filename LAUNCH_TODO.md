# Civica 2.0 — Launch To-Do List
*Full roadmap from current state → live, trafficked, monetized product*

---

## Where Things Stand Right Now

| Done | Item |
|---|---|
| ✅ | Scoring engine — 2,820 counties scored, `county_scores.csv` complete (mean=50.0, std=6.24, range 26.9–69.5) |
| ✅ | FBI NIBRS 2024 integrated — violent crime per 100k in Dim4; 21,068 agencies, 49 states, 2,869 counties |
| ✅ | All 14 datasets active (13 federal + Zillow) — no placeholders or imputed dimensions |
| ✅ | County report template — `harvard_county_profile.html` |
| ✅ | Methodology page — `harvard_model.html` |
| ✅ | GitHub repo — Civica-2.0 initialized |
| ✅ | County page generator — `county_generator.py`; 2,820 pages with SEO meta, OG tags, JSON-LD, compare button |
| ✅ | State pages — 51 pages at `output/states/{ST}.html` with county rankings + SEO |
| ✅ | `output/index.json` — 2,820 records for front-page search/filter |
| ✅ | Sitemap — `sitemap.xml` at root; 2,874 URLs (homepage + leaderboard + compare + counties + states) |
| ✅ | Front page (`index.html`) — real data from index.json, search, sort, filter, mobile nav, email form |
| ✅ | Compare feature (`compare.html`) — URL params, dimension bars, localStorage sync, share link |
| ✅ | County choropleth map — D3 + TopoJSON, AlbersUSA projection, colored by label, hover tooltip, click-to-report; replaced filter table |
| ✅ | SEO layer — unique title/desc/canonical/og/JSON-LD on every county + state page; robots.txt |
| ✅ | Security headers — `_headers` file for Cloudflare/Netlify (HSTS, CSP, X-Frame-Options, etc.) |
| ✅ | Legal pages — `privacy.html`, `terms.html`, `disclaimer.html` |
| ✅ | National leaderboard — `leaderboard.html`; Top 100, Undervalued Hidden Gems, Most Affordable, Markets to Avoid |
| ✅ | URL-based filter state — `?state=TN&label=EMERGING&sort=score` syncs as filters change; shareable |
| ✅ | Cookie consent — GDPR banner on `index.html`, `compare.html`, `leaderboard.html`; localStorage persists |
| ✅ | Leaderboard linked — nav + footer of `index.html`; nav of `compare.html`; sitemap.xml |
| ✅ | OG image — `og_image.png` (1200×630) via `generate_og_image.py`; og:image + twitter:card on all pages |
| ✅ | Saved counties — 🔖 bookmark column on front-page table; 📌 floating pill; `civica_saved` localStorage |
| ✅ | Reset filters button — appears when any filter is active; clears label + state |
| ✅ | "💎 Undervalued" filter — score ≥ 55 + median home ≤ $310k; front page filter strip; URL-synced |
| ✅ | Data as of date — county page footer: "Data as of Q1 2026 · BLS QCEW 2023 · FHFA Q4 2025 · NIBRS 2024" |
| ✅ | Print stylesheet — `@media print` CSS on every county page; hides nav/tabs/compare tray |
| ✅ | Empty search state — "No results for X — try a state abbreviation" instead of silent empty |
| ⬜ | GA4 analytics — Brian must create GA4 property → set `GA4_ID` in `county_generator.py` + uncomment in `index.html` → re-run generator |
| ⬜ | Formspree email capture — Brian must create account → set `FORMSPREE_ID` in `index.html` |
| ⬜ | Hosting, domain, CDN — Brian must purchase domain + connect to Cloudflare Pages or Netlify |
| ⬜ | Monetization wiring — Stripe setup (future) |

---

## Phase 1 — Core Build (Site Must Exist Before Anything Else)

### 1.1 County Page Generator
- [x] Write `county_generator.py` — reads `county_scores.csv`, writes one HTML file per county to `output/counties/{fips}.html`
- [x] Pull county names + state from USDA RUCC file (already on disk)
- [x] Replace all template tokens with real data (score ring, pills, dimension breakdown, thesis text, valuation metrics, scenarios, comparables)
- [x] Generate `output/index.json` — array of all 2,820 counties with score, label, name, state, key metrics — this powers the front page search and filter
- [x] Add color coding: green/yellow/red for each pill based on national percentile
- [x] Write a summary "thesis" sentence per county driven by its top 2 signal strengths and top 1 risk
- [ ] Surface crime signal on county page: add a "Safety" pill showing `violent_per100k` (from `county_scores.csv`) with national percentile context. Mark imputed counties with a small note ("Based on regional average — agency did not report to NIBRS").
- [x] Test 10 representative counties across score range before full run (check Palm Beach FL, Cook IL, Newton AR, Manhattan NY)
- [x] Run full generation — all 2,820 files

### 1.2 Front Page
- [x] Build `index.html` — the home/search/browse page
- [x] Hero section: tagline, search bar (county or state name → jumps to report)
- [x] National score map — D3 choropleth map replacing Top Counties table; AlbersUSA projection, colored by market label, hover tooltip, click navigates to county report
- [x] Top 25 counties table (sortable — by score, by price, by appreciation)
- [x] Label filter strip: click PEAKING, ESTABLISHED, EMERGING, etc. to filter the table
- [x] State filter dropdown
- [x] How It Works section (6 dimensions explained simply)
- [x] Link to `harvard_model.html` methodology page
- [x] Email capture (Formspree) — wired and ready; waiting for Brian's Formspree ID
- [x] Footer with data sources, disclaimer, links

### 1.3 Search
- [x] Client-side search powered by `index.json` (no server needed)
- [x] Search by county name (e.g., "Hamilton" shows Hamilton County IN, Hamilton County OH, etc.)
- [x] Search by state abbreviation or full name
- [x] Autocomplete dropdown — show top 6 results as user types
- [ ] "Did you mean?" for common misspellings
- [x] Empty state: "No results for X — try searching by state"

### 1.4 Filter & Ranking Table
- [x] Full sortable data table on front page (all 2,820 counties, load-more in 25-row increments)
- [x] Sort by: Total Score, Home Value, HPI 3yr Appreciation, Avg Wage
- [x] Filter by: Market Label (PEAKING / ESTABLISHED / etc.), State, Undervalued (score ≥ 55 + price ≤ $310k)
- [x] "Reset filters" button
- [x] URL reflects current filter state (`?state=TN&label=PEAKING`) — shareable/linkable
- [x] Show columns: County, State, Score, Label, Median Home Value, HPI 3yr, Avg Wage
- [ ] Mobile-responsive: collapse to card view on small screens *(currently uses horizontal scroll)*

### 1.5 Compare Feature
- [x] "Add to Compare" button on every county report page (stores up to 3 counties in localStorage)
- [x] Floating compare tray: shows selected counties + "Compare" CTA
- [x] `compare.html` — side-by-side view of 2–3 counties
- [x] Show all 6 dimension scores as bar chart comparison
- [x] Show key metrics table: price, rent, P/R ratio, breakeven, appreciation, wages, net migration, risk scores
- [x] "Share comparison" — generates a URL like `/compare?c=12099&c=18057&c=47187`
- [x] "Clear all" button

### 1.6 State Pages
- [x] One page per state: `output/states/TN.html` — 51 pages total
- [x] Shows all scored counties in that state, ranked by score
- [x] State-level summary: median score, top county, % per label
- [x] SEO-optimized — "best counties to buy a home in Tennessee" is a high-value keyword

---

## Phase 2 — Hosting & Infrastructure

### 2.1 Choose a Host (Recommendation: Cloudflare Pages)
- [ ] **Option A — Cloudflare Pages** (recommended): Free tier, global CDN, automatic HTTPS, custom domain, deploys from GitHub. Best for a static site of this scale.
- [ ] **Option B — Netlify**: Also free, similar to Cloudflare Pages. Slightly simpler setup.
- [ ] **Option C — GitHub Pages**: Free but slower CDN, no edge caching, 1GB soft limit — may struggle with 2,820 HTML files.
- [ ] Connect GitHub repo (Civica-2.0) to hosting provider
- [ ] Set up automatic deploys: every `git push` to `main` triggers a redeploy

### 2.2 Custom Domain
- [ ] Purchase `civica.com` or `usecivica.com` or `civica.io` (check availability — civica.com may be taken)
- [ ] Set DNS records: A/CNAME pointing to hosting provider
- [ ] Enable HTTPS (all hosts above do this automatically via Let's Encrypt)
- [ ] Set up `www` redirect → apex domain (or vice versa — pick one and be consistent)
- [ ] Set up `civica.com/county/12099` style routing (either folder structure in output, or hosting redirects)

### 2.3 Performance
- [ ] Verify all HTML files are under 200KB each (the template is ~47KB — should be fine)
- [x] No external fonts or scripts to preconnect (system font stack only)
- [ ] Lazy-load images (if any are added later)
- [ ] Minify `index.json` — remove whitespace, it will be downloaded by every front page visitor
- [ ] Test page load speed with Google PageSpeed Insights — target 90+ on mobile
- [x] `output/` folder structure: flat `output/counties/` + `output/states/` — not nested deeper

---

## Phase 3 — Security

*Civica is a static site — no database, no login, no server-side code. Attack surface is very small. These are the relevant hardening steps.*

### 3.1 HTTPS
- [ ] Enforce HTTPS everywhere — redirect all HTTP → HTTPS (hosting provider handles this)
- [x] HSTS header configured in `_headers`: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`

### 3.2 Security Headers
- [x] Content Security Policy — in `_headers` file; allows self + GA4 + Formspree
- [x] X-Frame-Options: DENY — in `_headers`
- [x] X-Content-Type-Options: nosniff — in `_headers`
- [x] Referrer-Policy: strict-origin-when-cross-origin — in `_headers`
- [x] Permissions-Policy: camera=(), microphone=(), geolocation=() — in `_headers`

### 3.3 Cloudflare Settings (if using Cloudflare Pages or proxy)
- [ ] Enable Cloudflare DDoS protection (free tier covers this)
- [ ] Enable Bot Fight Mode
- [ ] Set SSL/TLS mode to "Full (Strict)"
- [ ] Enable "Always Use HTTPS" rule

### 3.4 Email & Form Security (when you add Formspree)
- [ ] Formspree has spam protection built in — enable reCAPTCHA on the form
- [ ] Use Formspree's allowlist to restrict submissions to your domain only
- [x] No real email address in HTML source — form uses Formspree endpoint only

### 3.5 GitHub Repo Security
- [ ] Confirm `civica_data/` is in `.gitignore` and has never been committed (check: `git log --all -- civica_data/`)
- [ ] Enable GitHub's "Secret scanning" and "Dependabot alerts" in repo settings
- [x] No API keys, Stripe keys, or Formspree IDs committed — placeholders only in source

### 3.6 When You Add a Backend (future)
- [ ] Rate limit the compare/search API endpoints
- [ ] Validate and sanitize all user inputs (search queries, FIPS parameters)
- [ ] Use parameterized queries if you ever add a database
- [ ] Add CORS headers to allow only your domain to call your API

---

## Phase 4 — SEO

*Static HTML files are the right call — Google indexes them completely. This is a major advantage over JavaScript-rendered apps.*

### 4.1 On-Page SEO (Per County Page)
- [x] Unique `<title>` tag per page: `{County Name}, {State} Housing Market Score — Civica Research`
- [x] Unique `<meta name="description">` per page with score, label, and median home value
- [x] `og:title`, `og:description`, `og:image`, `og:url`, `twitter:card` on every page
- [x] `og:image` — `og_image.png` (1200×630) generated via `generate_og_image.py`; on all 2,820 county + 51 state pages
- [x] `<link rel="canonical">` on every page pointing to its own URL
- [x] Dataset JSON-LD structured data on every county and state page
- [x] H1 tag = county name (in template)
- [ ] Alt text on any images *(no images currently in county pages)*
- [ ] Internal links to 3 comparable counties *(deferred — requires similarity scoring pass)*

### 4.2 Site-Wide SEO
- [x] `robots.txt` — allows all crawlers, points to `https://civica.app/sitemap.xml`
- [x] `sitemap.xml` — 2,874 URLs: homepage, leaderboard, compare, all county URLs, all state URLs
- [ ] `sitemap_index.xml` — not needed; sitemap is well under 50,000 URLs
- [x] `<html lang="en">` on every page
- [x] BreadcrumbList JSON-LD on county pages: Home > {State} Counties > {County Name}

### 4.3 Google Search Console
- [ ] Create account at search.google.com/search-console
- [ ] Add property for your domain
- [ ] Verify ownership via DNS TXT record or HTML meta tag
- [ ] Submit `sitemap.xml`
- [ ] Monitor: which county pages get impressions, which keywords are driving clicks
- [ ] After 4–6 weeks: identify your top organic landing pages — double down on those states/labels

### 4.4 Google Analytics 4
- [ ] Create GA4 property
- [ ] Set `GA4_ID = 'G-XXXXXXXXXX'` in `county_generator.py` → re-run generator (all 2,820 pages get snippet)
- [ ] Uncomment GA4 snippet in `index.html`, `compare.html`, `leaderboard.html`
- [ ] Set up conversion events: `county_report_view`, `compare_initiated`, `email_signup`
- [ ] Create a GA4 audience for "visited 3+ county pages" — these are your most engaged users
- [ ] Connect GA4 to Google Search Console for combined organic + behavior data

### 4.5 Keyword Strategy
- [x] **Tier 1 — high intent, low competition**: `"{County} housing market 2026"` — 2,820 unique pages targeting these
- [x] **Tier 2 — comparison queries**: `"{County A} vs {County B}"` — compare feature built
- [x] **Tier 3 — state-level**: `"best counties to buy a home in {State}"` — 51 state pages built
- [x] **Tier 4 — methodology**: `"price-to-rent ratio by county"` — `harvard_model.html` captures these
- [ ] **Do NOT**: buy backlinks, keyword-stuff, or create pages that aren't useful to real people

### 4.6 Link Building
- [ ] List Civica on: ProductHunt, Hacker News (Show HN), Reddit r/datasets, r/dataisbeautiful
- [ ] Reach out to real estate blogs, local news sites — offer data for a story in exchange for a link
- [ ] Get listed on: AlternativeTo.net, G2 (Tools & Data category)
- [ ] Every Reddit post where you share Civica data = potential link if people cite it

---

## Phase 5 — Features Roadmap

### 5.1 Must-Have at Launch
- [x] Search (county name → report page)
- [x] State filter on front page table
- [x] Label filter (PEAKING, ESTABLISHED, etc.)
- [x] Sort by score / home value / appreciation / wage
- [x] Compare (URL-based, up to 3 counties)
- [x] Mobile-responsive layout on all pages *(horizontal scroll on table; full card collapse is post-launch)*

### 5.2 Shortly After Launch
- [ ] **Score history** — re-run engine each quarter, store historical scores, show trend line on county page ("Score 3 months ago: 61 → today: 64 ↑")
- [x] **Saved counties** — 🔖 bookmark on every table row; 📌 floating pill; `civica_saved` localStorage; clears on demand
- [ ] **Share button** — copies URL + pre-fills a tweet: "Jefferson County, CO scores 80/100 on @CivicaData — ESTABLISHED market. See the full breakdown:"
- [x] **Print / PDF view** — `@media print` stylesheet on every county page; hides nav/tabs/compare tray
- [ ] **"Near me" button** — uses browser geolocation to find closest county *(requires county centroid lat/lon file)*
- [ ] **Pagination** on front page table — show 50/100/250 at a time *(currently load-more in 25-row steps)*

### 5.3 Growth Features (Post-Launch, Once You Have Traffic)
- [ ] **Email alerts** — "Notify me if {county} score changes by more than 5 points" — user enters email, you send on quarterly re-score
- [ ] **Embed widget** — `<iframe src="civica.com/widget/12099">` — a compact score card any real estate agent can embed on their site. Drives backlinks.
- [ ] **API** — `GET /api/county/{fips}` returns JSON of all scores. Paid access via API key. Targets proptech developers.
- [x] **National leaderboard** — `leaderboard.html`: Top 100, Undervalued Hidden Gems, Most Affordable, Markets to Avoid
- [x] **"Undervalued" filter** — score ≥ 55 + below-median home value (≤ $310k); on front page filter strip + leaderboard
- [ ] **Metro area aggregation** — group counties into MSAs (Dallas-Ft Worth = Collin + Dallas + Tarrant + Denton counties). Show composite metro score.
- [ ] **School data** — download NCES F-33 and EDFacts (not yet in the data pipeline). Adds to Quality of Place dimension. Major differentiator.

### 5.4 Monetization Features
- [ ] **Paywall for full report** — free: score + label + 2 pills. Paid ($5 one-time or $15/month): all 6 tabs (Valuation, Supply & Demand, Scenarios, Fundamentals, Risk, Comparables). Implement with Stripe + a cookie/token system.
- [ ] **"Civica Pro" for agents** — $49/month: unlimited full reports, branded PDF export, bulk CSV download of scores for any state
- [ ] **Featured Agent slot** — one real estate agent per county/state, shown on the county report page. $200–800/month per market.
- [ ] **Stripe integration** — set up Stripe account, create a product for one-time report unlocks and subscriptions
- [ ] **Free tier limits** — make the paywall feel fair: show the score ring and market label for free, require payment only for the analytical depth

---

## Phase 6 — Legal & Compliance

### 6.1 Pages to Build
- [x] **Privacy Policy** — `privacy.html`: covers GA4 analytics, Formspree email, localStorage; no PII stored server-side
- [x] **Terms of Service** — `terms.html`: not financial advice, no warranty on accuracy, scores can change, IP clause
- [x] **Disclaimer** — `disclaimer.html`: 8-row known-limitations table; prominent on every county report
- [x] **Cookie Notice** — GDPR-compliant banner on `index.html`, `compare.html`, `leaderboard.html`; localStorage consent

### 6.2 Data & Accuracy Disclosures
- [x] "Data as of" date on every county page — footer: "Data as of Q1 2026 (scoring engine last run May 2026). BLS QCEW reflects 2023 annual data (18-month publication lag). FHFA HPI through Q4 2025. FBI NIBRS 2024."
- [x] FHFA coverage note — disclaimer.html covers "FHFA covers ~2,800 of 3,143 counties"
- [x] QCEW 18-month lag — documented in county page footer and disclaimer.html
- [x] NIBRS imputation note — documented in disclaimer.html; rural counties without a reporting agency receive RUCC-tier median
- [ ] Link to every raw data source cited in the report *(data sources listed in footer; direct links to federal data pages not yet wired)*

---

## Phase 7 — Launch & Marketing

### 7.1 Pre-Launch (Before Pushing to Domain)
- [ ] Test every county page in 3 browsers (Chrome, Safari, Firefox)
- [ ] Test on mobile (iPhone + Android)
- [ ] Run Lighthouse audit — target 90+ performance, 100 accessibility
- [ ] Verify `sitemap.xml` validates at sitemap.xml.com validator
- [ ] Verify structured data at Google's Rich Results Test tool
- [ ] Verify `robots.txt` is accessible at `/robots.txt`
- [ ] Check 10 random counties: is the data plausible? (Cross-check against Zillow / Redfin spot-check)

### 7.2 Launch Day
- [ ] Post to Hacker News (Show HN: "I scored all 2,820 US counties for homebuyers using only federal data")
- [ ] Post to Reddit: r/datasets, r/dataisbeautiful, r/personalfinance, r/FirstTimeHomeBuyer — lead with a data insight, not a promo
- [ ] Post to ProductHunt
- [ ] Tweet/X: tag data journalists, real estate accounts, and local news outlets in your top-scoring states
- [ ] Submit to Google Search Console and request indexing for the sitemap immediately

### 7.3 Ongoing (Monthly)
- [ ] Re-run scoring engine quarterly as new QCEW/BEA/FHFA data releases
- [ ] Send a "Score Update" email to list when quarterly scores publish
- [ ] Write one blog post per week targeting a specific county comparison or market insight
- [ ] Post 3x/week on Reddit (value-first, no spam — answer real homebuyer questions with Civica data)
- [ ] Monitor Search Console weekly — which county pages are ranking, which need more internal links

---

## Quick Wins (Do These First — High Impact, Low Effort)

1. ✅ **`county_generator.py`** — complete; 2,820 county pages + 51 state pages generated
2. ✅ **`robots.txt` + `sitemap.xml`** — done; sitemap at root with 2,874 URLs
3. ⬜ **GA4 snippet** — ready in template; just needs Brian's Measurement ID
4. ✅ **OG image** — `og_image.png` generated (1200×630) and wired into all pages
5. ✅ **Disclaimer on county pages** — `disclaimer.html` + footer disclaimer on every county page
6. ⬜ **Formspree email capture** — form wired; just needs Brian's Formspree endpoint ID

---

## What You (Brian) Need to Do Personally

These can't be scripted — they require a browser login:

- [ ] **Google Analytics**: Create GA4 property → get Measurement ID (`G-XXXXXXXX`) → set `GA4_ID` in `county_generator.py` → re-run generator
- [ ] **Google Search Console**: Add property → verify domain → submit sitemap (do after domain is live)
- [ ] **Formspree**: Create account at formspree.io → create form → paste endpoint ID into `FORMSPREE_ID` in `index.html`
- [ ] **Domain registrar**: Buy the domain (`civica.app` is live — check `civica.com`, `usecivica.com`, `civica.io`)
- [ ] **Cloudflare Pages**: Create account, connect GitHub repo (Civica-2.0), set custom domain, enable automatic deploys
- [ ] **Stripe**: Create account when ready to monetize → get publishable key + secret key
- [x] ~~**OG image**: Design a 1200×630 PNG~~ — done programmatically via `generate_og_image.py`
