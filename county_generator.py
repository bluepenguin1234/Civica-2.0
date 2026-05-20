#!/usr/bin/env python3
"""
county_generator.py — Civica Harvard Model
Reads county_scores.csv + RUCC xlsx → 2,820 county HTML pages + index.json + sitemap.xml

Output layout:
  output/counties/{fips}.html   — one page per county
  output/index.json             — all counties array for front-page search
  output/sitemap.xml            — XML sitemap
"""

import json
import math
import os
import sys

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

BASE     = os.path.dirname(os.path.abspath(__file__))
DATA     = os.path.join(BASE, 'civica_data')
TEMPLATE = os.path.join(BASE, 'harvard_county_profile.html')
SCORES   = os.path.join(BASE, 'county_scores.csv')
OUT_DIR  = os.path.join(BASE, 'output', 'counties')
OUT_JSON = os.path.join(BASE, 'output', 'index.json')
OUT_SITE = os.path.join(BASE, 'sitemap.xml')   # at root so /sitemap.xml resolves correctly
SITE_URL = 'https://civica.app'
# Canonical base URLs — must match actual deployed paths
COUNTY_URL_BASE = f'{SITE_URL}/output/counties'
STATE_URL_BASE  = f'{SITE_URL}/output/states'
GA4_ID   = ''  # Set to your Google Analytics 4 Measurement ID (e.g. 'G-XXXXXXXXXX') then re-run


# ── Constants ──────────────────────────────────────────────────────────────────

RUCC_LABEL = {
    1: 'Large Metro', 2: 'Metro', 3: 'Small Metro',
    4: 'Micropolitan', 5: 'Micropolitan',
    6: 'Rural-Urban', 7: 'Rural-Urban',
    8: 'Rural', 9: 'Rural',
}

THESIS = {
    'STRONG BUY': 'Top-tier fundamentals with positive momentum across all key dimensions.',
    'BUY':        'Solid market with good fundamentals. The data supports a purchase decision.',
    'WATCH':      'Mixed or shifting signals. Conditions worth monitoring before committing.',
    'CAUTION':    'Weakening fundamentals or softening momentum. Higher near-term risk.',
    'AVOID':      'Multiple dimensions are underperforming with no meaningful positive trend.',
}

VERDICT_SIGNAL = {
    'STRONG BUY': ('sig-green', '✅', 'strong buy', 'Top-tier fundamentals with positive momentum. All key signals are aligned. The window for best-value entry is open.'),
    'BUY':        ('sig-green', '✅', 'buy', 'Solid fundamentals support a purchase decision. The data and the direction are broadly aligned.'),
    'WATCH':      ('sig-yellow','👀', 'watch', 'Conditions are mixed or shifting. Do not rush — monitor for 1–2 quarters before committing capital.'),
    'CAUTION':    ('sig-yellow','⚠️', 'approach with caution', 'Fundamentals are softening or below average. Higher risk of value erosion in the near term.'),
    'AVOID':      ('sig-red',   '⚠️', 'avoid', 'Multiple dimensions are underperforming. Capital is better deployed in markets with clearer upside.'),
}

SIGNAL_VB_CLASS = {
    'STRONG BUY': 'vb-strongbuy',
    'BUY':        'vb-buy',
    'WATCH':      'vb-watch',
    'CAUTION':    'vb-caution',
    'AVOID':      'vb-avoid',
}
SIGNAL_SUB = {
    'STRONG BUY': 'Strong fundamentals, improving',
    'BUY':        'Good fundamentals',
    'WATCH':      'Mixed signals — monitor before committing',
    'CAUTION':    'Weakening — approach with care',
    'AVOID':      'Poor fundamentals across multiple dimensions',
}

NAT_MEDIAN_CRIME = 380  # approx violent offenses per 100k — used as comparison baseline


# ── Helpers ────────────────────────────────────────────────────────────────────

def ring_offset(score: float) -> str:
    return f'{289.02 * (1 - score / 100):.2f}'


def compute_trend(row) -> str:
    """RISING / STABLE / DECLINING based on HPI momentum and net migration rate."""
    pts = 0
    try:
        hpi_now = float(row['hpi_latest'])
        hpi_avg = float(row['hpi_3yr_avg'])
        if not (pd.isna(hpi_now) or pd.isna(hpi_avg)):
            diff = hpi_now - hpi_avg
            if diff > 1.0:  pts += 1
            elif diff < -1.0: pts -= 1
    except Exception:
        pass
    try:
        rnet = float(row['RNETMIG2023'])
        if not pd.isna(rnet):
            if rnet > 1.0:  pts += 1
            elif rnet < -1.0: pts -= 1
    except Exception:
        pass
    if pts >= 1:  return 'RISING'
    if pts <= -1: return 'DECLINING'
    return 'STABLE'


def compute_signal(score: float, trend: str) -> str:
    if score >= 57:
        return 'STRONG BUY' if trend == 'RISING' else ('BUY' if trend == 'STABLE' else 'WATCH')
    elif score >= 45:
        return 'BUY' if trend == 'RISING' else ('WATCH' if trend == 'STABLE' else 'CAUTION')
    elif score >= 37:
        return 'WATCH' if trend == 'RISING' else ('CAUTION' if trend == 'STABLE' else 'AVOID')
    return 'AVOID'


def tag_for_signal(signal: str) -> str:
    return {'STRONG BUY': 'tag-g', 'BUY': 'tag-g', 'WATCH': 'tag-y', 'CAUTION': 'tag-y', 'AVOID': 'tag-r'}.get(signal, 'tag-y')


def safe(v, fmt='.1f', prefix='', suffix='', signed=False, fallback='N/A'):
    try:
        if pd.isna(v): return fallback
        if signed and v >= 0:
            return f'{prefix}+{v:{fmt}}{suffix}'
        return f'{prefix}{v:{fmt}}{suffix}'
    except Exception:
        return fallback


def money(v, fallback='N/A'):
    try:
        if pd.isna(v): return fallback
        return f'${v:,.0f}'
    except Exception:
        return fallback


def compute_piti(home_value: float) -> float:
    r = 0.07 / 12
    mf = r / (1 - (1 + r) ** -360)
    return home_value * 0.80 * mf + home_value * 0.012 / 12 + home_value * 0.005 / 12


def dim_pct(row) -> dict:
    return {
        'Affordability':   row['dim1'] / 25 * 100,
        'Economic Vitality': row['dim2'] / 22 * 100,
        'Market Dynamics': row['dim3'] / 20 * 100,
        'Quality of Place': row['dim4'] / 15 * 100,
        'Physical Risk':   row['dim5'] / 12 * 100,
        'Pop. Momentum':   row['dim6'] / 6  * 100,
    }


def meter_pct(value, low, high):
    return min(100, max(0, (value - low) / (high - low) * 100))


def vcolor(value, good_below=None, warn_below=None):
    if good_below is not None:
        if value <= good_below:  return 'up'
        if warn_below and value <= warn_below: return 'flat'
        return 'down'
    return 'flat'


def hp_color(value, good_below=None, good_above=None, warn_below=None, warn_above=None):
    if good_below and value <= good_below: return 'hp-green'
    if good_above and value >= good_above: return 'hp-green'
    if warn_below and value <= warn_below: return 'hp-yellow'
    if warn_above and value >= warn_above: return 'hp-yellow'
    return 'hp-red'


# ── Bull / Bear text generators ────────────────────────────────────────────────

def build_bull_bullets(row, sub: dict) -> list:
    bullets = []
    top_dims = sorted(sub.items(), key=lambda x: x[1], reverse=True)

    dim_bullets = {
        'Affordability': (
            f'<strong>Affordable relative to national peers.</strong> '
            f'P/R ratio of {row["pr_ratio"]:.1f}x with a {row["breakeven_yrs"]:.1f}-year '
            f'buy-rent breakeven is a strong value signal.'
        ),
        'Economic Vitality': (
            f'<strong>Strong labor market fundamentals.</strong> '
            f'Average wage of {money(row["avg_annual_wage"])}/yr with '
            f'{row["income_4yr_growth"]:.1f}% per capita income growth over 4 years.'
        ),
        'Market Dynamics': (
            f'<strong>Housing market has sustained momentum.</strong> '
            f'FHFA 3-year average appreciation of {row["hpi_3yr_avg"]:+.1f}%/yr '
            f'with {row["total_permits"]:,.0f} units permitted — demand signal is consistent.'
        ),
        'Quality of Place': (
            f'<strong>Quality of place is above average.</strong> '
            f'Favorable urban access, amenity density, and crime rate versus peer counties.'
        ),
        'Physical Risk': (
            f'<strong>Low natural hazard exposure.</strong> '
            f'Flood, storm, and wildfire risk all below national median — '
            f'insurance costs are likely at or below national average.'
        ),
        'Pop. Momentum': (
            f'<strong>Net in-migration is positive.</strong> '
            f'{int(row["in_hh"] - row["out_hh"]):+,} net households (IRS SOI). '
            f'In-movers earn {(row["inmover_income_ratio"] - 1) * 100:+.0f}% more than out-movers.'
        ),
    }

    for dim_name, score in top_dims:
        if score >= 55 and dim_name in dim_bullets:
            bullets.append(dim_bullets[dim_name])
        if len(bullets) == 4:
            break

    if not bullets:
        bullets.append('<strong>Relative value exists in this market.</strong> Score above the SPECULATIVE/AVOID floor; some dimensions outperform peers.')

    return bullets


def build_bear_bullets(row, sub: dict) -> list:
    bullets = []
    bot_dims = sorted(sub.items(), key=lambda x: x[1])

    dim_bullets = {
        'Affordability': (
            f'<strong>Stretched valuation.</strong> '
            f'P/R of {row["pr_ratio"]:.1f}x and breakeven horizon of '
            f'{row["breakeven_yrs"]:.1f} years require a long hold to justify ownership over renting.'
        ),
        'Economic Vitality': (
            f'<strong>Weak economic foundation.</strong> '
            f'Below-median wages and {row["income_4yr_growth"]:.1f}% income growth '
            f'over 4 years suggest limited buyer pool expansion.'
        ),
        'Market Dynamics': (
            f'<strong>Price appreciation is {("tepid" if row["hpi_3yr_avg"] < 3 else "frothy")}.</strong> '
            f'3-year FHFA average of {row["hpi_3yr_avg"]:+.1f}%/yr '
            f'{"is below the 3% threshold for real wealth building" if row["hpi_3yr_avg"] < 3 else "is above the 7% threshold where affordability deterioration accelerates"}.'
        ),
        'Physical Risk': (
            f'<strong>Elevated natural hazard exposure.</strong> '
            f'Flood, storm, or wildfire risk is above the national median. '
            f'Homeowners insurance costs may be materially above national average.'
        ),
        'Pop. Momentum': (
            f'<strong>Net out-migration signal.</strong> '
            f'IRS data shows more households leaving than arriving. '
            f'Long-term demand trajectory warrants monitoring.'
        ),
        'Quality of Place': (
            f'<strong>Below-average quality of place metrics.</strong> '
            f'Crime rate, urban access, or amenity density scores '
            f'are below the national median for similarly-sized counties.'
        ),
    }

    for dim_name, score in bot_dims:
        if score <= 45 and dim_name in dim_bullets:
            bullets.append(dim_bullets[dim_name])
        if len(bullets) == 3:
            break

    if not bullets:
        bullets.append('<strong>Rate sensitivity.</strong> At any home price, a mortgage rate spike above 8% meaningfully extends the breakeven horizon. Stress-test your budget at 8.5%.')

    return bullets[:3]


# ── HTML Builders ──────────────────────────────────────────────────────────────

COMPARE_CSS = '''<style>
.cmp-btn {
  background: rgba(255,255,255,.15);
  border: 1px solid rgba(255,255,255,.3);
  color: #fff;
  border-radius: 100px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s;
  white-space: nowrap;
  font-family: inherit;
  align-self: flex-start;
  margin-top: 4px;
}
.cmp-btn:hover { background: rgba(255,255,255,.25); }
.cmp-btn.added { background: #16a34a; border-color: #16a34a; }
.compare-tray {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: #1a3a5c;
  border-top: 2px solid #1a7ff0;
  padding: 12px 28px;
  align-items: center;
  justify-content: space-between;
  z-index: 1000;
  gap: 12px;
  flex-wrap: wrap;
}
.tray-counties { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.tray-chip { background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.2); border-radius: 100px; padding: 4px 12px; font-size: 12px; color: #fff; font-weight: 600; }
.tray-actions { display: flex; gap: 10px; }
.tray-cmp-btn { background: #1a7ff0; color: #fff; border: none; border-radius: 8px; padding: 9px 20px; font-size: 13px; font-weight: 700; cursor: pointer; text-decoration: none; font-family: inherit; display: inline-block; }
.tray-cmp-btn:hover { background: #1568cc; }
.tray-clr-btn { background: transparent; color: rgba(255,255,255,.5); border: 1px solid rgba(255,255,255,.2); border-radius: 8px; padding: 9px 16px; font-size: 13px; cursor: pointer; font-family: inherit; }
.tray-clr-btn:hover { color: #fff; }
@media print {
  .nav, .hero-pills, .cmp-btn, .compare-tray, .cta-row, .acc-header { display: none !important; }
  .hero { padding: 20px 0; background: #fff !important; color: #1a3a5c !important; }
  .hero-eyebrow, .hero-sub { color: #6b7280 !important; }
  h1 { color: #1a3a5c !important; }
  .acc-section { box-shadow: none !important; }
  .acc-body { grid-template-rows: 1fr !important; }
  .card { box-shadow: none; border: 1px solid #e5e7eb; break-inside: avoid; }
  body { background: #fff; }
  a { color: inherit; text-decoration: none; }
}
</style>'''


def build_head(county_name: str, state: str, score: float, signal: str, fips: str, home_value: float, template_style: str) -> str:
    desc = (
        f"{county_name}, {state} scores {score:.0f}/100 on Civica's 6-dimension housing model. "
        f"Signal: {signal}. Median home value ${home_value:,.0f}. "
        f"See affordability, economic vitality, market dynamics, risk, and 5-year price scenarios."
    )
    url = f'{COUNTY_URL_BASE}/{fips}.html'
    ld  = json.dumps({
        "@context": "https://schema.org",
        "@type":    "Dataset",
        "name":     f"{county_name}, {state} Housing Market Analysis",
        "description": desc,
        "url":      url,
    }, separators=(',', ':'))
    breadcrumb = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home",               "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": f"{state} Counties",  "item": f"{STATE_URL_BASE}/{state}.html"},
            {"@type": "ListItem", "position": 3, "name": county_name,          "item": url},
        ],
    }, separators=(',', ':'))

    ga4_snippet = (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>\n'
        f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
        f'gtag("js",new Date());gtag("config","{GA4_ID}");</script>'
    ) if GA4_ID else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{county_name}, {state} Housing Market Score — Civica Research</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{county_name}, {state} Housing Market — Civica">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<meta property="og:image" content="https://civica.app/og_image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://civica.app/og_image.png">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'><rect width='30' height='30' rx='7' fill='%230d2d52'/><rect x='6' y='16' width='4' height='9' rx='1.5' fill='white' opacity='.65'/><rect x='13' y='8' width='4' height='17' rx='1.5' fill='white'/><rect x='20' y='12' width='4' height='13' rx='1.5' fill='white' opacity='.8'/></svg>">
<script type="application/ld+json">
{ld}
</script>
<script type="application/ld+json">
{breadcrumb}
</script>
{ga4_snippet}
{template_style}
{COMPARE_CSS}
</head>'''


def build_nav(state_abbr: str = '', state_name_full: str = '') -> str:
    state_crumb = (
        f'<a class="nav-back" href="../states/{state_abbr}.html" style="margin-right:4px;">{state_name_full}</a>'
        f'<span style="color:rgba(0,0,0,.18);margin:0 4px;">›</span>'
    ) if state_abbr and state_name_full else ''
    return f'''<nav class="nav">
  <a class="logo" href="../../index.html">
    <svg width="28" height="28" viewBox="0 0 30 30" fill="none">
      <rect width="30" height="30" rx="7" fill="#0d2d52"/>
      <rect x="6" y="16" width="4" height="9" rx="1.5" fill="white" opacity="0.65"/>
      <rect x="13" y="8" width="4" height="17" rx="1.5" fill="white"/>
      <rect x="20" y="12" width="4" height="13" rx="1.5" fill="white" opacity="0.8"/>
    </svg>
    <span class="logo-text">civi<em>ca</em></span>
  </a>
  <div class="nav-right">
    <span class="nav-tag" style="margin-right:8px;">Research Report</span>
    {state_crumb}<a class="nav-back" href="../../index.html">← All Counties</a>
  </div>
</nav>'''


def build_hero(row, county_name: str, state: str, rucc_label: str) -> str:
    score    = row['total_score']
    pop      = int(row['POPESTIMATE2023'])
    rucc     = int(row['rucc']) if not pd.isna(row['rucc']) else 5
    top_pct  = max(1, round(row['national_rank'] / 2820 * 100))
    offset   = ring_offset(score)
    trend    = compute_trend(row)
    signal   = compute_signal(score, trend)
    sig_cls  = SIGNAL_VB_CLASS[signal]
    sig_sub  = SIGNAL_SUB[signal]

    pr    = row['pr_ratio']
    be    = row['breakeven_yrs']
    hpi   = row['hpi_3yr_avg']
    piti  = compute_piti(row['median_home_value'])
    netmig = int(row['in_hh'] - row['out_hh'])

    pr_col  = hp_color(pr,  good_below=18, warn_below=22)
    be_col  = hp_color(be,  good_below=4,  warn_below=7)
    hpi_col = 'hp-green' if 3 <= hpi <= 9 else ('hp-yellow' if hpi > 9 else 'hp-red')
    mig_col = 'hp-green' if netmig >= 0 else 'hp-red'
    inc_col = 'hp-green' if row['income_4yr_growth'] >= 8 else ('hp-yellow' if row['income_4yr_growth'] >= 2 else 'hp-red')

    return f'''<div class="hero">
  <div class="hero-top">
    <div>
      <div class="hero-eyebrow">County Research Report · 2026</div>
      <h1>{county_name}, {state}</h1>
      <div class="hero-sub">{rucc_label} · RUCC Code {rucc} · Pop. {pop:,}</div>
    </div>
    <div style="display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;">
      <div class="score-hero">
        <div class="score-lbl" style="font-size:10px;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Civica Score</div>
        <div class="sh-ring">
          <svg viewBox="0 0 110 110">
            <circle cx="55" cy="55" r="46" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="9"/>
            <circle cx="55" cy="55" r="46" fill="none" stroke="#1a7ff0" stroke-width="9"
              stroke-dasharray="289.02" stroke-dashoffset="{offset}" stroke-linecap="round"/>
          </svg>
          <div class="sh-num">{score:.0f}</div>
          <div class="sh-denom">/100</div>
        </div>
        <div class="sh-grade">Top {top_pct}% Nationally</div>
      </div>
      <div class="verdict-badge" style="padding-top:4px;">
        <div class="vb-label">Civica Signal</div>
        <div class="vb-pill {sig_cls}">{signal}</div>
        <div class="vb-score">Score {score:.1f} · {sig_sub}</div>
      </div>
      <button class="cmp-btn" id="compareBtn" onclick="toggleCompare()">+ Compare</button>
    </div>
  </div>

  <div class="hero-pills">
    <div class="hero-pill"><span class="hp-lbl">Monthly Cost</span><span class="hp-val hp-white">{money(piti)}/mo</span></div>
    <div class="hero-pill"><span class="hp-lbl">Home Value</span><span class="hp-val hp-white">{money(row['median_home_value'])}</span></div>
    <div class="hero-pill"><span class="hp-lbl">Appreciation</span><span class="hp-val {hpi_col}">{hpi:+.1f}%/yr</span></div>
    <div class="hero-pill"><span class="hp-lbl">Breakeven</span><span class="hp-val {be_col}">{be:.1f} yrs</span></div>
    <div class="hero-pill"><span class="hp-lbl">Net Migration</span><span class="hp-val {mig_col}">{netmig:+,} HH</span></div>
    <div class="hero-pill"><span class="hp-lbl">P/R Ratio</span><span class="hp-val {pr_col}">{pr:.1f}x</span></div>
  </div>
</div>'''


def build_thesis_panel(row, county_name: str) -> str:
    score  = row['total_score']
    rank   = int(row['national_rank'])
    top_pct = max(1, round(rank / 2820 * 100))
    offset = ring_offset(score)
    sub    = dim_pct(row)
    signal = compute_signal(score, compute_trend(row))

    thesis_h3 = THESIS.get(signal, '')
    thesis_p  = (
        f'{county_name} ranks #{rank:,} of 2,820 scored US counties (top {top_pct}%). '
        f'Strongest dimension{'s' if sum(1 for v in sub.values() if v >= 60) > 1 else ""}: '
        + ', '.join(f'{k} ({v:.0f}/100)' for k, v in sorted(sub.items(), key=lambda x: -x[1])[:2])
        + f'. Weakest: '
        + ', '.join(f'{k} ({v:.0f}/100)' for k, v in sorted(sub.items(), key=lambda x: x[1])[:1])
        + '.'
    )

    sbb_items = ''.join(f'''
        <div class="sbb-item">
          <div class="sbb-name">{name}</div>
          <div class="sbb-val">{val:.0f}<span style="font-size:10px;color:rgba(255,255,255,.35)">/100</span></div>
          <div class="sbb-wt">{wt}% wt</div>
        </div>''' for (name, val), wt in zip(sub.items(), [25,22,20,15,12,6])
    )

    bulls = build_bull_bullets(row, sub)
    bears = build_bear_bullets(row, sub)

    bull_html = '\n'.join(
        f'<div style="display:flex;gap:10px;"><span style="color:var(--green);font-weight:700;flex-shrink:0;">{i+1}.</span><div>{b}</div></div>'
        for i, b in enumerate(bulls)
    )
    bear_html = '\n'.join(
        f'<div style="display:flex;gap:10px;"><span style="color:var(--red);font-weight:700;flex-shrink:0;">{i+1}.</span><div>{b}</div></div>'
        for i, b in enumerate(bears)
    )

    sig_class, sig_icon, verdict_short, verdict_body = VERDICT_SIGNAL.get(signal, VERDICT_SIGNAL['WATCH'])

    return f'''<div class="acc-section open" id="acc-thesis">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">📊</span> Investment Thesis</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">

  <div class="score-banner">
    <div>
      <svg width="88" height="88" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r="46" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="10"/>
        <circle cx="55" cy="55" r="46" fill="none" stroke="#1a7ff0" stroke-width="10"
          stroke-dasharray="289.02" stroke-dashoffset="{offset}" stroke-linecap="round" transform="rotate(-90 55 55)"/>
        <text x="55" y="50" text-anchor="middle" font-size="22" font-weight="900" fill="white" dy=".3em">{score:.0f}</text>
        <text x="55" y="68" text-anchor="middle" font-size="11" fill="rgba(255,255,255,.4)">/100</text>
      </svg>
    </div>
    <div>
      <h3>{thesis_h3}</h3>
      <p>{thesis_p}</p>
      <div class="sbb-items">{sbb_items}</div>
    </div>
  </div>

  <div class="g2">
    <div class="card">
      <div class="card-title"><span class="ct-icon">✅</span> Bull Case — Why This Works</div>
      <div style="display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.55;color:var(--subtext);">
        {bull_html}
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ct-icon">⚠️</span> Bear Case — What Could Go Wrong</div>
      <div style="display:flex;flex-direction:column;gap:10px;font-size:13px;line-height:1.55;color:var(--subtext);">
        {bear_html}
        <div style="display:flex;gap:10px;"><span style="color:var(--red);font-weight:700;flex-shrink:0;">{len(bears)+1}.</span><div><strong style="color:var(--text);">Rate sensitivity.</strong> Stress-test your monthly budget at 8.5% before committing. A 150bps rate increase adds roughly {money(row['median_home_value'] * 0.80 * 0.0125 / 12)}/mo to carrying cost.</div></div>
      </div>
    </div>
  </div>

  <div class="signal {sig_class}">
    <div class="icon">{sig_icon}</div>
    <div class="body" style="font-size:14px;"><strong>Civica Research Verdict:</strong> {county_name} is a <strong>{verdict_short}</strong>. {verdict_body} Data sources: FHFA HPI, BLS QCEW, BEA, FBI NIBRS, FEMA NFIP, Census, IRS SOI, HUD FMR, Zillow ZHVI.</div>
  </div>

  </div></div></div>
</div>'''


def build_valuation_panel(row) -> str:
    pr    = row['pr_ratio']
    pi    = row['price_income']
    be    = row['breakeven_yrs']
    hpi   = row['hpi_3yr_avg']
    home  = row['median_home_value']
    rent  = row['fmr_2br']
    piti  = compute_piti(home)
    excess = max(piti - rent, 1)

    pr_pct = meter_pct(pr,  10, 30)
    pi_pct = meter_pct(pi,  2,  8)
    be_pct = meter_pct(be,  0,  8)
    aff    = piti / max(row['per_capita_income'] / 12, 1) * 100
    aff_pct = meter_pct(aff, 20, 60)

    pr_col  = vcolor(pr,  good_below=18, warn_below=22)
    pi_col  = vcolor(pi,  good_below=4,  warn_below=6)
    be_col  = vcolor(be,  good_below=4,  warn_below=7)
    hpi_col = 'up' if 3 <= hpi <= 7 else 'flat'

    return f'''<div class="acc-section" id="acc-valuation">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">🏠</span> Valuation &amp; Breakeven</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">

  <div class="card">
    <div class="card-title"><span class="ct-icon">⚖️</span> Valuation Dashboard · FHFA + HUD FMR + BEA</div>
    <div class="g4" style="margin-bottom:20px;">
      <div class="sb"><div class="sb-val">{pr:.1f}x</div><div class="sb-lbl">Price-to-Rent Ratio</div><div class="sb-delta {pr_col}">{'✓ Below 18x norm' if pr < 18 else ('↑ Elevated vs 15–18x norm' if pr < 25 else '↑↑ Stretched vs norm')}</div></div>
      <div class="sb"><div class="sb-val">{pi:.1f}x</div><div class="sb-lbl">Price-to-Income Ratio</div><div class="sb-delta {pi_col}">Per capita income basis · See methodology</div></div>
      <div class="sb"><div class="sb-val">{be:.1f} yrs</div><div class="sb-lbl">Buy vs. Rent Breakeven</div><div class="sb-delta {be_col}">{'↓ Strong — under 4yr threshold' if be < 4 else ('Fair — 4–7yr range' if be < 7 else '↑ Long — above 7yr caution zone')}</div></div>
      <div class="sb"><div class="sb-val">{hpi:+.1f}%</div><div class="sb-lbl">3yr Avg Appreciation (FHFA)</div><div class="sb-delta {hpi_col}">{'Healthy range (3–7%)' if 3 <= hpi <= 7 else ('Above 7% — froth risk' if hpi > 7 else 'Below 3% — stagnation risk')}</div></div>
    </div>

    <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:14px;">Valuation Meters — vs. National Range</div>

    <div class="meter-row">
      <div class="meter-lbl">Price-to-Rent Ratio</div>
      <div style="flex:1;">
        <div class="meter-track">
          <div class="meter-fill" style="width:{pr_pct:.0f}%;background:linear-gradient(to right,#16a34a,#d97706,#dc2626);opacity:.7;"></div>
          <div class="meter-marker" style="left:{pr_pct:.0f}%;"></div>
        </div>
        <div class="meter-vals"><span>10x (cheap)</span><span>20x (norm)</span><span>30x (expensive)</span></div>
      </div>
      <div class="meter-val {pr_col}">{pr:.1f}x</div>
    </div>

    <div class="meter-row">
      <div class="meter-lbl">Price-to-Income Ratio</div>
      <div style="flex:1;">
        <div class="meter-track">
          <div class="meter-fill" style="width:{pi_pct:.0f}%;background:linear-gradient(to right,#16a34a,#d97706,#dc2626);opacity:.7;"></div>
          <div class="meter-marker" style="left:{pi_pct:.0f}%;"></div>
        </div>
        <div class="meter-vals"><span>2x (cheap)</span><span>4.5x (mid)</span><span>8x (expensive)</span></div>
      </div>
      <div class="meter-val {pi_col}">{pi:.1f}x</div>
    </div>

    <div class="meter-row">
      <div class="meter-lbl">Breakeven Horizon</div>
      <div style="flex:1;">
        <div class="meter-track">
          <div class="meter-fill" style="width:{be_pct:.0f}%;background:linear-gradient(to right,#16a34a,#d97706,#dc2626);opacity:.7;"></div>
          <div class="meter-marker" style="left:{be_pct:.0f}%;"></div>
        </div>
        <div class="meter-vals"><span>0 yrs (buy now)</span><span>4 yrs (fair)</span><span>8+ yrs (avoid)</span></div>
      </div>
      <div class="meter-val {be_col}">{be:.1f} yrs</div>
    </div>

    <div class="meter-row">
      <div class="meter-lbl">Monthly Cost / Income</div>
      <div style="flex:1;">
        <div class="meter-track">
          <div class="meter-fill" style="width:{aff_pct:.0f}%;background:linear-gradient(to right,#16a34a,#d97706,#dc2626);opacity:.7;"></div>
          <div class="meter-marker" style="left:{aff_pct:.0f}%;"></div>
        </div>
        <div class="meter-vals"><span>20% (affordable)</span><span>36% (max)</span><span>60%+ (crisis)</span></div>
      </div>
      <div class="meter-val {'up' if aff < 30 else ('flat' if aff < 40 else 'down')}">{aff:.0f}%</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span class="ct-icon">🏠</span> Buy vs. Rent Analysis</div>
    <div class="g3">
      <div class="sb"><div class="sb-val">{money(piti)}</div><div class="sb-lbl">Monthly cost to own (PITI)</div><div class="sb-delta flat">7% rate · 20% down · 1.2% tax</div></div>
      <div class="sb"><div class="sb-val">{money(rent)}</div><div class="sb-lbl">Monthly rent (HUD FMR 2BR)</div><div class="sb-delta flat">Source: HUD Fair Market Rents FY2026</div></div>
      <div class="sb"><div class="sb-val">{money(excess)}</div><div class="sb-lbl">Monthly ownership premium</div><div class="sb-delta flat">Extra cost of owning vs. renting</div></div>
    </div>
    <div class="signal sig-blue" style="margin-top:16px;">
      <div class="icon">💡</div>
      <div class="body"><strong>How breakeven works:</strong> You pay {money(excess)}/mo more to own than rent. At {hpi:.1f}% appreciation, your {money(home)} home gains approximately {money(home * hpi / 100 / 12)}/mo in value. After accounting for transaction costs (~11%), the ownership premium is recovered in <strong>{be:.1f} years</strong>. For any hold period beyond that, owning is financially superior to renting in this county — assuming current appreciation continues.</div>
    </div>
  </div>

  </div></div></div>
</div>'''


def build_supply_panel(row, county_name: str) -> str:
    permits  = int(row['total_permits'])
    net_hh   = int(row['in_hh'] - row['out_hh'])
    in_hh    = int(row['in_hh'])
    out_hh   = int(row['out_hh'])
    ratio    = row['inmover_income_ratio']
    inc_prem = (ratio - 1) * 100
    rnet     = row['RNETMIG2023']
    inv      = int(row['inventory']) if not pd.isna(row['inventory']) else 0

    supply_sig = 'sig-green' if permits > 0 and net_hh > 0 else 'sig-yellow'
    supply_icon = '🏗️' if net_hh > 0 else '⚠️'
    supply_body = (
        f'New construction ({permits:,} units permitted) is {"responding to" if permits > net_hh else "lagging"} demand. '
        f'Net household in-migration of {net_hh:+,} households (IRS SOI). '
        f'Zillow active inventory: {inv:,} listings as of latest available month.'
    )

    mig_sig = 'sig-purple' if ratio >= 1.0 else 'sig-yellow'
    mig_body = (
        f'IRS SOI data: {in_hh:,} filer households moved in, {out_hh:,} moved out. '
        f'Net: {net_hh:+,} households. '
        f'In-movers earn {inc_prem:+.0f}% {"more" if inc_prem >= 0 else "less"} than out-movers (AGI basis). '
        f'Census net migration rate: {rnet:+.1f} per 1,000 residents.'
    )

    return f'''<div class="acc-section" id="acc-supply">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">🏗️</span> Supply &amp; Demand</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">

  <div class="card">
    <div class="card-title"><span class="ct-icon">🏗️</span> Supply-Demand Balance</div>
    <div class="g3" style="margin-bottom:20px;">
      <div class="sb"><div class="sb-val">{net_hh:+,}</div><div class="sb-lbl">Net households (IRS, 2022-23)</div><div class="sb-delta {'up' if net_hh > 0 else 'down'}">{'In-migration positive' if net_hh > 0 else 'Net out-migration'}</div></div>
      <div class="sb"><div class="sb-val">{permits:,}</div><div class="sb-lbl">Units permitted (Census BPS 2022)</div><div class="sb-delta flat">New supply pipeline</div></div>
      <div class="sb"><div class="sb-val">{inv:,}</div><div class="sb-lbl">Active listings (Zillow, latest)</div><div class="sb-delta flat">Current for-sale inventory</div></div>
    </div>
    <div class="signal {supply_sig}">
      <div class="icon">{supply_icon}</div>
      <div class="body">{supply_body}</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span class="ct-icon">🧭</span> Migration Quality Analysis · IRS SOI 2022-23</div>
    <div class="g4">
      <div class="sb"><div class="sb-val">{in_hh:,}</div><div class="sb-lbl">Households moved IN</div><div class="sb-delta up">IRS SOI filer count</div></div>
      <div class="sb"><div class="sb-val">{out_hh:,}</div><div class="sb-lbl">Households moved OUT</div><div class="sb-delta flat">IRS SOI filer count</div></div>
      <div class="sb"><div class="sb-val">{ratio:.2f}x</div><div class="sb-lbl">In-mover income ratio</div><div class="sb-delta {'up' if ratio >= 1 else 'down'}">{'In-movers earn more' if ratio >= 1 else 'In-movers earn less'}</div></div>
      <div class="sb"><div class="sb-val">{net_hh:+,}</div><div class="sb-lbl">Net household gain</div><div class="sb-delta {'up' if net_hh > 0 else 'down'}">{'Positive net flow' if net_hh > 0 else 'Negative net flow'}</div></div>
    </div>
    <div class="signal {mig_sig}" style="margin-top:14px;">
      <div class="icon">📌</div>
      <div class="body">{mig_body}</div>
    </div>
  </div>

  </div></div></div>
</div>'''


def build_scenarios_panel(row) -> str:
    home  = row['median_home_value']
    bull  = home * 1.63
    base  = home * 1.27
    bear  = home * 0.93
    ev    = 0.30 * bull + 0.50 * base + 0.20 * bear

    return f'''<div class="acc-section" id="acc-scenarios">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">🔭</span> 5-Year Price Scenarios</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">


  <div class="card">
    <div class="card-title"><span class="ct-icon">🔭</span> 5-Year Price Scenarios · FHFA Trend Analysis</div>
    <div class="card-intro">Based on FHFA historical appreciation data and IRS migration trends. Scenarios reflect plausible macro conditions — not predictions.</div>

    <div class="scenario-grid">
      <div class="scenario-card sc-bull">
        <div class="sc-label">Bull Case</div>
        <div class="sc-prob">30% probability</div>
        <div class="sc-val">{money(bull)}</div>
        <div class="sc-rate">+10.3% / yr average</div>
        <div style="font-size:12px;font-weight:700;color:#15803d;margin-bottom:8px;">{money(bull - home)} gain · +63% total</div>
        <div class="sc-trigger"><strong>Triggers:</strong> Rates fall to 5.5–6.0%. Strong in-migration continues. Economic fundamentals accelerate. Supply remains constrained.</div>
      </div>
      <div class="scenario-card sc-base">
        <div class="sc-label">Base Case</div>
        <div class="sc-prob">50% probability</div>
        <div class="sc-val">{money(base)}</div>
        <div class="sc-rate">+4.8% / yr average</div>
        <div style="font-size:12px;font-weight:700;color:#1d4ed8;margin-bottom:8px;">{money(base - home)} gain · +27% total</div>
        <div class="sc-trigger"><strong>Triggers:</strong> Rates stable at 6.5–7.5%. Migration and employment continue at current pace. Appreciation moderates toward historical trend.</div>
      </div>
      <div class="scenario-card sc-bear">
        <div class="sc-label">Bear Case</div>
        <div class="sc-prob">20% probability</div>
        <div class="sc-val">{money(bear)}</div>
        <div class="sc-rate">−1.5% / yr average</div>
        <div style="font-size:12px;font-weight:700;color:#b91c1c;margin-bottom:8px;">{money(bear - home)} · −7% total</div>
        <div class="sc-trigger"><strong>Triggers:</strong> Rates spike above 9%. Recession or major employer exit. Broad return-to-office reduces remote-buyer demand. Natural disaster event.</div>
      </div>
    </div>

    <div class="signal sig-blue" style="margin-top:16px;">
      <div class="icon">📐</div>
      <div class="body"><strong>Expected Value (probability-weighted):</strong> 0.30 × {money(bull)} + 0.50 × {money(base)} + 0.20 × {money(bear)} = <strong>{money(ev)} expected home value in 5 years</strong> — a {(ev/home - 1)*100:.0f}% expected gain on today's {money(home)} price.</div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span class="ct-icon">📈</span> Equity Build — Base Case (4.8% / yr)</div>
    <div style="display:flex;flex-direction:column;gap:0;">
      {_equity_row('Today',  home,      home,  'Today · 20% down', 38)}
      {_equity_row('Year 2', home*1.10, home,  f'+{money(home*0.10)} appreciation', 48)}
      {_equity_row('Year 3', home*1.15, home,  f'+{money(home*0.15)} · Buy beats rent ✓', 56, green=True)}
      {_equity_row('Year 5', base,      home,  f'+{money(base - home)} appreciation', 70, green=True)}
      {_equity_row('Year 10',home*1.60, home,  f'+{money(home*0.60)} appreciation', 100, green=True)}
    </div>
  </div>

  </div></div></div>
</div>'''


def _equity_row(label, value, home, note, bar_pct, green=False):
    color = '#16a34a' if green else '#1a7ff0'
    return f'''<div style="display:flex;align-items:center;gap:14px;padding:11px 0;border-bottom:1px solid #f3f4f6;">
        <div style="font-size:12px;color:var(--muted);width:64px;flex-shrink:0;">{label}</div>
        <div style="flex:1;background:#f1f5f9;border-radius:4px;height:12px;"><div style="width:{min(bar_pct,100)}%;height:100%;border-radius:4px;background:{color};"></div></div>
        <div style="text-align:right;"><div style="font-size:14px;font-weight:800;color:var(--navy);">{money(value)}</div><div style="font-size:11px;color:{'var(--green)' if green else 'var(--muted)'};">{note}</div></div>
      </div>'''


def build_fundamentals_panel(row, county_name: str) -> str:
    wage   = row['avg_annual_wage']
    inc_g  = row['income_4yr_growth']
    hhi    = row['hhi']
    sq     = row['sector_quality']
    crime  = row['violent_per100k']
    pop    = row['POPESTIMATE2023']

    hhi_label = 'Low (diversified)' if hhi < 1500 else ('Moderate' if hhi < 2500 else 'High (concentrated)')
    crime_col = 'up' if crime < NAT_MEDIAN_CRIME else 'down'
    crime_vs  = f'vs ~{NAT_MEDIAN_CRIME} national est.'

    return f'''<div class="acc-section" id="acc-fundamentals">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">💼</span> Economic Fundamentals</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">

  <div class="g2">
    <div class="card">
      <div class="card-title"><span class="ct-icon">💼</span> Economic Vitality · BLS QCEW + BEA</div>
      <div class="g2" style="gap:10px;margin-bottom:14px;">
        <div class="sb"><div class="sb-val">{money(wage)}</div><div class="sb-lbl">Avg Annual Wage (BLS QCEW 2023)</div><div class="sb-delta {'up' if wage > 55000 else 'flat'}">{'Above' if wage > 55000 else 'Near'} national median</div></div>
        <div class="sb"><div class="sb-val">{inc_g:+.1f}%</div><div class="sb-lbl">Per Capita Income Growth (4yr)</div><div class="sb-delta {'up' if inc_g > 15 else ('flat' if inc_g > 5 else 'down')}">BEA CAINC1 · {'Strong' if inc_g > 15 else ('Moderate' if inc_g > 5 else 'Weak')}</div></div>
      </div>
      <div class="g2" style="gap:10px;">
        <div class="sb"><div class="sb-val">{sq:.2f}</div><div class="sb-lbl">Sector Quality Score</div><div class="sb-delta {'up' if sq > 1.0 else 'flat'}">{'Above-average sector mix' if sq > 1.0 else 'Average sector mix'} · 1.00 = neutral</div></div>
        <div class="sb"><div class="sb-val">{hhi_label}</div><div class="sb-lbl">Employment Concentration (HHI)</div><div class="sb-delta {'up' if hhi < 1500 else ('flat' if hhi < 2500 else 'down')}">HHI: {hhi:,.0f} · {'Diversified' if hhi < 1500 else ('Moderate' if hhi < 2500 else 'Concentrated')}</div></div>
      </div>
    </div>

    <div class="card">
      <div class="card-title"><span class="ct-icon">🛡️</span> Safety · FBI NIBRS 2024</div>
      <div class="g2" style="gap:10px;margin-bottom:12px;">
        <div class="sb"><div class="sb-val">{crime:.0f}</div><div class="sb-lbl">Violent Crime / 100k residents</div><div class="sb-delta {crime_col}">{crime_vs}</div></div>
        <div class="sb"><div class="sb-val">{row["est_per_1k"]:.1f}</div><div class="sb-lbl">Establishments / 1,000 residents</div><div class="sb-delta flat">Census CBP 2022 · Amenity density</div></div>
      </div>
      <div class="signal {'sig-green' if crime < NAT_MEDIAN_CRIME * 0.75 else ('sig-yellow' if crime < NAT_MEDIAN_CRIME else 'sig-red')}">
        <div class="icon">{'✅' if crime < NAT_MEDIAN_CRIME else '⚠️'}</div>
        <div class="body">Violent crime rate of {crime:.0f} per 100k is {'well below' if crime < NAT_MEDIAN_CRIME * 0.75 else ('below' if crime < NAT_MEDIAN_CRIME else 'above')} the national estimate of ~{NAT_MEDIAN_CRIME}. Source: FBI NIBRS 2024 National Master File ({int(row["violent_offenses"]):,} reported offenses).</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title"><span class="ct-icon">📍</span> Urban Access · USDA RUCC 2023</div>
    <div class="g3">
      <div class="sb"><div class="sb-val">{int(row["rucc"])}</div><div class="sb-lbl">RUCC Code (1=large metro, 9=rural)</div><div class="sb-delta {'up' if row['rucc'] <= 3 else ('flat' if row['rucc'] <= 6 else 'down')}">{RUCC_LABEL.get(int(row['rucc']), 'Unknown')} · USDA 2023</div></div>
      <div class="sb"><div class="sb-val">{pop:,.0f}</div><div class="sb-lbl">Population (Census 2023)</div><div class="sb-delta flat">County estimate</div></div>
      <div class="sb"><div class="sb-val">{int(row['private_employment']):,}</div><div class="sb-lbl">Private Sector Employment</div><div class="sb-delta flat">BLS QCEW 2023 annual average</div></div>
    </div>
  </div>

  </div></div></div>
</div>'''


def build_risk_panel(row) -> str:
    flood   = row['nfip_per_cap']
    storm   = row['storm_per_cap']
    wild    = row['wildfire_rank']
    dim5    = row['dim5'] / 12 * 100

    flood_col = 'impact-low' if flood < 5 else ('impact-med' if flood < 20 else 'impact-high')
    storm_col = 'impact-low' if storm < 50 else ('impact-med' if storm < 200 else 'impact-high')
    wild_col  = 'impact-low' if wild < 0.3 else ('impact-med' if wild < 0.6 else 'impact-high')

    overall_sig = 'sig-green' if dim5 >= 65 else ('sig-yellow' if dim5 >= 40 else 'sig-red')
    overall_icon = '✅' if dim5 >= 65 else '⚠️'

    return f'''<div class="acc-section" id="acc-risk">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">⚠️</span> Risk Matrix</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">

  <div class="card">
    <div class="card-title"><span class="ct-icon">⚠️</span> Physical Risk Matrix · FEMA NFIP + NOAA + USFS</div>
    <div class="card-intro">Risk is scored relative to all 2,820 counties. Physical Risk dimension score: {dim5:.0f}/100 (higher = safer).</div>

    <div class="risk-matrix">
      <div class="rm-card">
        <div class="rm-icon">🌊</div>
        <div class="rm-name">Flood Risk</div>
        <div class="rm-prob">NFIP claims per capita (10yr avg)</div>
        <div class="rm-impact {flood_col}">{('LOW' if flood_col=='impact-low' else 'MODERATE' if flood_col=='impact-med' else 'HIGH')} — ${flood:.2f}/capita avg annual claims</div>
      </div>
      <div class="rm-card">
        <div class="rm-icon">🌪️</div>
        <div class="rm-name">Storm Risk</div>
        <div class="rm-prob">NOAA property damage per capita (5yr)</div>
        <div class="rm-impact {storm_col}">{('LOW' if storm_col=='impact-low' else 'MODERATE' if storm_col=='impact-med' else 'HIGH')} — ${storm:.0f}/capita avg annual damage</div>
      </div>
      <div class="rm-card">
        <div class="rm-icon">🔥</div>
        <div class="rm-name">Wildfire Exposure</div>
        <div class="rm-prob">USFS Wildfire Risk to Communities</div>
        <div class="rm-impact {wild_col}">{('LOW' if wild_col=='impact-low' else 'MODERATE' if wild_col=='impact-med' else 'HIGH')} — national risk rank {wild:.3f}</div>
      </div>
      <div class="rm-card">
        <div class="rm-icon">📈</div>
        <div class="rm-name">Rate Shock (&gt;9%)</div>
        <div class="rm-prob">Probability: 20%</div>
        <div class="rm-impact impact-high">Impact: HIGH — extends breakeven materially</div>
      </div>
      <div class="rm-card">
        <div class="rm-icon">💼</div>
        <div class="rm-name">Economic Slowdown</div>
        <div class="rm-prob">Probability: 20%</div>
        <div class="rm-impact impact-med">Impact: MODERATE — softens buyer demand</div>
      </div>
      <div class="rm-card">
        <div class="rm-icon">🏦</div>
        <div class="rm-name">Insurance Cost Rise</div>
        <div class="rm-prob">Probability: 30%</div>
        <div class="rm-impact {'impact-high' if wild > 0.5 or flood > 15 else 'impact-med'}">Impact: {'HIGH in high-risk areas' if wild > 0.5 or flood > 15 else 'MODERATE — monitor carrier availability'}</div>
      </div>
    </div>

    <div class="signal {overall_sig}" style="margin-top:16px;">
      <div class="icon">{overall_icon}</div>
      <div class="body"><strong>Physical Risk Summary:</strong> This county scores {dim5:.0f}/100 on the Civica Physical Risk dimension (higher = safer). {'Natural hazard exposure is below the national median across flood, storm, and wildfire categories.' if dim5 >= 65 else 'One or more natural hazard categories are above the national median. Review your homeowners insurance quotes carefully before closing.'} Data: FEMA NFIP paid claims, NOAA Storm Events 2019–2023, USFS Wildfire Risk to Communities.</div>
    </div>
  </div>

  </div></div></div>
</div>'''


def build_compare_panel(row, comp_rows, comp_names, comp_states) -> str:
    def comp_row_html(crow, cname, cstate, highlight=False):
        cs = crow['total_score']
        c_signal  = compute_signal(cs, compute_trend(crow))
        tag_class = tag_for_signal(c_signal)
        net_mig = int(crow['in_hh'] - crow['out_hh'])
        pr_col  = vcolor(crow['pr_ratio'],   good_below=18, warn_below=24)
        be_col  = vcolor(crow['breakeven_yrs'], good_below=4,  warn_below=7)
        hpi_col = 'up' if 3 <= crow['hpi_3yr_avg'] <= 8 else 'flat'
        mig_col = 'up' if net_mig >= 0 else 'down'

        hl = ' class="hl"' if highlight else ''
        nm = ' class="cn"' if not highlight else ' class="cn"'
        star = ' ★' if highlight else ''
        return f'''<tr{hl}>
            <td{nm}>{cname}, {cstate}{star}</td>
            <td><strong>{cs:.0f}</strong></td>
            <td class="{pr_col}">{crow["pr_ratio"]:.1f}x</td>
            <td class="{be_col}">{crow["breakeven_yrs"]:.1f} yrs</td>
            <td class="{hpi_col}">{crow["hpi_3yr_avg"]:+.1f}%</td>
            <td class="{mig_col}">{net_mig:+,}</td>
            <td><span class="tag {tag_class}">{c_signal}</span></td>
          </tr>'''

    current_row_html = comp_row_html(row, comp_names[0], comp_states[0], highlight=True)
    comp_rows_html = '\n'.join(
        comp_row_html(comp_rows[i], comp_names[i+1], comp_states[i+1])
        for i in range(len(comp_rows))
    )

    return f'''<div class="acc-section" id="acc-compare">
  <div class="acc-header" onclick="toggleAcc(this)">
    <div class="acc-title"><span class="acc-icon">⚖️</span> Comparable Counties</div>
    <span class="acc-chevron">▾</span>
  </div>
  <div class="acc-body"><div class="acc-inner"><div class="acc-content">

  <div class="card">
    <div class="card-title"><span class="ct-icon">⚖️</span> Comparable Counties — Nearest Civica Scores</div>
    <div style="overflow-x:auto;">
      <table class="comp-table">
        <thead>
          <tr>
            <th>County</th>
            <th>Score</th>
            <th>P/R Ratio</th>
            <th>Breakeven</th>
            <th>3yr Appr.</th>
            <th>Net Migration</th>
            <th>Signal</th>
          </tr>
        </thead>
        <tbody>
          {current_row_html}
          {comp_rows_html}
        </tbody>
      </table>
    </div>
    <div class="signal sig-blue" style="margin-top:14px;">
      <div class="icon">💡</div>
      <div class="body"><strong>How to use comparables:</strong> These counties have similar overall Civica scores but may differ significantly on individual dimensions. A low P/R ratio is only a buy signal when paired with positive fundamentals — compare all metrics before drawing conclusions.</div>
    </div>
  </div>

  <div class="cta-strip">
    <button class="cta cta-p" onclick="alert('Save feature coming soon.')">Save This County</button>
    <button class="cta cta-s" onclick="window.location='../../harvard_model.html'">View Model Methodology</button>
    <button class="cta cta-s" onclick="window.location='../../index.html'">Back to All Counties</button>
  </div>

  </div></div></div>
</div>'''


COMPARE_TRAY_HTML = '''<div class="compare-tray" id="compareTray">
  <div class="tray-counties" id="trayCounties"></div>
  <div class="tray-actions">
    <a class="tray-cmp-btn" id="trayLink" href="#">Compare Counties →</a>
    <button class="tray-clr-btn" onclick="clearCompare()">Clear all</button>
  </div>
</div>'''


def build_js(fips: str, county_name: str, state: str) -> str:
    this_data = json.dumps({"fips": fips, "name": county_name, "state": state})
    return f'''<script>
function toggleAcc(header) {{
  header.closest('.acc-section').classList.toggle('open');
}}
const _THIS = {this_data};
const CMP_KEY = 'civica_compare';
function getCompare() {{ try {{ return JSON.parse(localStorage.getItem(CMP_KEY)||'[]'); }} catch(e) {{ return []; }} }}
function saveCompare(a) {{ localStorage.setItem(CMP_KEY, JSON.stringify(a)); }}
function toggleCompare() {{
  let a = getCompare();
  const i = a.findIndex(c => c.fips === _THIS.fips);
  if (i >= 0) {{ a.splice(i, 1); }}
  else if (a.length < 3) {{ a.push(_THIS); }}
  else {{ alert('You can compare up to 3 counties. Remove one to add another.'); return; }}
  saveCompare(a);
  renderTray();
}}
function clearCompare() {{ saveCompare([]); renderTray(); }}
function renderTray() {{
  const a = getCompare();
  const btn = document.getElementById('compareBtn');
  const tray = document.getElementById('compareTray');
  const chips = document.getElementById('trayCounties');
  const link = document.getElementById('trayLink');
  const isAdded = a.some(c => c.fips === _THIS.fips);
  if (btn) {{ btn.textContent = isAdded ? '✓ Added' : '+ Compare'; btn.className = isAdded ? 'cmp-btn added' : 'cmp-btn'; }}
  if (a.length >= 2) {{
    tray.style.display = 'flex';
    chips.innerHTML = a.map(c => '<span class="tray-chip">' + c.name + ', ' + c.state + '</span>').join('');
    link.href = '../../compare.html?' + a.map(c => 'c=' + c.fips).join('&');
  }} else {{ tray.style.display = 'none'; }}
}}
renderTray();
</script>'''


FOOTER_HTML = '''<div class="footer">
  Data as of Q1 2026 (scoring engine last run May 2026). BLS QCEW reflects 2023 annual data (18-month publication lag). FHFA HPI through Q4 2025. FBI NIBRS 2024 National Master File.<br>
  All data: IRS SOI · FHFA HPI · BLS QCEW · BEA · FBI NIBRS 2024 · FEMA NFIP · NOAA Storm Events · USFS Wildfire Risk · USDA RUCC · HUD FMR FY2026 · Census Population Estimates · Zillow ZHVI<br>
  Scenarios are illustrative projections, not guarantees. Breakeven assumes 11% total transaction cost and current appreciation rate. P/I uses BEA per capita income (not household income).<br><br>
  <strong>civi<em style="font-style:normal;color:#1a7ff0;">ca</em></strong> — research-grade county intelligence for homebuyers
</div>'''


# ── Assemble full page ──────────────────────────────────────────────────────────

def generate_page(row, county_name, state, template_style, all_df, name_map, state_map):
    score = row['total_score']
    fips  = row['fips']
    rucc  = int(row['rucc']) if not pd.isna(row['rucc']) else 5
    rucc_label = RUCC_LABEL.get(rucc, 'Unknown')

    # Find 4 nearest-score comparables (excluding self)
    others = all_df[all_df['fips'] != fips].copy()
    others['_dist'] = (others['total_score'] - score).abs()
    comp_df = others.nsmallest(4, '_dist')

    comp_rows   = [comp_df.iloc[i] for i in range(len(comp_df))]
    comp_names  = [county_name] + [name_map.get(r['fips'], r['fips']) for r in comp_rows]
    comp_states = [state]       + [state_map.get(r['fips'], '??')     for r in comp_rows]

    panels = '\n'.join([
        build_thesis_panel(row, county_name),
        build_valuation_panel(row),
        build_supply_panel(row, county_name),
        build_scenarios_panel(row),
        build_fundamentals_panel(row, county_name),
        build_risk_panel(row),
        build_compare_panel(row, comp_rows, comp_names, comp_states),
    ])

    state_full = STATE_NAMES.get(state, state)
    _sig = compute_signal(score, compute_trend(row))
    return f'''{build_head(county_name, state, score, _sig, fips, row["median_home_value"], template_style)}
<body>
{build_nav(state, state_full)}
{build_hero(row, county_name, state, rucc_label)}
<div class="page">
{panels}
{FOOTER_HTML}
</div><!-- /page -->
{COMPARE_TRAY_HTML}
{build_js(fips, county_name, state)}
</body>
</html>'''


STATE_NAMES = {
    'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California',
    'CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia',
    'HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa',
    'KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland',
    'MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi',
    'MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire',
    'NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina',
    'ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania',
    'RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee',
    'TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington',
    'WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming','DC':'District of Columbia',
}

LB_CLASS = {
    'STRONG BUY': 'lb-sbuy',
    'BUY':        'lb-buy',
    'WATCH':      'lb-watch',
    'CAUTION':    'lb-caut',
    'AVOID':      'lb-avoid',
}


def build_state_page(state: str, counties: list, template_style: str) -> str:
    state_name = STATE_NAMES.get(state, state)
    count = len(counties)
    top_row, top_name = counties[0]
    top_score = top_row['total_score']
    scores = [r['total_score'] for r, _ in counties]
    median_score = sorted(scores)[len(scores) // 2]

    label_counts = {}
    for r, _ in counties:
        sig = compute_signal(r['total_score'], compute_trend(r))
        label_counts[sig] = label_counts.get(sig, 0) + 1

    dist_html = ' &nbsp;·&nbsp; '.join(
        f'<strong>{v}</strong> {k.title()}'
        for k, v in label_counts.items() if v > 0
    )

    rows_html = ''
    for i, (r, name) in enumerate(counties):
        fips   = r['fips']
        sc     = r['total_score']
        sig    = compute_signal(sc, compute_trend(r))
        lb_cls = LB_CLASS.get(sig, 'lb-watch')
        home   = r['median_home_value']
        hpi    = r['hpi_3yr_avg']
        wage   = r['avg_annual_wage']
        nat_rk = int(r['national_rank'])
        sc_bg  = '#16a34a' if sc >= 58 else ('#d97706' if sc >= 38 else '#dc2626')
        hpi_c  = '#16a34a' if hpi >= 3 else '#dc2626'
        rows_html += f'''<tr onclick="window.location='../counties/{fips}.html'" style="cursor:pointer;">
          <td><span style="font-size:13px;font-weight:700;color:#c7c7cc;">{i+1}</span></td>
          <td><div style="font-size:14px;font-weight:700;color:#0d2d52;">{name}</div>
              <div style="font-size:11px;color:#98989d;">#{nat_rk} nationally</div></td>
          <td><div style="display:flex;align-items:center;gap:8px;">
              <div style="width:32px;height:32px;border-radius:50%;background:{sc_bg};color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;">{sc:.0f}</div>
              <span style="font-size:14px;font-weight:800;color:#0d2d52;">{sc:.1f}</span></div></td>
          <td><span style="font-size:10px;font-weight:700;padding:3px 9px;border-radius:100px;" class="{lb_cls}">{sig}</span></td>
          <td style="text-align:right;font-weight:600;">{money(home)}</td>
          <td style="text-align:right;font-weight:600;color:{hpi_c};">{hpi:+.1f}%</td>
          <td style="text-align:right;">{money(wage)}</td>
        </tr>'''

    url  = f'{STATE_URL_BASE}/{state}.html'
    desc = (
        f'Compare all {count} scored counties in {state_name} by Civica housing score. '
        f'Best counties to buy a home in {state_name} — ranked by affordability, '
        f'economic vitality, market dynamics, and risk.'
    )
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type":    "Dataset",
        "name":     f"Best Counties to Buy a Home in {state_name} — Civica",
        "description": desc,
        "url":      url,
    }, separators=(',', ':'))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Best Counties to Buy a Home in {state_name} — Civica Research</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="Best Counties in {state_name} — Civica Housing Research">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<meta property="og:image" content="https://civica.app/og_image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://civica.app/og_image.png">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'><rect width='30' height='30' rx='7' fill='%230d2d52'/><rect x='6' y='16' width='4' height='9' rx='1.5' fill='white' opacity='.65'/><rect x='13' y='8' width='4' height='17' rx='1.5' fill='white'/><rect x='20' y='12' width='4' height='13' rx='1.5' fill='white' opacity='.8'/></svg>">
<script type="application/ld+json">
{ld}
</script>
{template_style}
<style>
.sp-table {{ width:100%;border-collapse:collapse;font-size:13px; }}
.sp-table th {{ text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#98989d;padding:0 14px 12px;border-bottom:2px solid rgba(0,0,0,.08);white-space:nowrap; }}
.sp-table th.r {{ text-align:right; }}
.sp-table td {{ padding:12px 14px;border-bottom:1px solid rgba(0,0,0,.06);vertical-align:middle; }}
.sp-table tbody tr:hover td {{ background:#f5f5f7; }}
.lb-sbuy  {{ background:#16a34a;color:#fff; }}
.lb-buy   {{ background:#1a7ff0;color:#fff; }}
.lb-watch {{ background:#f59e0b;color:#fff; }}
.lb-caut  {{ background:#f97316;color:#fff; }}
.lb-avoid {{ background:#dc2626;color:#fff; }}
</style>
</head>
<body>
<nav class="nav">
  <a class="logo" href="../../index.html">
    <svg width="28" height="28" viewBox="0 0 30 30" fill="none">
      <rect width="30" height="30" rx="7" fill="#0d2d52"/>
      <rect x="6" y="16" width="4" height="9" rx="1.5" fill="white" opacity="0.65"/>
      <rect x="13" y="8" width="4" height="17" rx="1.5" fill="white"/>
      <rect x="20" y="12" width="4" height="13" rx="1.5" fill="white" opacity="0.8"/>
    </svg>
    <span class="logo-text">civi<em>ca</em></span>
  </a>
  <div class="nav-right">
    <span class="nav-tag">{state_name} · {count} Counties</span>
    <a class="nav-back" href="../../index.html">← All Counties</a>
  </div>
</nav>

<div class="hero" style="padding:56px 28px 64px;">
  <div style="max-width:960px;margin:0 auto;">
    <div class="hero-eyebrow">State Housing Report · 2026</div>
    <h1 style="font-size:44px;font-weight:900;color:#fff;margin:10px 0 16px;line-height:1.05;">{state_name}</h1>
    <div style="display:flex;gap:36px;flex-wrap:wrap;margin-bottom:22px;">
      <div><div style="font-size:28px;font-weight:900;color:#fff;">{count}</div><div style="font-size:12px;color:rgba(255,255,255,.5);">Counties Scored</div></div>
      <div><div style="font-size:28px;font-weight:900;color:#1a7ff0;">{median_score:.1f}</div><div style="font-size:12px;color:rgba(255,255,255,.5);">Median Score</div></div>
      <div><div style="font-size:28px;font-weight:900;color:#4ade80;">{top_score:.1f}</div><div style="font-size:12px;color:rgba(255,255,255,.5);">Top County Score</div></div>
      <div><div style="font-size:16px;font-weight:800;color:#fff;max-width:180px;">{top_name}</div><div style="font-size:12px;color:rgba(255,255,255,.5);">Top Ranked County</div></div>
    </div>
    <div style="font-size:13px;color:rgba(255,255,255,.45);">{dist_html}</div>
  </div>
</div>

<div class="page">
  <div class="card">
    <div class="card-title"><span class="ct-icon">📊</span> All {state_name} Counties — Ranked by Civica Score</div>
    <div style="overflow-x:auto;">
      <table class="sp-table">
        <thead>
          <tr>
            <th style="width:36px;">#</th>
            <th>County</th>
            <th>Score</th>
            <th>Label</th>
            <th class="r">Median Price</th>
            <th class="r">HPI 3yr</th>
            <th class="r">Avg Wage</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-top:12px;text-align:center;">
    <a href="../../index.html" style="display:inline-block;padding:12px 28px;background:#1a7ff0;color:#fff;border-radius:10px;font-weight:700;text-decoration:none;font-size:14px;">← Browse All 2,820 Counties</a>
  </div>

  <div class="footer">
    Data: FHFA HPI · BLS QCEW · BEA · FBI NIBRS 2024 · FEMA NFIP · NOAA Storm Events · USFS Wildfire · USDA RUCC · HUD FMR · IRS SOI · Census · Zillow ZHVI<br>
    Civica scores are for informational purposes only. Not financial, investment, or real estate advice. &copy; 2026 Civica.
  </div>
</div>
</body>
</html>'''


# ── Extract CSS from template ───────────────────────────────────────────────────

def extract_style(template_html: str) -> str:
    start = template_html.find('<style>')
    end   = template_html.find('</style>') + len('</style>')
    return template_html[start:end] if start != -1 else ''


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE, 'output'), exist_ok=True)

    print('Loading county_scores.csv...')
    df = pd.read_csv(SCORES, dtype={'fips': str})
    df['fips'] = df['fips'].str.zfill(5)
    print(f'  {len(df):,} counties loaded')

    # Reclassify labels using updated thresholds (no need to re-run scoring_engine.py)
    _LABELS = [
        (61, 'ACCELERATING'), (57, 'PEAKING'), (51, 'ESTABLISHED'),
        (45, 'EMERGING'), (37, 'FRONTIER'), (29, 'TURNING'),
        (24, 'SPECULATIVE'), (0, 'AVOID'),
    ]
    def _classify(s):
        for t, l in _LABELS:
            if s >= t: return l
        return 'AVOID'
    df['market_label'] = df['total_score'].apply(_classify)
    print('  Labels reclassified with updated thresholds')
    print(df['market_label'].value_counts().sort_values(ascending=False).to_string())

    print('Loading USDA RUCC for county names...')
    rucc_df = pd.read_excel(
        os.path.join(DATA, 'usda_rucc', 'ruralurbancodes2023.xlsx'),
        dtype={'FIPS': str}
    )
    rucc_df['FIPS'] = rucc_df['FIPS'].str.strip().str.zfill(5)

    # Build FIPS → name / state maps — try common column name variants
    name_col  = next((c for c in rucc_df.columns if 'county' in c.lower() or 'name' in c.lower()), None)
    state_col = next((c for c in rucc_df.columns if c.lower() == 'state'), None)

    if name_col is None or state_col is None:
        print(f'  RUCC columns: {list(rucc_df.columns)}')
        print('  WARNING: Could not find County_Name / State columns — using FIPS as name fallback')

    name_map  = dict(zip(rucc_df['FIPS'], rucc_df[name_col]))  if name_col  else {}
    state_map = dict(zip(rucc_df['FIPS'], rucc_df[state_col])) if state_col else {}

    print('Reading template HTML...')
    with open(TEMPLATE, encoding='utf-8') as f:
        template_html = f.read()
    template_style = extract_style(template_html)

    total = len(df)
    print(f'\nGenerating {total:,} county pages → {OUT_DIR}')

    index_records = []
    sitemap_urls  = [f'  <url><loc>{SITE_URL}/</loc></url>']

    for i, (_, row) in enumerate(df.iterrows(), 1):
        fips         = row['fips']
        county_name  = name_map.get(fips, f'County {fips}')
        state        = state_map.get(fips, '??')
        out_path     = os.path.join(OUT_DIR, f'{fips}.html')

        try:
            html = generate_page(row, county_name, state, template_style, df, name_map, state_map)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)
        except Exception as e:
            print(f'  ERROR {fips} {county_name}: {e}')
            continue

        # Index entry
        _trend  = compute_trend(row)
        _signal = compute_signal(float(row['total_score']), _trend)
        index_records.append({
            'fips':              fips,
            'name':              county_name,
            'state':             state,
            'score':             round(row['total_score'], 2),
            'signal':            _signal,
            'rank':              int(row['national_rank']),
            'dim1':              round(row['dim1'], 2),
            'dim2':              round(row['dim2'], 2),
            'dim3':              round(row['dim3'], 2),
            'dim4':              round(row['dim4'], 2),
            'dim5':              round(row['dim5'], 2),
            'dim6':              round(row['dim6'], 2),
            'median_home_value': round(row['median_home_value'], 0),
            'avg_annual_wage':   round(row['avg_annual_wage'],   0),
            'pr_ratio':          round(row['pr_ratio'],          2),
            'breakeven_yrs':     round(row['breakeven_yrs'],     2),
            'hpi_3yr_avg':       round(row['hpi_3yr_avg'],       2),
            'hpi_latest':        round(row['hpi_latest'],        2),
            'violent_per100k':   round(row['violent_per100k'],   1),
        })

        sitemap_urls.append(f'  <url><loc>{COUNTY_URL_BASE}/{fips}.html</loc></url>')

        if i % 200 == 0 or i == total:
            print(f'  {i:,}/{total:,} pages written')

    # Write index.json (sorted by score descending)
    index_records.sort(key=lambda x: x['score'], reverse=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(index_records, f, separators=(',', ':'))
    print(f'\nindex.json → {OUT_JSON}  ({len(index_records):,} records)')

    # Generate state pages
    print('\nGenerating state pages...')
    state_dir = os.path.join(BASE, 'output', 'states')
    os.makedirs(state_dir, exist_ok=True)

    state_groups: dict = {}
    for _, row in df.iterrows():
        fips = row['fips']
        st   = state_map.get(fips, '??')
        if st == '??':
            continue
        if st not in state_groups:
            state_groups[st] = []
        state_groups[st].append((row, name_map.get(fips, f'County {fips}')))

    for st, counties in sorted(state_groups.items()):
        counties.sort(key=lambda x: x[0]['total_score'], reverse=True)
        html = build_state_page(st, counties, template_style)
        path = os.path.join(state_dir, f'{st}.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        sitemap_urls.append(f'  <url><loc>{STATE_URL_BASE}/{st}.html</loc></url>')

    print(f'  {len(state_groups)} state pages written → {state_dir}')

    # Write sitemap.xml (includes county + state URLs)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '\n'.join(sitemap_urls)
    sitemap += '\n</urlset>'
    with open(OUT_SITE, 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f'sitemap.xml → {OUT_SITE}  ({len(sitemap_urls):,} URLs)')

    print(f'\nDone. {total:,} county pages + {len(state_groups)} state pages generated.')


if __name__ == '__main__':
    main()
