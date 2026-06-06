#!/usr/bin/env python3
"""
town_generator.py — Civica Town-Level Model
Reads town_scores.csv -> one HTML page per town in output/towns/{place_fips}.html,
plus output/town_index.json (front-page search) and output/towns/_progress.json (ledger).

Design system (colors, fonts, cards, score ring, dimension bars) is reused verbatim
from harvard_county_profile.html via extract_style(). The town report is intentionally
lean: one score ring, four dimension bars, a four-label verdict, an in-county rank line,
and the honest town/county data-coverage chip. No Zillow / price-to-rent / breakeven UI.

Usage:
  python town_generator.py              # generate every town in every state (one pass)
  python town_generator.py --state TX   # generate one state (loop / resume fallback)
"""

import os
import sys
import json
import argparse

import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE, 'harvard_county_profile.html')
SCORES = os.path.join(BASE, 'town_scores.csv')
OUT_DIR = os.path.join(BASE, 'output', 'towns')
OUT_INDEX = os.path.join(BASE, 'output', 'town_index.json')
PROGRESS = os.path.join(OUT_DIR, '_progress.json')
SITE_URL = 'https://civica.app'
TOWN_URL_BASE = f'{SITE_URL}/output/towns'
GA4_ID = ''

DIM_MAX = {'dim1': 28, 'dim2': 28, 'dim3': 26, 'dim4': 18}
DIM_NAMES = [
    ('dim1', 'Affordability', '🏠'),
    ('dim2', 'Economy', '💼'),
    ('dim3', 'Safety & Place', '🛡️'),
    ('dim4', 'Growth', '📈'),
]

# 4 labels -> existing vb pill styles (Strong Buy/Buy green/blue, Hold yellow, Caution red).
LABEL_PILL = {
    'Strong Buy': 'vb-accelerating',
    'Buy': 'vb-established',
    'Hold': 'vb-frontier',
    'Caution': 'vb-avoid',
}
LABEL_SUB = {
    'Strong Buy': 'Town fundamentals lead its county and the nation',
    'Buy': 'Solid fundamentals with room to run',
    'Hold': 'Balanced, middle-of-the-pack market',
    'Caution': 'Multiple fundamentals trail national peers',
}
LABEL_SIG = {
    'Strong Buy': ('sig-green', '✅'),
    'Buy': ('sig-green', '✅'),
    'Hold': ('sig-yellow', '👀'),
    'Caution': ('sig-red', '⚠️'),
}

STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee',
    'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
}


# ── Helpers ──────────────────────────────────────────────────────────────────────

def ring_offset(score):
    return f'{289.02 * (1 - score / 100):.2f}'


def money(v, fallback='N/A'):
    try:
        if pd.isna(v):
            return fallback
        return f'${v:,.0f}'
    except Exception:
        return fallback


def pctfmt(v, fallback='N/A', signed=False):
    try:
        if pd.isna(v):
            return fallback
        return f'{v:+.1f}%' if signed else f'{v:.1f}%'
    except Exception:
        return fallback


def extract_style(template_html):
    start = template_html.find('<style>')
    end = template_html.find('</style>') + len('</style>')
    return template_html[start:end] if start != -1 else ''


def rank_phrase(rank, total):
    if total <= 1:
        return 'the only scored town in the county'
    third = total / 3.0
    if rank <= max(1, third):
        return 'one of the strongest towns in its county'
    if rank <= 2 * third:
        return 'mid-pack among towns in its county'
    return 'below the stronger towns in its county'


# ── Page builders ────────────────────────────────────────────────────────────────

def build_head(row, place, state, county, score, label, fips, style):
    desc = (
        f"{place}, {state} scores {score:.0f}/100 on Civica's 4-dimension town housing model. "
        f"Signal: {label}. Ranks #{int(row['rank_in_county'])} of {int(row['towns_in_county'])} "
        f"towns in {county}. Town-level crime, income, and growth on 100% federal data."
    )
    url = f'{TOWN_URL_BASE}/{fips}.html'
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"{place}, {state} Housing Market Analysis", "description": desc, "url": url,
    }, separators=(',', ':'))
    crumb = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": county, "item": url},
            {"@type": "ListItem", "position": 3, "name": place, "item": url},
        ],
    }, separators=(',', ':'))
    ga = (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_ID}"></script>'
        f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
        f'gtag("js",new Date());gtag("config","{GA4_ID}");</script>'
    ) if GA4_ID else ''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{place}, {state} Town Housing Score — Civica Research</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{place}, {state} Town Housing Score — Civica">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<meta property="og:image" content="{SITE_URL}/og_image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE_URL}/og_image.png">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'><rect width='30' height='30' rx='7' fill='%230d2d52'/><rect x='6' y='16' width='4' height='9' rx='1.5' fill='white' opacity='.65'/><rect x='13' y='8' width='4' height='17' rx='1.5' fill='white'/><rect x='20' y='12' width='4' height='13' rx='1.5' fill='white' opacity='.8'/></svg>">
<script type="application/ld+json">{ld}</script>
<script type="application/ld+json">{crumb}</script>
{ga}
{style}
<style>
.dc-chip {{ display:inline-flex; flex-wrap:wrap; gap:6px; align-items:center; font-size:11px; color:rgba(255,255,255,.6); background:rgba(0,0,0,.2); border:1px solid rgba(255,255,255,.12); border-radius:100px; padding:6px 14px; margin-top:14px; }}
.dc-chip b {{ color:#4ade80; font-weight:700; }}
.dc-chip i {{ color:#fbbf24; font-style:normal; font-weight:700; }}
.rank-line {{ font-size:14px; color:#fff; font-weight:600; margin-top:16px; }}
.rank-line span {{ color:#4ade80; }}
.howto {{ background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:0 18px; margin-top:16px; }}
.howto summary {{ cursor:pointer; font-weight:700; font-size:14px; color:#0d2d52; padding:16px 0; list-style:none; }}
.howto summary::-webkit-details-marker {{ display:none; }}
.howto summary::before {{ content:'▸ '; color:#1a7ff0; }}
.howto[open] summary::before {{ content:'▾ '; }}
.howto-body {{ font-size:13px; line-height:1.6; color:#475569; padding:0 0 18px; }}
.schools-soon {{ opacity:.7; }}
.tcap {{ font-size:11px; color:#94a3b8; margin-top:6px; }}
</style>
</head>'''


def build_nav():
    return '''<nav class="nav">
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
    <span class="nav-tag" style="margin-right:8px;">Town Report</span>
    <a class="nav-back" href="../../index.html">← All Towns</a>
  </div>
</nav>'''


def build_hero(row, place, state, county):
    score = row['civica_score']
    pop = int(row['POPESTIMATE2025'])
    offset = ring_offset(score)
    label = row['market_label']
    pill = LABEL_PILL.get(label, 'vb-frontier')
    sub = LABEL_SUB.get(label, '')
    top_pct = max(1, round(row['national_rank'] / row['_n_national'] * 100))
    rk, tot = int(row['rank_in_county']), int(row['towns_in_county'])

    rent_burden_pct = row['rent_burden'] * 100
    rb_col = 'hp-green' if rent_burden_pct < 25 else ('hp-yellow' if rent_burden_pct < 35 else 'hp-red')
    hpi = row['hpi_3yr_avg']
    hpi_col = 'hp-green' if 3 <= hpi <= 9 else ('hp-yellow' if hpi > 9 else 'hp-red')
    vcrime = row['violent_per100k']
    vc_col = 'hp-green' if vcrime < 250 else ('hp-yellow' if vcrime < 500 else 'hp-red')
    g5 = row['town_growth_5yr'] * 100
    g_col = 'hp-green' if g5 > 2 else ('hp-yellow' if g5 > -2 else 'hp-red')
    crime_star = ' *' if int(row['crime_imputed']) == 1 else ''
    inc_star = ' *' if int(row['income_imputed']) == 1 else ''

    return f'''<div class="hero">
  <div class="hero-top">
    <div>
      <div class="hero-eyebrow">Town Research Report · 2026</div>
      <h1>{place}, {state}</h1>
      <div class="hero-sub">{county} · Pop. {pop:,}</div>
      <div class="rank-line">Ranks <span>#{rk} of {tot}</span> towns in {county} — {rank_phrase(rk, tot)}</div>
      <div class="dc-chip">Town-level: <b>crime · income · growth</b> &nbsp;·&nbsp; County-level: <i>economy · appreciation · climate</i></div>
    </div>
    <div style="display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap;">
      <div class="score-hero">
        <div class="vb-label" style="margin-bottom:4px;">Civica Score</div>
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
        <div class="vb-pill {pill}">{label}</div>
        <div class="vb-score">Score {score:.1f} · {sub}</div>
      </div>
    </div>
  </div>

  <div class="hero-pills">
    <div class="hero-pill"><span class="hp-lbl">Town Income</span><span class="hp-val hp-white">{money(row['town_income'])}{inc_star}</span></div>
    <div class="hero-pill"><span class="hp-lbl">Rent Burden</span><span class="hp-val {rb_col}">{rent_burden_pct:.0f}%</span></div>
    <div class="hero-pill"><span class="hp-lbl">Appreciation</span><span class="hp-val {hpi_col}">{hpi:+.1f}%/yr</span></div>
    <div class="hero-pill"><span class="hp-lbl">Violent Crime</span><span class="hp-val {vc_col}">{vcrime:.0f}/100k{crime_star}</span></div>
    <div class="hero-pill"><span class="hp-lbl">Pop Growth 5yr</span><span class="hp-val {g_col}">{g5:+.1f}%</span></div>
    <div class="hero-pill"><span class="hp-lbl">Town Scale</span><span class="hp-val hp-white">{row['town_scale_pct']:.0f} pctl</span></div>
  </div>
</div>'''


def build_dimension_card(row):
    bars = ''
    palette = ['#1a7ff0', '#16a34a', '#8b5cf6', '#f59e0b']
    for (col, name, icon), color in zip(DIM_NAMES, palette):
        val = row[col] / DIM_MAX[col] * 100
        bars += f'''
      <div class="bar-row">
        <div class="bar-lbl">{icon} {name}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{val:.0f}%;background:{color};"></div></div>
        <div class="bar-val">{val:.0f}/100</div>
      </div>'''
    return f'''<div class="card">
    <div class="card-title"><span class="ct-icon">📊</span> Four-Dimension Breakdown</div>
    <div class="bar-chart">{bars}
    </div>
    <div class="tcap">Each dimension is a national percentile blend (0–100). Affordability 28 pts ·
      Economy 28 · Safety &amp; Place 26 · Growth 18. Town-resolved metrics (crime, income, growth,
      scale) account for ~51% of the score; the rest is inherited from {row['county_name']}.</div>
  </div>'''


def build_verdict_card(row, place):
    label = row['market_label']
    sig_cls, icon = LABEL_SIG.get(label, ('sig-yellow', '👀'))
    dims = {name: row[col] / DIM_MAX[col] * 100 for col, name, _ in DIM_NAMES}
    top = max(dims, key=dims.get)
    bot = min(dims, key=dims.get)
    verdict = {
        'Strong Buy': f'{place} is a <strong>Strong Buy</strong>. Its strongest dimension is '
                      f'{top} ({dims[top]:.0f}/100), and town-level fundamentals lead both its '
                      f'county and most of the nation.',
        'Buy': f'{place} is a <strong>Buy</strong>. {top} ({dims[top]:.0f}/100) anchors solid '
               f'fundamentals; watch {bot} ({dims[bot]:.0f}/100) as the softer dimension.',
        'Hold': f'{place} is a <strong>Hold</strong> — a balanced, middle-of-the-pack market. '
                f'{top} ({dims[top]:.0f}/100) is the bright spot; {bot} ({dims[bot]:.0f}/100) lags.',
        'Caution': f'{place} warrants <strong>Caution</strong>. {bot} ({dims[bot]:.0f}/100) and '
                   f'other fundamentals trail national peers; even {top} ({dims[top]:.0f}/100) is '
                   f'only middling.',
    }.get(label, '')
    return f'''<div class="signal {sig_cls}" style="margin:0 0 16px;">
    <div class="icon">{icon}</div>
    <div class="body" style="font-size:14px;"><strong>Civica Verdict:</strong> {verdict}</div>
  </div>'''


def build_fundamentals_card(row):
    crime_note = (' <span class="tcap" style="display:inline;">(county/RUCC-tier rate — no '
                  'municipal agency matched)</span>') if int(row['crime_imputed']) == 1 else ''
    inc_note = (' <span class="tcap" style="display:inline;">(county fallback — no ZIP '
                'allocation)</span>') if int(row['income_imputed']) == 1 else ''
    rb = row['rent_burden'] * 100
    return f'''<div class="card">
    <div class="card-title"><span class="ct-icon">📋</span> The Numbers</div>
    <div class="g3">
      <div class="sb"><div class="sb-val">{money(row['town_income'])}</div><div class="sb-lbl">Town income / return (IRS ZIP){inc_note}</div></div>
      <div class="sb"><div class="sb-val">{rb:.0f}%</div><div class="sb-lbl">Rent burden (2BR FMR ÷ income)</div></div>
      <div class="sb"><div class="sb-val">{row['hpi_3yr_avg']:+.1f}%</div><div class="sb-lbl">3yr appreciation (FHFA)</div></div>
      <div class="sb"><div class="sb-val">{money(row['avg_annual_wage'])}</div><div class="sb-lbl">Avg annual wage (BLS QCEW)</div></div>
      <div class="sb"><div class="sb-val">{row['violent_per100k']:.0f}</div><div class="sb-lbl">Violent crime / 100k (NIBRS){crime_note}</div></div>
      <div class="sb"><div class="sb-val">{row['property_per100k']:.0f}</div><div class="sb-lbl">Property crime / 100k (NIBRS)</div></div>
      <div class="sb"><div class="sb-val">{row['town_growth_5yr']*100:+.1f}%</div><div class="sb-lbl">Town pop growth, 5yr (Census)</div></div>
      <div class="sb"><div class="sb-val">{row['town_income_growth']*100:+.1f}%</div><div class="sb-lbl">Town income growth (IRS ZIP)</div></div>
      <div class="sb"><div class="sb-val">{row['RNETMIG2023']:+.1f}</div><div class="sb-lbl">County net migration / 1k (Census)</div></div>
    </div>
  </div>'''


def build_schools_card():
    # Schools (coming soon) — clean slot for a future data layer (TOWN_HANDOFF.md §1).
    return '''<div class="card schools-soon">
    <div class="card-title"><span class="ct-icon">🎓</span> Schools <span style="font-size:10px;color:#94a3b8;font-weight:600;">(coming soon)</span></div>
    <div class="tcap">School-quality data is not yet part of the town model. It will be added here
      as a dedicated dimension in a future release.</div>
  </div>'''


def build_howto(row):
    return f'''<details class="howto">
    <summary>How we scored this</summary>
    <div class="howto-body">
      The Civica Score blends four dimensions into a single 0–100 number, percentile-ranked
      across {int(row['_n_national']):,} US towns. Roughly <strong>51% is town-resolved</strong>
      — crime (FBI NIBRS, mapped from reporting agencies to places), income (IRS SOI ZIP-code AGI
      allocated to places by land-area overlap), and population growth/scale (Census sub-county
      estimates). The other <strong>~49% is inherited from {row['county_name']}</strong> — wages,
      sector mix, home-price appreciation, climate risk, migration, and permits — because those
      genuinely operate at a regional scale and faking them per-town would be dishonest.
      <br><br>
      <strong>Honest caveats:</strong> town income is a ZIP→place address-share approximation, not
      a survey median. Crime is mapped via agency name; county sheriffs cover unincorporated area,
      and towns with no matched reporting agency inherit the county/RUCC-tier rate (flagged, never
      penalized). There is no home-value level — affordability is rent-vs-income plus appreciation
      quality. The universe is incorporated places ≥ 1,000 people (CDPs excluded for now).
      Every input is now a <strong>federal</strong> source.
    </div>
  </details>'''


FOOTER = '''<div class="footer">
  100% federal data: FBI NIBRS 2024 · IRS SOI (ZIP AGI + migration) · Census Population Estimates
  (sub-county) · BLS QCEW · BEA · FHFA HPI · HUD FMR FY2026 · Census CBP/BPS · FEMA NFIP ·
  NOAA Storm Events · USFS Wildfire · USDA RUCC.<br>
  ~49% of each town's score is county-inherited (wages, appreciation, climate, migration, permits) —
  regional by nature. Town income is a ZIP→place approximation; crime→town mapping is approximate.
  Civica scores are informational only — not financial, investment, or real estate advice.<br><br>
  <strong>civi<em style="font-style:normal;color:#1a7ff0;">ca</em></strong> — research-grade town intelligence for homebuyers
</div>'''


def generate_page(row, style):
    place = str(row['place_name'])
    state = str(row['state_abbr'])
    county = str(row['county_name'])
    fips = str(row['fips']).zfill(7)
    score = row['civica_score']
    label = row['market_label']
    return f'''{build_head(row, place, state, county, score, label, fips, style)}
<body>
{build_nav()}
{build_hero(row, place, state, county)}
<div class="page">
  {build_verdict_card(row, place)}
  {build_dimension_card(row)}
  {build_fundamentals_card(row)}
  {build_howto(row)}
  {build_schools_card()}
  {FOOTER}
</div>
</body>
</html>'''


# ── Index + progress ledger ──────────────────────────────────────────────────────

def load_index():
    if os.path.exists(OUT_INDEX):
        try:
            return {r['fips']: r for r in json.load(open(OUT_INDEX, encoding='utf-8'))}
        except Exception:
            return {}
    return {}


def write_index(index_map):
    records = sorted(index_map.values(), key=lambda x: x['score'], reverse=True)
    json.dump(records, open(OUT_INDEX, 'w', encoding='utf-8'), separators=(',', ':'))
    return len(records)


def load_progress(all_states):
    if os.path.exists(PROGRESS):
        try:
            p = json.load(open(PROGRESS, encoding='utf-8'))
            p.setdefault('done', [])
            p['all'] = all_states
            return p
        except Exception:
            pass
    return {'done': [], 'all': all_states}


def write_progress(p):
    json.dump(p, open(PROGRESS, 'w', encoding='utf-8'), indent=2)


def write_sitemap(index_map):
    """Regenerate sitemap.xml from town URLs + the core static pages."""
    static = ['', 'disclaimer.html', 'privacy.html', 'terms.html', 'harvard_model.html']
    urls = [f'  <url><loc>{SITE_URL}/{p}</loc></url>' for p in static]
    for fips in sorted(index_map):
        urls.append(f'  <url><loc>{TOWN_URL_BASE}/{fips}.html</loc></url>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + '\n'.join(urls) + '\n</urlset>')
    with open(os.path.join(BASE, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(xml)
    return len(urls)


# ── Main ─────────────────────────────────────────────────────────────────────────

def generate_state(state_df, style, index_map):
    """Generate every town page for one state; update index_map in place. Returns count."""
    for _, row in state_df.iterrows():
        fips = str(row['fips']).zfill(7)
        html = generate_page(row, style)
        with open(os.path.join(OUT_DIR, f'{fips}.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        index_map[fips] = {
            'fips': fips, 'name': str(row['place_name']), 'state': str(row['state_abbr']),
            'county': str(row['county_name']), 'score': round(float(row['civica_score']), 2),
            'label': str(row['market_label']),
            'dim1': round(float(row['dim1']), 2), 'dim2': round(float(row['dim2']), 2),
            'dim3': round(float(row['dim3']), 2), 'dim4': round(float(row['dim4']), 2),
            'rank_in_county': int(row['rank_in_county']),
        }
    return len(state_df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', help='2-letter state to generate (default: all states)')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(SCORES, dtype={'fips': str, 'primary_county_fips': str})
    df['fips'] = df['fips'].str.zfill(7)
    df['_n_national'] = len(df)

    with open(TEMPLATE, encoding='utf-8') as f:
        style = extract_style(f.read())

    all_states = sorted(df['state_abbr'].dropna().unique().tolist())
    index_map = load_index()
    progress = load_progress(all_states)

    targets = [args.state.upper()] if args.state else all_states

    for st in targets:
        sdf = df[df['state_abbr'] == st]
        if sdf.empty:
            print(f'  {st}: no towns, skipping')
            continue
        n = generate_state(sdf, style, index_map)
        if st not in progress['done']:
            progress['done'].append(st)
        write_progress(progress)
        write_index(index_map)
        print(f'  {st} ({STATE_NAMES.get(st, st)}): {n} towns -> output/towns/')

    total = write_index(index_map)
    remaining = [s for s in all_states if s not in progress['done']]
    # Regenerate the sitemap once everything is built (idempotent).
    if not remaining:
        n_urls = write_sitemap(index_map)
        print(f'  sitemap.xml regenerated: {n_urls:,} URLs')
    print(f'\nDone. town_index.json: {total:,} towns. '
          f'States done: {len(progress["done"])}/{len(all_states)}. '
          f'Remaining: {len(remaining)}')


if __name__ == '__main__':
    main()
