#!/usr/bin/env python3
"""
Civica Scoring Engine v1.3
Harvard-style 6-dimension housing market analysis for all US counties.

v1.3 changes vs v1.2:
  - Dim1 home values: Zillow ZHVI → ACS 5-year B25077 (federal source)
  - Dim3 Supply Tightness (Zillow inventory) removed; weights redistributed:
      3yr trend 50%, current momentum 20%, permit pipeline 30%
  - home_value_imputed flag added to output

Dimensions:
  1. Affordability & Value       25 pts
  2. Economic Vitality           22 pts
  3. Housing Market Dynamics     20 pts
  4. Quality of Place            15 pts
  5. Physical Risk               12 pts  (lower raw risk = higher score)
  6. Population Momentum          6 pts
                                -------
  Total                         100 pts

Output: county_scores.csv — one row per county with scores, label, and raw metrics.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')  # Windows UTF-8

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'civica_data')
OUT  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'county_scores.csv')


# ── Utilities ──────────────────────────────────────────────────────────────────

def to_fips5(state, county):
    try:
        return str(int(state)).zfill(2) + str(int(county)).zfill(3)
    except (ValueError, TypeError):
        return None


def pct(s):
    """National percentile rank 0-100: higher raw value = higher score."""
    return s.rank(pct=True, na_option='keep') * 100


def pct_inv(s):
    """National percentile rank 0-100: lower raw value = higher score."""
    return (1 - s.rank(pct=True, na_option='keep')) * 100


def parse_damage(v):
    """Convert NOAA storm damage strings ('5.00K', '1.50M') to float dollars."""
    if pd.isna(v) or str(v).strip() == '':
        return 0.0
    v = str(v).strip().upper()
    if v.endswith('K'):  return float(v[:-1]) * 1_000
    if v.endswith('M'):  return float(v[:-1]) * 1_000_000
    if v.endswith('B'):  return float(v[:-1]) * 1_000_000_000
    try:
        return float(v)
    except ValueError:
        return 0.0


# ── Data Loaders ───────────────────────────────────────────────────────────────

def load_population():
    """Census Population Estimates 2023 — base universe of counties."""
    df = pd.read_csv(
        f'{DATA}/census_population/co-est2023-alldata.csv',
        encoding='latin1'
    )
    df = df[df['SUMLEV'] == 50].copy()  # county level only
    df['fips'] = df.apply(lambda r: to_fips5(r['STATE'], r['COUNTY']), axis=1)
    return df[['fips', 'POPESTIMATE2023', 'RNETMIG2023',
               'RDOMESTICMIG2023', 'RINTERNATIONALMIG2023',
               'NETMIG2023', 'DOMESTICMIG2023']].dropna(subset=['fips'])


def load_bea():
    """BEA CAINC1: per capita personal income (LineCode=3), 2024 latest."""
    df = pd.read_csv(
        f'{DATA}/bea_income/CAINC1__ALL_AREAS_1969_2024.csv',
        encoding='latin1'
    )
    df = df[df['LineCode'] == 3].copy()
    df['fips'] = df['GeoFIPS'].str.strip().str.strip('"').str.strip().str.zfill(5)
    df = df[~df['fips'].str.endswith('000')]  # drop state/national totals

    year_cols = sorted([c for c in df.columns if c.isdigit()])
    latest = year_cols[-1]
    prior  = str(int(latest) - 4)
    if prior not in year_cols:
        prior = year_cols[-5]

    df['per_capita_income']  = pd.to_numeric(df[latest], errors='coerce')
    df['income_prior']       = pd.to_numeric(df[prior],  errors='coerce')
    df['income_4yr_growth']  = (df['per_capita_income'] / df['income_prior'] - 1) * 100
    return df[['fips', 'per_capita_income', 'income_4yr_growth']].dropna(subset=['fips'])


def load_home_values():
    """ACS 5-year (2023) median home value (B25077) by county.
    Downloads from Census API on first run and caches to civica_data/census_acs/.
    Missing values flagged via home_value_imputed; imputed with RUCC-tier median in main().
    """
    import json, urllib.request

    acs_dir  = f'{DATA}/census_acs'
    acs_path = f'{acs_dir}/acs5_home_values_2023.csv'

    if not os.path.exists(acs_path):
        api_key = os.environ.get('CENSUS_API_KEY', '')
        if not api_key:
            raise RuntimeError(
                '\n\nCensus API key required to download ACS home values.\n'
                'Get a free key (takes ~2 min) at:\n'
                '  https://api.census.gov/data/key_signup.html\n\n'
                'Then set it before running:\n'
                '  Windows:  set CENSUS_API_KEY=your_key_here\n'
                '  Mac/Linux: export CENSUS_API_KEY=your_key_here\n'
            )
        print('    Fetching ACS 5-yr home values from Census API...')
        url = (f'https://api.census.gov/data/2023/acs/acs5'
               f'?get=GEO_ID,B25077_001E&for=county:*&in=state:*&key={api_key}')
        with urllib.request.urlopen(url, timeout=60) as resp:
            raw = json.loads(resp.read())
        os.makedirs(acs_dir, exist_ok=True)
        pd.DataFrame(raw[1:], columns=raw[0]).to_csv(acs_path, index=False)

    df = pd.read_csv(acs_path, dtype=str)
    df['fips'] = df['GEO_ID'].str[-5:]
    df['median_home_value'] = pd.to_numeric(df['B25077_001E'], errors='coerce')
    df.loc[df['median_home_value'] < 0, 'median_home_value'] = np.nan  # Census null sentinel (-666666666)
    df['home_value_imputed'] = False
    return df[['fips', 'median_home_value', 'home_value_imputed']].dropna(subset=['fips'])


def load_fmr():
    """HUD FY2026 Fair Market Rents: 2BR as median rent proxy."""
    df = pd.read_excel(
        f'{DATA}/hud_fmr/FY26_FMRs_revised.xlsx',
        engine='calamine'
    )
    # HUD fips format: state_int + county_3digit + "99999" suffix
    # e.g. Autauga AL = 100199999 → 100199999 // 100000 = 1001 → "01001"
    df['fips'] = (df['fips'].astype(float).astype(int) // 100000).astype(str).str.zfill(5)
    df['fmr_2br'] = pd.to_numeric(df['fmr_2'], errors='coerce')
    return df.groupby('fips')['fmr_2br'].mean().reset_index()


def load_hpi():
    """FHFA HPI: 3-year average annual appreciation + latest annual change."""
    df = pd.read_excel(f'{DATA}/fhfa_hpi/hpi_at_county.xlsx', header=5)
    df.columns = ['state', 'county', 'fips', 'year', 'annual_chg', 'hpi', 'hpi90', 'hpi2000']
    df = df.dropna(subset=['fips'])
    df['fips']      = df['fips'].astype(float).astype(int).astype(str).str.zfill(5)
    df['year']      = pd.to_numeric(df['year'],      errors='coerce')
    df['annual_chg'] = pd.to_numeric(df['annual_chg'], errors='coerce')

    max_yr  = df['year'].max()
    recent  = df[df['year'] >= max_yr - 2]
    avg3    = recent.groupby('fips')['annual_chg'].mean().reset_index()
    avg3.columns = ['fips', 'hpi_3yr_avg']

    latest_yr = df[df['year'] == max_yr][['fips', 'annual_chg']].rename(
        columns={'annual_chg': 'hpi_latest'}
    )
    return avg3.merge(latest_yr, on='fips', how='left')


def load_qcew():
    """BLS QCEW 2023: wages, employment size, sector quality score, HHI."""
    print("    Streaming BLS QCEW (531 MB)...")
    totals, sectors = [], []

    for chunk in pd.read_csv(
        f'{DATA}/bls_qcew/2023.annual.singlefile.csv',
        chunksize=500_000,
        dtype={'area_fips': str, 'industry_code': str}
    ):
        county = chunk[
            chunk['area_fips'].str.len().eq(5) &
            ~chunk['area_fips'].str.endswith('000')
        ]
        private = county[county['own_code'] == 5]

        # own_code=5 + industry_code='10' → total private sector per county
        totals.append(
            private[private['industry_code'] == '10']
            [['area_fips', 'annual_avg_emplvl', 'avg_annual_pay']].copy()
        )
        # own_code=5 + 2-digit NAICS (excluding '10') → private by supersector
        sectors.append(
            private[
                private['industry_code'].str.len().eq(2) &
                (private['industry_code'] != '10')
            ][['area_fips', 'industry_code', 'annual_avg_emplvl']].copy()
        )

    total_df = pd.concat(totals, ignore_index=True).rename(columns={'area_fips': 'fips'})
    total_df['annual_avg_emplvl'] = pd.to_numeric(total_df['annual_avg_emplvl'], errors='coerce')
    total_df['avg_annual_pay']    = pd.to_numeric(total_df['avg_annual_pay'],    errors='coerce')
    agg = total_df.groupby('fips').agg(
        private_employment=('annual_avg_emplvl', 'sum'),
        avg_annual_wage=('avg_annual_pay', 'mean')
    ).reset_index()

    sec_df = pd.concat(sectors, ignore_index=True).rename(columns={'area_fips': 'fips'})
    sec_df['annual_avg_emplvl'] = pd.to_numeric(sec_df['annual_avg_emplvl'], errors='coerce').fillna(0)
    sec_df['naics2'] = sec_df['industry_code'].astype(str).str[:2]

    # Sector quality weights per CLAUDE.md spec (unspecified NAICS = 1.00 neutral)
    WEIGHTS = {
        '54': 1.30,  # Professional/Scientific/Technical
        '52': 1.30,  # Finance & Insurance
        '62': 1.00,  # Healthcare
        '61': 1.00,  # Education
        '23': 0.80,  # Construction (cyclical leading indicator)
        '44': 0.60,  # Retail (secular decline risk)
        '45': 0.60,  # Retail
        '31': 0.60,  # Legacy Manufacturing
        '32': 0.60,  # Legacy Manufacturing
        '33': 0.60,  # Legacy Manufacturing
    }
    sec_df['weight'] = sec_df['naics2'].map(WEIGHTS).fillna(1.00)

    def _sector_quality(g):
        tot = g['annual_avg_emplvl'].sum()
        return (g['annual_avg_emplvl'] * g['weight']).sum() / tot if tot > 0 else np.nan

    def _hhi(g):
        tot = g['annual_avg_emplvl'].sum()
        if tot == 0:
            return np.nan
        return ((g['annual_avg_emplvl'] / tot) ** 2).sum() * 10_000  # 0–10,000 scale

    sq  = sec_df.groupby('fips').apply(_sector_quality).reset_index(name='sector_quality')
    hhi = sec_df.groupby('fips').apply(_hhi).reset_index(name='hhi')
    return agg.merge(sq, on='fips', how='left').merge(hhi, on='fips', how='left')


def load_cbp():
    """Census CBP 2022: total establishments per county (amenity density proxy)."""
    print("    Reading Census CBP (106 MB)...")
    df = pd.read_csv(f'{DATA}/census_cbp/cbp22co.txt', dtype=str, low_memory=False)
    df['fips'] = df['fipstate'].str.zfill(2) + df['fipscty'].str.zfill(3)
    total = df[df['naics'] == '------'][['fips', 'est']].copy()
    total['establishments'] = pd.to_numeric(total['est'], errors='coerce')
    return total.groupby('fips')['establishments'].sum().reset_index()


def load_bps():
    """Census Building Permits Survey 2022: total new housing units permitted."""
    # BPS county file: 2-row header + 1 blank line, then data
    # Cols: 0=year, 1=state_fips, 2=county_fips, 3=region, 4=division, 5=name
    #        6=1unit_bldg, 7=1unit_units, 8=1unit_val
    #        9=2unit_bldg, 10=2unit_units, ...  15=5+unit_bldg, 16=5+unit_units
    df = pd.read_csv(
        f'{DATA}/census_bps/co2022a.txt',
        skiprows=3, header=None, dtype=str
    )
    df = df.dropna(subset=[1])  # drop blank rows
    df['fips'] = df[1].str.strip().str.zfill(2) + df[2].str.strip().str.zfill(3)
    for col in [7, 10, 13, 16]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['total_permits'] = df[7] + df[10] + df[13] + df[16]
    return df.groupby('fips')['total_permits'].sum().reset_index()


def load_irs():
    """IRS Migration 2022-2023: in-mover income quality (inflow AGI / outflow AGI)."""
    def _clean(df, dest_state_col, dest_county_col, origin_state_col):
        df = df.copy()
        df[origin_state_col] = pd.to_numeric(df[origin_state_col], errors='coerce')
        df = df[~df[origin_state_col].isin([96, 97, 98, 99])]  # drop totals/special codes
        df['fips'] = (df[dest_state_col].astype(str).str.zfill(2) +
                      df[dest_county_col].astype(str).str.zfill(3))
        df['n1']  = pd.to_numeric(df['n1'],  errors='coerce')
        df['agi'] = pd.to_numeric(df['agi'], errors='coerce')
        return df

    inf = pd.read_csv(f'{DATA}/irs_migration/countyinflow2223.csv',  encoding='latin1')
    out = pd.read_csv(f'{DATA}/irs_migration/countyoutflow2223.csv', encoding='latin1')

    inf = _clean(inf, 'y2_statefips', 'y2_countyfips', 'y1_statefips')  # into destination (y2)
    out = _clean(out, 'y1_statefips', 'y1_countyfips', 'y2_statefips')  # out of origin (y1)

    inf_g = inf.groupby('fips').agg(in_hh=('n1','sum'), in_agi=('agi','sum')).reset_index()
    out_g = out.groupby('fips').agg(out_hh=('n1','sum'), out_agi=('agi','sum')).reset_index()

    m = inf_g.merge(out_g, on='fips', how='outer')
    m['in_avg_agi']  = m['in_agi']  / m['in_hh'].clip(lower=1)
    m['out_avg_agi'] = m['out_agi'] / m['out_hh'].clip(lower=1)
    # Ratio > 1 means higher-income people moving in than leaving (positive demand signal)
    m['inmover_income_ratio'] = m['in_avg_agi'] / m['out_avg_agi'].clip(lower=1)
    return m[['fips', 'inmover_income_ratio', 'in_hh', 'out_hh']]


def load_nfip():
    """FEMA NFIP: flood insurance claims paid, 2014-2023 (10-year window)."""
    df = pd.read_csv(
        f'{DATA}/fema_nfip/fema_nfip_claims.csv',
        dtype={'countyCode': str},
        low_memory=False
    )
    df['fips'] = df['countyCode'].str.zfill(5)
    df['paid'] = (
        pd.to_numeric(df['amountPaidOnBuildingClaim'], errors='coerce').fillna(0) +
        pd.to_numeric(df['amountPaidOnContentsClaim'], errors='coerce').fillna(0)
    )
    if 'yearOfLoss' in df.columns:
        df['yr'] = pd.to_numeric(df['yearOfLoss'], errors='coerce')
        df = df[df['yr'] >= 2014]
    return df.groupby('fips')['paid'].sum().reset_index().rename(columns={'paid': 'nfip_claims'})


def load_noaa_storm():
    """NOAA Storm Events 2019-2023: property damage by county."""
    print("    Reading NOAA Storm Events (5 files, ~323 MB)...")
    parts = []
    storm_dir = f'{DATA}/noaa_storm_events'
    for fn in sorted(os.listdir(storm_dir)):
        if not fn.endswith('.csv'):
            continue
        df = pd.read_csv(
            f'{storm_dir}/{fn}',
            dtype={'STATE_FIPS': str, 'CZ_FIPS': str},
            usecols=['STATE_FIPS', 'CZ_FIPS', 'CZ_TYPE', 'DAMAGE_PROPERTY'],
            low_memory=False
        )
        df = df[df['CZ_TYPE'] == 'C'].copy()  # county zones only (not forecast zones)
        df['fips']   = df['STATE_FIPS'].str.zfill(2) + df['CZ_FIPS'].str.zfill(3)
        df['damage'] = df['DAMAGE_PROPERTY'].apply(parse_damage)
        parts.append(df[['fips', 'damage']])

    combined = pd.concat(parts, ignore_index=True)
    return combined.groupby('fips')['damage'].sum().reset_index().rename(
        columns={'damage': 'storm_damage'}
    )


def load_usfs():
    """USFS Wildfire Risk: national rank by county (0=safest, 1=highest risk)."""
    df = pd.read_excel(
        f'{DATA}/usfs_wildfire/wrc_download_20260415.xlsx',
        sheet_name='Counties'
    )
    df['fips'] = df['GEOID'].astype(str).str.zfill(5)
    return df[['fips', 'RISK_NATIONAL_RANK']].rename(columns={'RISK_NATIONAL_RANK': 'wildfire_rank'})


def load_rucc():
    """USDA Rural-Urban Continuum Codes 2023: 1=largest metro, 9=most rural."""
    df = pd.read_excel(f'{DATA}/usda_rucc/ruralurbancodes2023.xlsx')
    df['fips'] = df['FIPS'].astype(str).str.zfill(5)
    return df[['fips', 'RUCC_2023']].rename(columns={'RUCC_2023': 'rucc'})


def load_nibrs_crime():
    """FBI NIBRS 2024: violent crime rate per 100k residents by county.

    Field positions discovered empirically from the National Master File format:
      BH record: ORI = chars 3-11 (0-indexed 2:11); county 3-digit FIPS = chars 270-272 (269:272)
      02 record: ORI = chars 3-11 (2:11); NIBRS offense code = chars 34-36 (33:36)

    Violent crime codes (FBI NIBRS Group A):
      09A=Murder, 09B=Negligent Manslaughter, 100=Kidnapping,
      11A=Rape, 11B=Sodomy, 11C=Sexual Assault w/ Object, 11D=Fondling,
      120=Robbery, 13A=Aggravated Assault, 13B=Simple Assault, 13C=Intimidation
    """
    print("    Streaming FBI NIBRS 2024 (5.8 GB) — this takes ~10 minutes...")

    VIOLENT = {'09A','09B','100','11A','11B','11C','11D','120','13A','13B','13C'}

    STATE_FIPS = {
        'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09',
        'DE':'10','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18',
        'IA':'19','KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25',
        'MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32',
        'NH':'33','NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39',
        'OK':'40','OR':'41','PA':'42','RI':'44','SC':'45','SD':'46','TN':'47',
        'TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55',
        'WY':'56','DC':'11'
    }

    ori_to_fips  = {}   # 9-char ORI -> 5-char county FIPS
    violent_cnts = {}   # 5-char county FIPS -> int count

    fpath = f'{DATA}/fbi_crime/2024_NIBRS_NATIONAL_MASTER_FILE.txt'
    with open(fpath, 'r', encoding='latin1', errors='replace') as f:
        for line in f:
            seg = line[:2]

            if seg == 'BH' and len(line) >= 272:
                ori         = line[2:11]            # 9-char ORI
                state_alpha = line[4:6]             # embedded state abbrev
                county3     = line[269:272].strip() # 3-digit county FIPS
                state_fips  = STATE_FIPS.get(state_alpha)
                if state_fips and county3.isdigit() and len(county3) == 3:
                    ori_to_fips[ori] = state_fips + county3

            elif seg == '02' and len(line) >= 36:
                ori    = line[2:11]
                code   = line[33:36].strip()
                fips5  = ori_to_fips.get(ori)
                if fips5 and code in VIOLENT:
                    violent_cnts[fips5] = violent_cnts.get(fips5, 0) + 1

    print(f"    Parsed {len(ori_to_fips):,} agencies across "
          f"{len({v[:2] for v in ori_to_fips.values()})} states")
    print(f"    Violent offenses counted: {sum(violent_cnts.values()):,}")
    print(f"    Counties with crime data: {len(violent_cnts):,}")

    crime_df = pd.DataFrame(
        list(violent_cnts.items()), columns=['fips', 'violent_offenses']
    )
    return crime_df


# ── Scoring Functions ──────────────────────────────────────────────────────────
# Each function receives the merged dataframe and returns it with a new dim_N column.
# Percentile normalization is applied within each metric nationally, then weighted.

def score_dim1(df):
    """Affordability & Value — 25 pts.
    P/R Ratio 30% | Price/Income 30% | Buy-Rent Breakeven 25% | Appreciation Quality 15%
    """
    d = df.copy()
    d['annual_rent']  = d['fmr_2br'] * 12
    d['pr_ratio']     = d['median_home_value'] / d['annual_rent'].clip(lower=1)
    d['price_income'] = d['median_home_value'] / d['per_capita_income'].clip(lower=1)

    # Breakeven: years to recover 20% down payment through ownership savings vs. renting.
    # Assumes 7% 30yr fixed (2024 national rate), 1.2% annual property tax, 0.5% insurance.
    # Cap at 30 years — markets where PITI < rent have negative excess (buy wins immediately).
    # KNOWN LIMITATION: 1.2% property tax is the national median effective rate.
    # Actual rates range 0.28% (HI) to 2.23% (NJ/IL) — error up to $340/mo at $400k home value.
    # State-level effective rates from Lincoln Institute of Land Policy are a candidate fix (v1.3).
    r = 0.07 / 12
    mortgage_factor = r / (1 - (1 + r) ** -360)
    d['monthly_piti'] = (
        d['median_home_value'] * 0.80 * mortgage_factor
        + d['median_home_value'] * 0.012 / 12   # property tax — see limitation note above
        + d['median_home_value'] * 0.005 / 12
    )
    d['monthly_excess'] = (d['monthly_piti'] - d['fmr_2br']).clip(lower=1)
    d['breakeven_yrs']  = (d['median_home_value'] * 0.20 / (d['monthly_excess'] * 12)).clip(0, 30)

    # Appreciation quality: penalizes stagnation (<3%) and froth (>7%), rewards 3–7% range.
    d['appr_deviation'] = (d['hpi_3yr_avg'].clip(-5, 25) - 5.0).abs()

    s1 = pct_inv(d['pr_ratio'])       # 30%: lower P/R = better buy vs. rent
    s2 = pct_inv(d['price_income'])   # 30%: lower price/income = more affordable
    s3 = pct_inv(d['breakeven_yrs'])  # 25%: shorter breakeven = stronger buy case
    s4 = pct_inv(d['appr_deviation']) # 15%: deviation from healthy 3–7% band

    d['dim1'] = (s1*0.30 + s2*0.30 + s3*0.25 + s4*0.15) / 100 * 25
    return d


def score_dim2(df):
    """Economic Vitality — 22 pts.
    Wage Level 35% | Sector Quality 25% | Economic Diversity 25% | Income Growth 15%
    """
    d = df.copy()
    s1 = pct(d['avg_annual_wage'])     # 35%: wage level (proxy for real wage strength)
    s2 = pct(d['sector_quality'])      # 25%: quality-weighted sector mix (Prof/Finance premium)
    s3 = pct_inv(d['hhi'])            # 25%: lower HHI = more diversified = more resilient
    s4 = pct(d['income_4yr_growth'])   # 15%: real income trajectory (BEA per capita growth)

    d['dim2'] = (s1*0.35 + s2*0.25 + s3*0.25 + s4*0.15) / 100 * 22
    return d


def score_dim3(df):
    """Housing Market Dynamics — 20 pts (v1.3 — all-federal).
    3yr Appreciation Trend 50% | Current Momentum 20% | Permit Pipeline 30%

    Supply Tightness (Zillow inventory) removed in v1.3. The 30% redistributed:
    +15% to 3yr trend (dominant price signal), +10% to permits (supply counter-signal),
    +5% to current momentum (cross-validation). Result: 50 / 20 / 30 split.
    """
    d = df.copy()
    s1 = pct(d['hpi_3yr_avg'])   # 50%: FHFA 3-yr avg annual appreciation (sustained trend)
    s2 = pct(d['hpi_latest'])    # 20%: FHFA latest annual HPI change (current momentum)
    s3 = pct(d['total_permits']) # 30%: Census BPS new units permitted (supply response)

    d['dim3'] = (s1*0.50 + s2*0.20 + s3*0.30) / 100 * 20
    return d


def score_dim4(df):
    """Quality of Place — 15 pts.
    Crime Rate 35% | Urban Access 40% | Amenity Density 25%

    Crime: FBI NIBRS 2024 violent offenses per 100k residents.
    Counties without NIBRS coverage receive their RUCC-tier median rate
    (rural agencies have lower NIBRS participation; tier imputation prevents
    penalizing rural counties for non-reporting rather than low crime).
    """
    d = df.copy()

    # Crime rate per 100k — lower is better
    d['violent_per100k'] = (
        d['violent_offenses'].fillna(0) /
        d['POPESTIMATE2023'].clip(lower=100) * 100_000
    )

    # Impute missing/zero counties with their RUCC-tier median to avoid
    # penalising non-reporters (many rural agencies don't participate in NIBRS).
    d['rucc_tier'] = pd.cut(
        d['rucc'].fillna(5),
        bins=[0, 3, 6, 9],
        labels=['metro', 'micro', 'rural']
    )
    tier_medians = (
        d[d['violent_offenses'] > 0]
        .groupby('rucc_tier')['violent_per100k']
        .median()
    )
    mask = d['violent_offenses'].isna() | (d['violent_offenses'] == 0)
    d.loc[mask, 'violent_per100k'] = d.loc[mask, 'rucc_tier'].map(tier_medians)
    d['violent_per100k'] = d['violent_per100k'].fillna(d['violent_per100k'].median())

    s1 = pct_inv(d['violent_per100k'])  # 35%: lower crime rate = better
    s2 = pct_inv(d['rucc'].fillna(5))   # 40%: USDA RUCC urban access
    d['est_per_1k'] = d['establishments'] / d['POPESTIMATE2023'].clip(lower=100) * 1000
    s3 = pct(d['est_per_1k'])            # 25%: Census CBP amenity density

    d['dim4'] = (s1*0.35 + s2*0.40 + s3*0.25) / 100 * 15
    return d


def score_dim5(df):
    """Physical Risk — 12 pts. Lower risk = higher score. (Physical Risk proxies for FEMA NRI.)"""
    d = df.copy()
    pop = d['POPESTIMATE2023'].clip(lower=100)

    # Flood risk: NFIP insurance payouts per capita over 10 years (40%)
    d['nfip_per_cap'] = d['nfip_claims'] / pop

    # Storm risk: NOAA property damage per capita over 5 years (35%)
    d['storm_per_cap'] = d['storm_damage'] / pop

    # Wildfire risk: USFS national rank (0=safe, 1=highest risk) (25%)
    d['wildfire_rank'] = d['wildfire_rank'].fillna(d['wildfire_rank'].median())

    s1 = pct_inv(d['nfip_per_cap'])    # 40%
    s2 = pct_inv(d['storm_per_cap'])   # 35%
    s3 = pct_inv(d['wildfire_rank'])   # 25%

    d['dim5'] = (s1*0.40 + s2*0.35 + s3*0.25) / 100 * 12
    return d


def score_dim6(df):
    """Population Momentum — 6 pts.
    Net Migration Rate 60% | Income Quality of In-Movers 40%
    """
    d = df.copy()
    s1 = pct(d['RNETMIG2023'])           # 60%: net migration rate per 1,000 (Census 2023)
    s2 = pct(d['inmover_income_ratio'])  # 40%: in-mover AGI ÷ out-mover AGI (IRS SOI) — ratio
                                         # > 1.0 means higher-income people arriving than leaving

    d['dim6'] = (s1*0.60 + s2*0.40) / 100 * 6
    return d


# ── Market Labels ──────────────────────────────────────────────────────────────

# Label thresholds calibrated to the actual score distribution (mean≈50, std≈6.2, range 27–70).
# Original thresholds (78/68/58/48/38/28/18/0) assumed a wider range than the percentile
# normalization produces. These recalibrated thresholds span the empirical range.
# Note: AVOID requires score < 26; empirical floor with FBI NIBRS is ~26.85, so AVOID
# currently has 0 counties. The 4 SPECULATIVE counties (<30) are the true worst performers.
LABELS = [
    (61, 'ACCELERATING'),   # top ~4%: ~100 counties; all signals aligned, prices still defensible
    (57, 'PEAKING'),        # strong momentum approaching affordability ceiling
    (51, 'ESTABLISHED'),    # healthy balanced market, sustainable fundamentals
    (45, 'EMERGING'),       # improving fundamentals, early-mover opportunity
    (37, 'FRONTIER'),       # below-average market, higher uncertainty
    (29, 'TURNING'),        # softening demand, watch for continued weakness
    (24, 'SPECULATIVE'),    # poor fundamentals, momentum-only pricing risk
    (0,  'AVOID'),          # systemic weakness across multiple dimensions
]


def classify(score):
    for threshold, label in LABELS:
        if score >= threshold:
            return label
    return 'AVOID'


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Civica Harvard Scoring Engine v1.3")
    print("=" * 60)

    print("\n[1/13]  Census Population...")
    pop  = load_population();  print(f"          {len(pop):,} counties")

    print("[2/13]  BEA Income...")
    bea  = load_bea();         print(f"          {len(bea):,} counties")

    print("[3/13]  ACS 5-yr Home Values (B25077)...")
    home_vals = load_home_values(); print(f"          {len(home_vals):,} counties")

    print("[4/13]  HUD Fair Market Rents...")
    fmr  = load_fmr();         print(f"          {len(fmr):,} FMR areas")

    print("[5/13]  FHFA HPI...")
    hpi  = load_hpi();         print(f"          {len(hpi):,} counties")

    print("[6/13]  BLS QCEW...")
    qcew = load_qcew();        print(f"          {len(qcew):,} counties")

    print("[7/13]  Census CBP...")
    cbp  = load_cbp();         print(f"          {len(cbp):,} counties")

    print("[8/13]  Census BPS Permits...")
    bps  = load_bps();         print(f"          {len(bps):,} counties")

    print("[9/13]  IRS Migration...")
    irs  = load_irs();         print(f"          {len(irs):,} counties")

    print("[10/13] FEMA NFIP Claims...")
    nfip = load_nfip();        print(f"          {len(nfip):,} counties")

    print("[11/13] NOAA Storm Events...")
    noaa = load_noaa_storm();  print(f"          {len(noaa):,} counties")

    print("[12/13] USFS Wildfire Risk...")
    usfs = load_usfs();        print(f"          {len(usfs):,} counties")

    print("[13/13] USDA Rural-Urban Codes...")
    rucc = load_rucc();        print(f"          {len(rucc):,} counties")

    print("[14/14] FBI NIBRS Crime (2024)...")
    nibrs = load_nibrs_crime(); print(f"          {len(nibrs):,} counties with crime data")

    # ── Merge ────────────────────────────────────────────────────────────────
    print("\nMerging all datasets on FIPS...")
    df = pop.copy()
    for ds in [bea, home_vals, fmr, hpi, qcew, cbp, bps, irs, nfip, noaa, usfs, rucc, nibrs]:
        df = df.merge(ds, on='fips', how='left')
    print(f"  Merged: {len(df):,} rows × {len(df.columns)} columns")

    # Require minimum population to score (very small counties have sparse data)
    df = df[df['POPESTIMATE2023'] >= 5_000].copy()
    print(f"  After pop ≥ 5,000 filter: {len(df):,} counties")

    # RUCC-tier imputation for missing ACS home values (must run before general fillna)
    missing_hv = df['median_home_value'].isna()
    if missing_hv.any():
        rucc_hv = (
            df[df['median_home_value'].notna()]
            .groupby('rucc')['median_home_value'].median()
        )
        df.loc[missing_hv, 'median_home_value'] = df.loc[missing_hv, 'rucc'].map(rucc_hv)
        df.loc[missing_hv, 'home_value_imputed'] = True
        print(f"  ACS home value imputed (RUCC-tier median): {missing_hv.sum():,} counties")

    # Fill remaining missing values with national medians so every county gets a score
    num_cols = df.select_dtypes(include=[np.number]).columns
    medians  = df[num_cols].median()
    df[num_cols] = df[num_cols].fillna(medians)

    # ── Score ────────────────────────────────────────────────────────────────
    print("\nScoring 6 dimensions...")
    df = score_dim1(df); print("  [1/6] Affordability & Value       ✓")
    df = score_dim2(df); print("  [2/6] Economic Vitality            ✓")
    df = score_dim3(df); print("  [3/6] Housing Market Dynamics      ✓")
    df = score_dim4(df); print("  [4/6] Quality of Place             ✓")
    df = score_dim5(df); print("  [5/6] Physical Risk                ✓")
    df = score_dim6(df); print("  [6/6] Population Momentum          ✓")

    df['total_score']   = (df[['dim1','dim2','dim3','dim4','dim5','dim6']]
                           .sum(axis=1).clip(0, 100))
    df['market_label']  = df['total_score'].apply(classify)
    df['national_rank'] = df['total_score'].rank(ascending=False, method='min').astype(int)

    # ── Output ───────────────────────────────────────────────────────────────
    out_cols = [
        'fips', 'POPESTIMATE2023',
        'total_score', 'market_label', 'national_rank',
        'dim1', 'dim2', 'dim3', 'dim4', 'dim5', 'dim6',
        # Raw metrics for county report cards
        'median_home_value', 'home_value_imputed', 'fmr_2br', 'pr_ratio', 'price_income',
        'breakeven_yrs', 'hpi_3yr_avg', 'hpi_latest',
        'per_capita_income', 'income_4yr_growth',
        'private_employment', 'avg_annual_wage', 'sector_quality', 'hhi',
        'total_permits', 'inmover_income_ratio',
        'nfip_per_cap', 'storm_per_cap', 'wildfire_rank',
        'RNETMIG2023', 'RDOMESTICMIG2023', 'rucc',
        'est_per_1k', 'in_hh', 'out_hh',
        'violent_offenses', 'violent_per100k',
    ]
    available = [c for c in out_cols if c in df.columns]
    out = df[available].round(4)
    out['fips'] = out['fips'].astype(str).str.zfill(5)  # preserve leading zeros
    out.to_csv(OUT, index=False)

    print(f"\n{'='*60}")
    print(f"Output → {OUT}")
    print(f"Counties scored: {len(out):,}")

    print(f"\nScore distribution:")
    print(out['total_score'].describe().round(2).to_string())

    print(f"\nMarket label counts:")
    print(out['market_label'].value_counts().sort_index().to_string())

    print(f"\nTop 25 counties:")
    top25 = df.nlargest(25, 'total_score')[
        ['fips', 'total_score', 'market_label', 'median_home_value', 'avg_annual_wage']
    ].round(2)
    print(top25.to_string(index=False))

    print(f"\nBottom 10 counties:")
    bot10 = df.nsmallest(10, 'total_score')[
        ['fips', 'total_score', 'market_label', 'median_home_value', 'per_capita_income']
    ].round(2)
    print(bot10.to_string(index=False))


if __name__ == '__main__':
    main()
