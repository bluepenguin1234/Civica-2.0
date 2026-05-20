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
| ⬜ | County page generator (`county_generator.py`) |
| ⬜ | Front page (search + browse) |
| ⬜ | Compare feature |
| ⬜ | Filter / ranking table |
| ⬜ | Hosting, domain, CDN |
| ⬜ | SEO layer |
| ⬜ | Security headers |
| ⬜ | Analytics |
| ⬜ | Legal pages |
| ⬜ | Monetization wiring |

---

## Phase 1 — Core Build (Site Must Exist Before Anything Else)

### 1.1 County Page Generator
- [ ] Write `county_generator.py` — reads `county_scores.csv`, writes one HTML file per county to `output/counties/{fips}.html`
- [ ] Pull county names + state from USDA RUCC file (already on disk)
- [ ] Replace all template tokens with real data (score ring, pills, dimension breakdown, thesis text, valuation metrics, scenarios, comparables)
- [ ] Generate `output/index.json` — array of all 2,820 counties with score, label, name, state, key metrics — this powers the front page search and filter
- [ ] Add color coding: green/yellow/red for each pill based on national percentile
- [ ] Write a summary "thesis" sentence per county driven by its top 2 signal strengths and top 1 risk
- [ ] Surface crime signal on county page: add a "Safety" pill showing `violent_per100k` (from `county_scores.csv`) with national percentile context. Mark imputed counties with a small note ("Based on regional average — agency did not report to NIBRS").
- [ ] Test 10 representative counties across score range before full run (check Palm Beach FL, Cook IL, Newton AR, Manhattan NY)
- [ ] Run full generation — all 2,820 files

### 1.2 Front Page
- [ ] Build `index.html` — the home/search/browse page
- [ ] Hero section: tagline, search bar (county or state name → jumps to report)
- [ ] National score map (SVG or lightweight library — one color-coded dot per county by label)
- [ ] Top 25 counties table (sortable — by score, by price, by appreciation)
- [ ] Label filter strip: click PEAKING, ESTABLISHED, EMERGING, etc. to filter the table
- [ ] State filter dropdown
- [ ] How It Works section (6 dimensions explained simply)
- [ ] Link to `harvard_model.html` methodology page
- [ ] Email capture (Formspree) — "Get notified when scores update"
- [ ] Footer with data sources, disclaimer, links

### 1.3 Search
- [ ] Client-side search powered by `index.json` (no server needed)
- [ ] Search by county name (e.g., "Hamilton" shows Hamilton County IN, Hamilton County OH, etc.)
- [ ] Search by state abbreviation or full name
- [ ] Autocomplete dropdown — show top 5 results as user types
- [ ] "Did you mean?" for common misspellings
- [ ] Empty state: "No results for X — try searching by state"

### 1.4 Filter & Ranking Table
- [ ] Full sortable data table on front page (all 2,820 counties or paginated)
- [ ] Sort by: Total Score, Affordability, Economic Vitality, Market Dynamics, Physical Risk, Home Value, Appreciation
- [ ] Filter by: Market Label (PEAKING / ESTABLISHED / etc.), State, Population range, Home value range, Score range
- [ ] "Reset filters" button
- [ ] URL reflects current filter state (e.g., `?state=TN&label=PEAKING`) so filters are shareable/linkable
- [ ] Show column: FIPS, County, State, Score, Label, Median Home Value, Avg Wage, HPI 3yr
- [ ] Mobile-responsive: collapse to card view on small screens

### 1.5 Compare Feature
- [ ] "Add to Compare" button on every county report page (stores up to 3 counties in localStorage)
- [ ] Floating compare tray: shows selected counties + "Compare" CTA
- [ ] `compare.html` — side-by-side view of 2–3 counties
- [ ] Show all 6 dimension scores as bar chart comparison
- [ ] Show key metrics table: price, rent, P/R ratio, breakeven, appreciation, wages, net migration, risk scores
- [ ] "Share comparison" — generates a URL like `/compare?a=12099&b=18057&c=47187`
- [ ] "Clear all" button

### 1.6 State Pages
- [ ] One page per state: `output/states/TN.html`
- [ ] Shows all scored counties in that state, ranked by score
- [ ] State-level summary: median score, top county, % PEAKING/ESTABLISHED/etc.
- [ ] These pages are critical for SEO — "best counties to buy a home in Tennessee" is a high-value keyword

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
- [ ] Verify all HTML files are under 200KB each (the template is ~30KB — should be fine)
- [ ] Add `<link rel="preconnect">` for any external fonts or scripts
- [ ] Lazy-load images (if any are added later)
- [ ] Minify `index.json` — remove whitespace, it will be downloaded by every front page visitor
- [ ] Test page load speed with Google PageSpeed Insights — target 90+ on mobile
- [ ] `output/` folder structure: keep it flat `output/counties/` + `output/states/` — don't nest deeper

---

## Phase 3 — Security

*Civica is a static site — no database, no login, no server-side code. Attack surface is very small. These are the relevant hardening steps.*

### 3.1 HTTPS
- [ ] Enforce HTTPS everywhere — redirect all HTTP → HTTPS (hosting provider handles this)
- [ ] Enable HSTS (HTTP Strict Transport Security) header — tells browsers to always use HTTPS
  ```
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  ```

### 3.2 Security Headers (add via hosting provider's `_headers` file or `netlify.toml`)
- [ ] **Content Security Policy** — restrict what scripts/styles can load
  ```
  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none';
  ```
  *(Adjust as you add third-party scripts — GA4, Stripe, Formspree)*
- [ ] **X-Frame-Options** — prevent your pages from being embedded in iframes on other sites
  ```
  X-Frame-Options: DENY
  ```
- [ ] **X-Content-Type-Options** — prevent MIME-type sniffing
  ```
  X-Content-Type-Options: nosniff
  ```
- [ ] **Referrer-Policy** — control what referrer info is sent to third parties
  ```
  Referrer-Policy: strict-origin-when-cross-origin
  ```
- [ ] **Permissions-Policy** — disable browser features you don't use
  ```
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  ```

### 3.3 Cloudflare Settings (if using Cloudflare Pages or proxy)
- [ ] Enable Cloudflare DDoS protection (free tier covers this)
- [ ] Enable Bot Fight Mode
- [ ] Set SSL/TLS mode to "Full (Strict)"
- [ ] Enable "Always Use HTTPS" rule

### 3.4 Email & Form Security (when you add Formspree)
- [ ] Formspree has spam protection built in — enable reCAPTCHA on the form
- [ ] Use Formspree's allowlist to restrict submissions to your domain only
- [ ] Never put a real email address in the HTML source — use Formspree endpoint only

### 3.5 GitHub Repo Security
- [ ] Confirm `civica_data/` is in `.gitignore` and has never been committed (check: `git log --all -- civica_data/`)
- [ ] Enable GitHub's "Secret scanning" and "Dependabot alerts" in repo settings
- [ ] Never commit API keys, Stripe keys, or Formspree IDs directly — use environment variables in hosting dashboard

### 3.6 When You Add a Backend (future)
- [ ] Rate limit the compare/search API endpoints
- [ ] Validate and sanitize all user inputs (search queries, FIPS parameters)
- [ ] Use parameterized queries if you ever add a database
- [ ] Add CORS headers to allow only your domain to call your API

---

## Phase 4 — SEO

*Static HTML files are the right call — Google indexes them completely. This is a major advantage over JavaScript-rendered apps.*

### 4.1 On-Page SEO (Per County Page)
- [ ] Unique `<title>` tag per page: `{County Name}, {State} Housing Market Score — Civica`
- [ ] Unique `<meta name="description">`: `{County} scores {score}/100 on Civica's 6-dimension housing model. {Label} market. Median home: ${value}. See affordability, economic vitality, risk, and more.`
- [ ] `<meta property="og:title">`, `og:description`, `og:image`, `og:url` for social sharing
- [ ] `og:image` — create a template OG image (1200×630px) for county pages: score ring + county name + label badge. Can generate these programmatically in Python using Pillow.
- [ ] `<link rel="canonical">` on every page pointing to its own URL
- [ ] Structured data / JSON-LD on each county page:
  ```json
  {
    "@context": "https://schema.org",
    "@type": "Dataset",
    "name": "{County} Housing Market Analysis",
    "description": "...",
    "url": "https://civica.com/county/{fips}"
  }
  ```
- [ ] H1 tag = county name (already in template)
- [ ] Alt text on any images
- [ ] Internal links: each county page links to its state page and to 3 comparable counties

### 4.2 Site-Wide SEO
- [ ] `robots.txt` — allow all crawlers, point to sitemap
  ```
  User-agent: *
  Allow: /
  Sitemap: https://civica.com/sitemap.xml
  ```
- [ ] `sitemap.xml` — list all 2,820 county URLs + 50 state URLs + front page. Generate this in `county_generator.py`.
- [ ] `sitemap_index.xml` — if sitemap grows past 50,000 URLs, split into multiple files
- [ ] Set `<html lang="en">` on every page
- [ ] Breadcrumb structured data on county pages: Home > Tennessee > Williamson County

### 4.3 Google Search Console
- [ ] Create account at search.google.com/search-console
- [ ] Add property for your domain
- [ ] Verify ownership via DNS TXT record or HTML meta tag
- [ ] Submit `sitemap.xml`
- [ ] Monitor: which county pages get impressions, which keywords are driving clicks
- [ ] After 4–6 weeks: identify your top organic landing pages — double down on those states/labels

### 4.4 Google Analytics 4
- [ ] Create GA4 property
- [ ] Add `G-XXXXXXXXXX` measurement ID to the `<head>` of every generated HTML page (add to the template before running the generator)
- [ ] Set up conversion events: `county_report_view`, `compare_initiated`, `email_signup`
- [ ] Create a GA4 audience for "visited 3+ county pages" — these are your most engaged users
- [ ] Connect GA4 to Google Search Console for combined organic + behavior data

### 4.5 Keyword Strategy
- [ ] **Tier 1 — high intent, low competition**: `"{County} housing market 2026"`, `"is {County} a good place to buy a home"`, `"{County} home prices"` — 2,820 unique pages targeting these
- [ ] **Tier 2 — comparison queries**: `"{County A} vs {County B}"` — build the compare feature, it captures this traffic
- [ ] **Tier 3 — state-level**: `"best counties to buy a home in {State}"` — one page per state
- [ ] **Tier 4 — methodology**: `"price-to-rent ratio by county"`, `"housing market risk index"` — the methodology page captures these researchers
- [ ] **Do NOT**: buy backlinks, keyword-stuff, or create pages that aren't useful to real people

### 4.6 Link Building
- [ ] List Civica on: ProductHunt, Hacker News (Show HN), Reddit r/datasets, r/dataisbeautiful
- [ ] Reach out to real estate blogs, local news sites — offer data for a story in exchange for a link
- [ ] Get listed on: AlternativeTo.net, G2 (Tools & Data category)
- [ ] Every Reddit post where you share Civica data = potential link if people cite it

---

## Phase 5 — Features Roadmap

### 5.1 Must-Have at Launch
- [ ] Search (county name → report page)
- [ ] State filter on front page table
- [ ] Label filter (PEAKING, ESTABLISHED, etc.)
- [ ] Sort by score / home value / appreciation
- [ ] Compare (basic: URL-based, 2 counties)
- [ ] Mobile-responsive layout on all pages

### 5.2 Shortly After Launch
- [ ] **Score history** — re-run engine each quarter, store historical scores, show trend line on county page ("Score 3 months ago: 61 → today: 64 ↑")
- [ ] **Saved counties** — localStorage saves, no login required. "You saved 3 counties" floating button
- [ ] **Share button** — copies URL + pre-fills a tweet: "Jefferson County, CO scores 80/100 on @CivicaData — ESTABLISHED market. See the full breakdown:"
- [ ] **Print / PDF view** — clean print stylesheet so the report looks good printed
- [ ] **"Near me" button** — uses browser geolocation to find closest county
- [ ] **Pagination** on front page table — show 50/100/250 at a time

### 5.3 Growth Features (Post-Launch, Once You Have Traffic)
- [ ] **Email alerts** — "Notify me if {county} score changes by more than 5 points" — user enters email, you send on quarterly re-score
- [ ] **Embed widget** — `<iframe src="civica.com/widget/12099">` — a compact score card any real estate agent can embed on their site. Drives backlinks.
- [ ] **API** — `GET /api/county/{fips}` returns JSON of all scores. Paid access via API key. Targets proptech developers.
- [ ] **National leaderboard** — "Top 100 counties" and "Bottom 100 counties" pages. High SEO value.
- [ ] **"Undervalued" filter** — high score + below-median home value. This is a power user feature that will go viral on Reddit.
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
- [ ] **Privacy Policy** — describe what data you collect (GA4 analytics, Formspree email, no PII stored on your servers). Template exists from v1 — update it for the national Harvard model.
- [ ] **Terms of Service** — key clauses: data is informational only (not financial/legal advice), no warranty on accuracy, you can change the scores at any time
- [ ] **Disclaimer** — prominent on every county report: "Civica scores are derived from federal government data and are for informational purposes only. They do not constitute investment, financial, or real estate advice. Past appreciation is not indicative of future returns."
- [ ] **Cookie Notice** — GDPR requires it if you serve EU visitors (GA4 uses cookies). A simple banner: "This site uses Google Analytics. By continuing, you consent." with an Opt Out link.

### 6.2 Data & Accuracy Disclosures
- [ ] Add a "Data as of" date on every county page (scoring engine last run: date)
- [ ] Add the known limitations note from CLAUDE.md: "FHFA covers ~2,800 of 3,143 counties. Missing counties receive median imputation."
- [ ] Note that QCEW has an 18-month lag — economic vitality scores reflect 2023 data
- [ ] Note that NIBRS covers ~2,869 of 2,820 scored counties; rural counties without a participating agency receive their RUCC-tier median rate (not actual crime data)
- [ ] Link to every raw data source cited in the report (builds trust, helps SEO, is the right thing to do)

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
- [ ] Post to Hacker News (Show HN: "I scored all 3,143 US counties for homebuyers using only federal data")
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

1. **`county_generator.py`** — without this, none of the above matters
2. **`robots.txt` + `sitemap.xml`** — 30 minutes of work, massive SEO value
3. **GA4 snippet in the template** — add it before running the generator so every page is tracked from day one
4. **OG image** — one 1200×630 PNG, generated by Python script. Without it, every shared link shows a blank preview.
5. **Disclaimer on county pages** — legal protection, should go live with the site
6. **Formspree email capture** — start building the list on day one

---

## What You (Brian) Need to Do Personally

These can't be scripted — they require a browser login:

- [ ] **Google Analytics**: Create GA4 property → get Measurement ID (`G-XXXXXXXX`) → share it
- [ ] **Google Search Console**: Add property → verify domain → will be done after the domain is live
- [ ] **Formspree**: Create account → create form → get endpoint ID
- [ ] **Domain registrar**: Buy the domain (`civica.com` or `usecivica.com`) and set DNS
- [ ] **Cloudflare/Netlify**: Create account, connect GitHub repo, set custom domain
- [ ] **Stripe**: Create account when ready to monetize → get publishable key + secret key
- [ ] **OG image**: Design a 1200×630 PNG (Canva works fine) — Civica logo + "Research-grade county intelligence"
