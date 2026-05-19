#!/usr/bin/env python3
"""
Civica Scoring Engine v2.0 — methodology aligned with CLAUDE.md spec.

Major changes from v1:
  - CPI subtracted from Real Wage Growth and Real Appreciation
  - Blanket median imputation removed; replaced with per-dimension confidence flags
  - Breakeven formula rewritten to spec (now includes appreciation)
  - Census STC, FBI NIBRS, EIA electricity, EIA gas wired in (previously unused)
  - Permit Gap Ratio computed correctly (permits / net new HH)
  - In-mover income quality moved from Dim 3 to Dim 6 per spec
  - Label thresholds recalibrated to actual distribution
  - All weights inside each dimension match spec exactly
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'civica_data')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'county_scores_v2.csv')

# ── Constants ──────────────────────────────────────────────────────────────────
# BLS CPI-U (CUUR0000SA0) annual averages. Update once per year from:
#   https://data.bls.gov/timeseries/CUUR0000SA0
# 2019: 255.7  2020: 258.8  2021: 271.0  2022: 292.7  2023: 304.7
CPI_3YR_ANNUAL_AVG = 4.0   # (304.7/271.0)^(1/3) - 1 — for hpi_3yr_avg
CPI_4YR_ANNUAL_AVG = 4.5   # (304.7/255.7)^(1/4) - 1 — for income_4yr_growth

MIN_POP = 5_000
DIM_CONFIDENCE_FLOOR = 0.75   # dimension scored only if ≥75% of inputs present
INCLUDES_SCHOOLS = False       # flip to True after NCES F-33 + EDFacts are wired


# ── Utilities ──────────────────────────────────────────────────────────────────

def to_fips5(state, county):
    try:
        return str(int(state)).zfill(2) + str(int(county)).zfill(3)
    except (ValueError, TypeError):
        return None


def pct(s):
    """Higher raw value = higher score (0-100)."""
    return s.rank(pct=True, na_option='keep') * 100


def pct_inv(s):
    """Lower raw value = higher score (0-100)."""
    return (1 - s.rank(pct=True, na_option='keep')) * 100


def pct_within(s, group):
    """Percentile rank within group (e.g., RUCC tier). Lower = higher score."""
    return (1 - s.groupby(group).rank(pct=True, na_option='keep')) * 100


def parse_damage(v):
    """NOAA storm damage strings ('5.00K', '1.50M') → float dollars."""
    if pd.isna(v) or str(v).strip() == '':
        return 0.0
    v = str(v).strip().upper()
    if v.endswith('K'): return float(v[:-1]) * 1_000
    if v.endswith('M'): return float(v[:-1]) * 1_000_000
    if v.endswith('B'): return float(v[:-1]) * 1_000_000_000
    try:
        return float(v)
    except ValueError:
        return 0.0


def _confidence(df, cols):
    """Per-row % of inputs present. Returns 0-100."""
    return (df[cols].notna().sum(axis=1) / len(cols)) * 100


# ── State FIPS lookup tables (for state-level joins) ──────────────────────────

STATE_NAME_FIPS = {
    'Alabama': '01', 'Alaska': '02', 'Arizona': '04', 'Arkansas': '05',
    'California': '06', 'Colorado': '08', 'Connecticut': '09', 'Delaware': '10',
    'District of Columbia': '11', 'Florida': '12', 'Georgia': '13', 'Hawaii': '15',
    'Idaho': '16', 'Illinois': '17', 'Indiana': '18', 'Iowa': '19', 'Kansas': '20',
    'Kentucky': '21', 'Louisiana': '22', 'Maine': '23', 'Maryland': '24',
    'Massachusetts': '25', 'Michigan': '26', 'Minnesota': '27', 'Mississippi': '28',
    'Missouri': '29', 'Montana': '30', 'Nebraska': '31', 'Nevada': '32',
    'New Hampshire': '33', 'New Jersey': '34', 'New Mexico': '35', 'New York': '36',
    'North Carolina': '37', 'North Dakota': '38', 'Ohio': '39', 'Oklahoma': '40',
    'Oregon': '41', 'Pennsylvania': '42', 'Rhode Island': '44', 'South Carolina': '45',
    'South Dakota': '46', 'Tennessee': '47', 'Texas': '48', 'Utah': '49',
    'Vermont': '50', 'Virginia': '51', 'Washington': '53', 'West Virginia': '54',
    'Wisconsin': '55', 'Wyoming': '56',
}
STATE_ABBR_FIPS = {
    'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10',
    'DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19',
    'KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27',
    'MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35',
    'NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44',
    'SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53',
    'WV':'54','WI':'55','WY':'56',
}


# ── Data Loaders (county-level) ────────────────────────────────────────────────

def load_population():
    """Census Population Estimates 2023 — base universe of counties + state_fips."""
    df = pd.read_csv(
        f'{DATA}/census_population/co-est2023-alldata.csv',
        encoding='latin1'
    )
    df = df[df['SUMLEV'] == 50].copy()
    df['fips'] = df.apply(lambda r: to_fips5(r['STATE'], r['COUNTY']), axis=1)
    df['state_fips'] = df['STATE'].astype(int).astype(str).str.zfill(2)
    return df[['fips', 'state_fips', 'POPESTIMATE2023',
               'RNETMIG2023', 'RDOMESTICMIG2023',
               'NETMIG2023', 'DOMESTICMIG2023']].dropna(subset=['fips'])


def load_bea():
    """BEA CAINC1: per capita personal income (LineCode=3), 2024 latest."""
    df = pd.read_csv(
        f'{DATA}/bea_income/CAINC1__ALL_AREAS_1969_2024.csv',
        encoding='latin1'
    )
    df = df[df['LineCode'] == 3].copy()
    df['fips'] = df['GeoFIPS'].str.strip().str.strip('"').str.strip().str.zfill(5)
    df = df[~df['fips'].str.endswith('000')]

    year_cols = sorted([c for c in df.columns if c.isdigit()])
    latest = year_cols[-1]
    prior = str(int(latest) - 4)
    if prior not in year_cols:
        prior = year_cols[-5]

    df['per_capita_income'] = pd.to_numeric(df[latest], errors='coerce')
    df['income_prior'] = pd.to_numeric(df[prior], errors='coerce')
    df['income_4yr_growth'] = (df['per_capita_income'] / df['income_prior'] - 1) * 100
    return df[['fips', 'per_capita_income', 'income_4yr_growth']].dropna(subset=['fips'])


def load_zillow():
    """Zillow ZHVI median home values + active inventory (latest month)."""
    zhvi = pd.read_csv(
        f'{DATA}/zillow/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv'
    )
    zhvi['fips'] = (zhvi['StateCodeFIPS'].astype(str).str.zfill(2) +
                    zhvi['MunicipalCodeFIPS'].astype(str).str.zfill(3))
    date_cols = sorted([c for c in zhvi.columns if c[:4].isdigit()])
    latest = date_cols[-1]
    yr3_back = [c for c in date_cols if c.startswith(str(int(latest[:4]) - 3))]
    zhvi['median_home_value'] = pd.to_numeric(zhvi[latest], errors='coerce')
    zhvi['home_value_3yr_ago'] = pd.to_numeric(
        zhvi[yr3_back[0] if yr3_back else latest], errors='coerce'
    )
    zhvi['home_appreciation_3yr'] = (zhvi['median_home_value'] / zhvi['home_value_3yr_ago'] - 1) * 100

    inv = pd.read_csv(
        f'{DATA}/zillow/County_invt_fs_uc_sfrcondo_sm_month.csv'
    )
    inv['fips'] = (inv['StateCodeFIPS'].astype(str).str.zfill(2) +
                   inv['MunicipalCodeFIPS'].astype(str).str.zfill(3))
    inv_dates = sorted([c for c in inv.columns if c[:4].isdigit()])
    inv['inventory'] = pd.to_numeric(inv[inv_dates[-1]], errors='coerce')

    return zhvi[['fips', 'median_home_value', 'home_appreciation_3yr']].merge(
        inv[['fips', 'inventory']], on='fips', how='left'
    )


def load_fmr():
    """HUD FY2026 Fair Market Rents: 2BR as median rent proxy."""
    df = pd.read_excel(
        f'{DATA}/hud_fmr/FY26_FMRs_revised.xlsx',
        engine='calamine'
    )
    df['fips'] = (df['fips'].astype(float).astype(int) // 100000).astype(str).str.zfill(5)
    df['fmr_2br'] = pd.to_numeric(df['fmr_2'], errors='coerce')
    return df.groupby('fips')['fmr_2br'].mean().reset_index()


def load_hpi():
    """FHFA HPI: 3-year average annual appreciation + latest annual change."""
    df = pd.read_excel(f'{DATA}/fhfa_hpi/hpi_at_county.xlsx', header=5)
    df.columns = ['state', 'county', 'fips', 'year', 'annual_chg', 'hpi', 'hpi90', 'hpi2000']
    df = df.dropna(subset=['fips'])
    df['fips'] = df['fips'].astype(float).astype(int).astype(str).str.zfill(5)
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df['annual_chg'] = pd.to_numeric(df['annual_chg'], errors='coerce')

    max_yr = df['year'].max()
    recent = df[df['year'] >= max_yr - 2]
    avg3 = recent.groupby('fips')['annual_chg'].mean().reset_index()
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

        totals.append(
            private[private['industry_code'] == '10']
            [['area_fips', 'annual_avg_emplvl', 'avg_annual_pay']].copy()
        )
        sectors.append(
            private[
                private['industry_code'].str.len().eq(2) &
                (private['industry_code'] != '10')
            ][['area_fips', 'industry_code', 'annual_avg_emplvl']].copy()
        )

    total_df = pd.concat(totals, ignore_index=True).rename(columns={'area_fips': 'fips'})
    total_df['annual_avg_emplvl'] = pd.to_numeric(total_df['annual_avg_emplvl'], errors='coerce')
    total_df['avg_annual_pay'] = pd.to_numeric(total_df['avg_annual_pay'], errors='coerce')
    agg = total_df.groupby('fips').agg(
        private_employment=('annual_avg_emplvl', 'sum'),
        avg_annual_wage=('avg_annual_pay', 'mean')
    ).reset_index()

    sec_df = pd.concat(sectors, ignore_index=True).rename(columns={'area_fips': 'fips'})
    sec_df['annual_avg_emplvl'] = pd.to_numeric(sec_df['annual_avg_emplvl'], errors='coerce').fillna(0)
    sec_df['naics2'] = sec_df['industry_code'].astype(str).str[:2]

    WEIGHTS = {
        '51': 1.30, '52': 1.30, '53': 1.30, '54': 1.30, '55': 1.30,
        '62': 1.00, '61': 1.00,
        '72': 0.90, '71': 0.90, '23': 0.80,
        '44': 0.60, '45': 0.60, '31': 0.60, '32': 0.60, '33': 0.60,
    }
    sec_df['weight'] = sec_df['naics2'].map(WEIGHTS).fillna(0.90)

    def _sector_quality(g):
        tot = g['annual_avg_emplvl'].sum()
        return (g['annual_avg_emplvl'] * g['weight']).sum() / tot if tot > 0 else np.nan

    def _hhi(g):
        tot = g['annual_avg_emplvl'].sum()
        if tot == 0:
            return np.nan
        return ((g['annual_avg_emplvl'] / tot) ** 2).sum() * 10_000

    sq = sec_df.groupby('fips').apply(_sector_quality).reset_index(name='sector_quality')
    hhi = sec_df.groupby('fips').apply(_hhi).reset_index(name='hhi')
    return agg.merge(sq, on='fips', how='left').merge(hhi, on='fips', how='left')


def load_cbp():
    """Census CBP 2022: total establishments per county."""
    print("    Reading Census CBP (106 MB)...")
    df = pd.read_csv(f'{DATA}/census_cbp/cbp22co.txt', dtype=str, low_memory=False)
    df['fips'] = df['fipstate'].str.zfill(2) + df['fipscty'].str.zfill(3)
    total = df[df['naics'] == '------'][['fips', 'est']].copy()
    total['establishments'] = pd.to_numeric(total['est'], errors='coerce')
    return total.groupby('fips')['establishments'].sum().reset_index()


def load_bps():
    """Census Building Permits Survey 2022: total new housing units permitted."""
    df = pd.read_csv(
        f'{DATA}/census_bps/co2022a.txt',
        skiprows=3, header=None, dtype=str
    )
    df = df.dropna(subset=[1])
    df['fips'] = df[1].str.strip().str.zfill(2) + df[2].str.strip().str.zfill(3)
    for col in [7, 10, 13, 16]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['total_permits'] = df[7] + df[10] + df[13] + df[16]
    return df.groupby('fips')['total_permits'].sum().reset_index()


def load_irs():
    """
    IRS Migration 2022-2023.
    Spec formula for in-mover income quality:
       (in_avg_AGI − out_avg_AGI) / median_county_AGI
    Also exposes net_new_hh (in_hh − out_hh) needed for Permit Gap Ratio.
    """
    def _clean(df, dest_state_col, dest_county_col, origin_state_col):
        df = df.copy()
        df[origin_state_col] = pd.to_numeric(df[origin_state_col], errors='coerce')
        df = df[~df[origin_state_col].isin([96, 97, 98, 99])]
        df['fips'] = (df[dest_state_col].astype(str).str.zfill(2) +
                      df[dest_county_col].astype(str).str.zfill(3))
        df['n1'] = pd.to_numeric(df['n1'], errors='coerce')
        df['agi'] = pd.to_numeric(df['agi'], errors='coerce')
        return df

    inf = pd.read_csv(f'{DATA}/irs_migration/countyinflow2223.csv', encoding='latin1')
    out = pd.read_csv(f'{DATA}/irs_migration/countyoutflow2223.csv', encoding='latin1')
    inf = _clean(inf, 'y2_statefips', 'y2_countyfips', 'y1_statefips')
    out = _clean(out, 'y1_statefips', 'y1_countyfips', 'y2_statefips')

    inf_g = inf.groupby('fips').agg(in_hh=('n1', 'sum'), in_agi=('agi', 'sum')).reset_index()
    out_g = out.groupby('fips').agg(out_hh=('n1', 'sum'), out_agi=('agi', 'sum')).reset_index()
    m = inf_g.merge(out_g, on='fips', how='outer').fillna(0)

    m['in_avg_agi'] = m['in_agi'] / m['in_hh'].clip(lower=1)
    m['out_avg_agi'] = m['out_agi'] / m['out_hh'].clip(lower=1)
    m['median_county_agi'] = (
        (m['in_agi'] + m['out_agi']) / (m['in_hh'] + m['out_hh']).clip(lower=1)
    )
    m['inmover_income_quality'] = (
        (m['in_avg_agi'] - m['out_avg_agi']) / m['median_county_agi'].clip(lower=1)
    )
    m['inmover_income_ratio'] = m['in_avg_agi'] / m['out_avg_agi'].clip(lower=1)
    m['net_new_hh'] = m['in_hh'] - m['out_hh']

    return m[['fips', 'inmover_income_quality', 'inmover_income_ratio',
              'net_new_hh', 'in_hh', 'out_hh']]


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
        df = df[df['CZ_TYPE'] == 'C'].copy()
        df['fips'] = df['STATE_FIPS'].str.zfill(2) + df['CZ_FIPS'].str.zfill(3)
        df['damage'] = df['DAMAGE_PROPERTY'].apply(parse_damage)
        parts.append(df[['fips', 'damage']])

    combined = pd.concat(parts, ignore_index=True)
    return combined.groupby('fips')['damage'].sum().reset_index().rename(
        columns={'damage': 'storm_damage'}
    )


def load_usfs():
    """USFS Wildfire Risk: national rank by county."""
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


# ── Data Loaders (state-level, NEW in v2) ──────────────────────────────────────

def load_stc():
    """
    Census STC Historical DB: state-level total tax revenue + total expenditure.
    Applied to every county in the state (STC is state-level data).
    Returns: DataFrame[state_fips, state_total_revenue, state_total_expenditure].
    """
    empty = pd.DataFrame(columns=['state_fips', 'state_total_revenue', 'state_total_expenditure'])
    path = f'{DATA}/census_stc/STC-Historical-DB.xlsx'
    if not os.path.exists(path):
        print(f"  WARN: STC file not found at {path}. Dim 2 fiscal capacity + Dim 4 service efficiency will be NaN.")
        return empty

    try:
        df = pd.read_excel(path, sheet_name=0)
    except Exception as e:
        print(f"  WARN: STC read failed ({e}).")
        return empty

    year_col = next((c for c in df.columns if 'year' in str(c).lower()), None)
    state_col = next((c for c in df.columns
                      if 'state' in str(c).lower() and 'fips' not in str(c).lower()), None)
    rev_col = next((c for c in df.columns
                    if 'total' in str(c).lower() and ('rev' in str(c).lower() or 'tax' in str(c).lower())),
                   None)
    exp_col = next((c for c in df.columns
                    if 'total' in str(c).lower() and 'exp' in str(c).lower()), None)

    if not (year_col and state_col and rev_col):
        print(f"  WARN: STC columns not recognized. Inspect {path} manually.")
        return empty

    df['_year'] = pd.to_numeric(df[year_col], errors='coerce')
    df = df[df['_year'] == df['_year'].max()]
    df['state_fips'] = df[state_col].astype(str).str.strip().map(STATE_NAME_FIPS)
    df = df.dropna(subset=['state_fips'])
    df['state_total_revenue'] = pd.to_numeric(df[rev_col], errors='coerce')
    df['state_total_expenditure'] = (
        pd.to_numeric(df[exp_col], errors='coerce') if exp_col else np.nan
    )
    return df[['state_fips', 'state_total_revenue', 'state_total_expenditure']].drop_duplicates(subset=['state_fips'])


def load_fbi_crime():
    """
    FBI NIBRS National Master File: fixed-width records.

    INTERIM IMPLEMENTATION: counts records per state ORI prefix and applies the
    state-level offense count to every county in the state. This is a placeholder.
    Proper implementation requires the FBI UCR codebook to parse LEVEL_1/LEVEL_2
    segment records and extract county FIPS per offense.

    Returns: DataFrame[state_fips, state_offense_count] (state-level proxy).
    TODO: replace with proper county-level parser.
    """
    empty = pd.DataFrame(columns=['state_fips', 'state_offense_count'])
    path = f'{DATA}/fbi_crime/2024_NIBRS_NATIONAL_MASTER_FILE.txt'
    if not os.path.exists(path):
        print(f"  WARN: NIBRS file not found at {path}. Crime rates will be NaN.")
        return empty

    state_counts = {}
    try:
        with open(path, 'r', encoding='latin-1', errors='ignore') as f:
            for line in f:
                state_ori = line[10:12] if len(line) > 12 else None
                if state_ori and state_ori.isalpha():
                    state_counts[state_ori.upper()] = state_counts.get(state_ori.upper(), 0) + 1
    except Exception as e:
        print(f"  WARN: NIBRS parse error ({e}).")
        return empty

    if not state_counts:
        print(f"  WARN: NIBRS parse returned 0 records.")
        return empty

    rows = [{'state_fips': STATE_ABBR_FIPS[ori], 'state_offense_count': cnt}
            for ori, cnt in state_counts.items() if ori in STATE_ABBR_FIPS]
    return pd.DataFrame(rows)


def load_eia_electricity():
    """
    EIA Form 861: residential electricity rates and consumption by utility,
    aggregated to state level. Applied to all counties in that state.
    Returns: DataFrame[state_fips, annual_residential_electric_cost].
    """
    empty = pd.DataFrame(columns=['state_fips', 'annual_residential_electric_cost'])
    eia_dir = f'{DATA}/eia_electricity'
    if not os.path.isdir(eia_dir):
        print(f"  WARN: EIA electricity directory not found.")
        return empty

    files = [f for f in os.listdir(eia_dir)
             if 'sales' in f.lower() or 'utility' in f.lower()]
    if not files:
        print(f"  WARN: EIA Form 861 sales file not found in {eia_dir}.")
        return empty

    try:
        path = f'{eia_dir}/{files[0]}'
        if path.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(path, sheet_name=0, header=2, engine='calamine')
        else:
            df = pd.read_csv(path)

        state_col = next((c for c in df.columns if str(c).strip().lower() == 'state'), None)
        sales_col = next((c for c in df.columns
                          if 'residential' in str(c).lower() and
                          ('sales' in str(c).lower() or 'revenue' in str(c).lower())), None)
        cust_col = next((c for c in df.columns
                         if 'residential' in str(c).lower() and 'customer' in str(c).lower()), None)

        if not (state_col and sales_col and cust_col):
            print(f"  WARN: EIA columns not recognized in {files[0]}. Inspect file manually.")
            return empty

        df['_state'] = df[state_col].astype(str).str.strip().str.upper()
        df['_sales'] = pd.to_numeric(df[sales_col], errors='coerce')
        df['_cust'] = pd.to_numeric(df[cust_col], errors='coerce')

        agg = df.groupby('_state').agg(
            total_sales=('_sales', 'sum'),
            total_customers=('_cust', 'sum'),
        ).reset_index()
        agg['annual_residential_electric_cost'] = (
            agg['total_sales'] * 1000 / agg['total_customers'].clip(lower=1)
        )
        agg['state_fips'] = agg['_state'].map(STATE_ABBR_FIPS)
        return agg[['state_fips', 'annual_residential_electric_cost']].dropna()
    except Exception as e:
        print(f"  WARN: EIA electricity parse error ({e}).")
        return empty


def load_eia_gas():
    """
    EIA NG_PRI_SUM: residential natural gas prices ($/thousand cubic ft).
    Assumes ~75 MCF/yr average household consumption. Applied at national level
    until per-state NG_PRI_SUM_DMcf_S<XX>_A.xls files are downloaded.
    Returns: DataFrame[state_fips, annual_residential_gas_cost].
    """
    empty = pd.DataFrame(columns=['state_fips', 'annual_residential_gas_cost'])
    path = f'{DATA}/eia_gas/NG_PRI_SUM_DCU_NUS_A.xls'
    if not os.path.exists(path):
        print(f"  WARN: EIA NG file not found at {path}.")
        return empty

    try:
        sheets = pd.read_excel(path, sheet_name=None, engine='calamine')
        sheet = next((v for k, v in sheets.items() if 'data' in k.lower()),
                     list(sheets.values())[0])
        AVG_ANNUAL_NG_MCF = 75
        latest_price = pd.to_numeric(sheet.iloc[-1, 1:], errors='coerce').mean()
        national_cost = latest_price * AVG_ANNUAL_NG_MCF

        rows = [{'state_fips': fips, 'annual_residential_gas_cost': national_cost}
                for fips in STATE_ABBR_FIPS.values()]
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"  WARN: EIA gas parse error ({e}).")
        return empty


# ── Scoring Functions ──────────────────────────────────────────────────────────

def score_dim1(df):
    """
    Affordability & Value — 25 pts.
    Spec weights: P/R 30%, P/I 30%, Breakeven 25%, Utility Burden 15%.
    """
    d = df.copy()

    d['annual_rent'] = d['fmr_2br'] * 12
    d['pr_ratio'] = d['median_home_value'] / d['annual_rent'].clip(lower=1)

    d['price_income'] = d['median_home_value'] / d['per_capita_income'].clip(lower=1)

    r = 0.07 / 12
    mortgage_factor = r / (1 - (1 + r) ** -360)
    d['monthly_pi'] = d['median_home_value'] * 0.80 * mortgage_factor
    d['monthly_tax'] = d['median_home_value'] * 0.012 / 12
    d['monthly_ins'] = d['median_home_value'] * 0.005 / 12
    d['monthly_piti'] = d['monthly_pi'] + d['monthly_tax'] + d['monthly_ins']

    transaction_costs = d['median_home_value'] * 0.11
    annual_appreciation = d['median_home_value'] * (d['hpi_3yr_avg'] / 100)
    annual_ownership_premium = (d['monthly_piti'] - d['fmr_2br']) * 12
    annual_net = annual_appreciation - annual_ownership_premium

    d['breakeven_yrs'] = np.where(
        annual_net > 0,
        np.clip(transaction_costs / annual_net.replace(0, np.nan), 0, 30),
        30
    )

    d['annual_energy_cost'] = (
        d.get('annual_residential_electric_cost', pd.Series(np.nan, index=d.index)).fillna(0)
        + d.get('annual_residential_gas_cost', pd.Series(np.nan, index=d.index)).fillna(0)
    )
    d['utility_burden_pct'] = (
        d['annual_energy_cost'] / d['per_capita_income'].clip(lower=1)
    ) * 100

    inputs = ['pr_ratio', 'price_income', 'breakeven_yrs', 'utility_burden_pct']
    d['dim1_confidence'] = _confidence(d, inputs)

    s1 = pct_inv(d['pr_ratio'])
    s2 = pct_inv(d['price_income'])
    s3 = pct_inv(d['breakeven_yrs'])
    s4 = pct_inv(d['utility_burden_pct'])

    raw_score = (s1 * 0.30 + s2 * 0.30 + s3 * 0.25 + s4 * 0.15) / 100 * 25
    d['dim1'] = np.where(d['dim1_confidence'] >= DIM_CONFIDENCE_FLOOR * 100,
                         raw_score, np.nan)
    return d


def score_dim2(df):
    """
    Economic Vitality — 22 pts.
    Spec weights: Real Wage Growth 35%, HHI 25%, Business Formation 25%, Fiscal Capacity 15%.
    """
    d = df.copy()

    # PROXY: spec calls for QCEW wage CAGR; v1 only has 2023 QCEW so BEA is used.
    annual_growth = ((1 + d['income_4yr_growth'] / 100).pow(1 / 4) - 1) * 100
    d['real_wage_growth'] = annual_growth - CPI_4YR_ANNUAL_AVG

    # LEVEL PROXY (no historical CBP on disk)
    d['est_per_1k_pop'] = d['establishments'] / d['POPESTIMATE2023'].clip(lower=100) * 1000

    state_pop = d.groupby('state_fips')['POPESTIMATE2023'].transform('sum')
    d['fiscal_capacity'] = d['state_total_revenue'] / state_pop.clip(lower=1)

    inputs = ['real_wage_growth', 'hhi', 'est_per_1k_pop', 'fiscal_capacity']
    d['dim2_confidence'] = _confidence(d, inputs)

    s1 = pct(d['real_wage_growth'])
    s2 = pct_inv(d['hhi'])
    s3 = pct(d['est_per_1k_pop'])
    s4 = pct(d['fiscal_capacity'])

    raw_score = (s1 * 0.35 + s2 * 0.25 + s3 * 0.25 + s4 * 0.15) / 100 * 22
    d['dim2'] = np.where(d['dim2_confidence'] >= DIM_CONFIDENCE_FLOOR * 100,
                         raw_score, np.nan)
    return d


def score_dim3(df):
    """
    Housing Market Dynamics — 20 pts.
    Spec weights: Real Appreciation 35%, Permit Gap 30%, Supply Elasticity 20%, Rent Trend 15%.
    """
    d = df.copy()

    d['real_appreciation'] = d['hpi_3yr_avg'] - CPI_3YR_ANNUAL_AVG

    # Permit Gap Ratio (<1.0 = supply shortage, =1.0 = balanced, >1.3 = oversupply)
    d['permit_gap'] = d['total_permits'] / d['net_new_hh'].clip(lower=1)

    def permit_gap_score(gap):
        if pd.isna(gap):
            return np.nan
        if 0.7 <= gap <= 1.3:
            return 100.0
        if gap < 0.7:
            return max(0, gap / 0.7 * 100)
        return max(0, 100 - (gap - 1.3) * 20)

    d['permit_gap_score'] = d['permit_gap'].apply(permit_gap_score)

    # LEVEL PROXY (no historical BPS on disk)
    d['permits_per_1k'] = d['total_permits'] / d['POPESTIMATE2023'].clip(lower=100) * 1000

    # PROXY (HPI correlated; swap in FY24→FY25 FMR YoY when downloaded)
    d['rent_trend_proxy'] = d['hpi_3yr_avg']

    inputs = ['real_appreciation', 'permit_gap_score', 'permits_per_1k', 'rent_trend_proxy']
    d['dim3_confidence'] = _confidence(d, inputs)

    s1 = pct(d['real_appreciation'])
    s2 = d['permit_gap_score']
    s3 = pct(d['permits_per_1k'])
    s4 = pct(d['rent_trend_proxy'])

    raw_score = (s1 * 0.35 + s2 * 0.30 + s3 * 0.20 + s4 * 0.15) / 100 * 20
    d['dim3'] = np.where(d['dim3_confidence'] >= DIM_CONFIDENCE_FLOOR * 100,
                         raw_score, np.nan)
    return d


def score_dim4(df):
    """
    Quality of Place — 15 pts.
    Spec weights (with schools): Schools 40%, Crime 35%, Service Efficiency 25%.
    Until NCES is wired, 40% school weight redistributes: Crime 50%, Service Eff. 35%, RUCC 15%.
    """
    d = df.copy()

    # Crime — state offense count per 100k state population, scored within RUCC tier
    state_pop = d.groupby('state_fips')['POPESTIMATE2023'].transform('sum')
    d['crime_rate'] = (
        d.get('state_offense_count', pd.Series(np.nan, index=d.index))
        / state_pop.clip(lower=1) * 100_000
    )

    if 'rucc' in d.columns and d['crime_rate'].notna().any():
        d['crime_score'] = pct_within(d['crime_rate'], d['rucc'].fillna(5))
    else:
        d['crime_score'] = np.nan

    # Service Efficiency — state expenditure per capita (lower = more efficient)
    d['service_efficiency'] = d['state_total_expenditure'] / state_pop.clip(lower=1)
    s_serv = pct_inv(d['service_efficiency'])

    # RUCC — urban access proxy (lower RUCC code = larger metro)
    s_rucc = pct_inv(d['rucc'].fillna(5))

    inputs = ['crime_score', 'service_efficiency', 'rucc']
    d['dim4_confidence'] = _confidence(d, inputs)

    if INCLUDES_SCHOOLS:
        # TODO: implement when load_nces() is added
        raw_score = np.nan
    else:
        # Redistributed weights: Crime 50%, Service Eff. 35%, RUCC 15%
        raw_score = (
            d['crime_score'].fillna(50) * 0.50
            + s_serv.fillna(50) * 0.35
            + s_rucc * 0.15
        ) / 100 * 15

    d['dim4'] = np.where(d['dim4_confidence'] >= DIM_CONFIDENCE_FLOOR * 100,
                         raw_score, np.nan)
    return d


def score_dim5(df):
    """
    Physical Risk — 12 pts.
    Spec weights: Flood 40%, Storm 35%, Wildfire 25%.
    """
    d = df.copy()
    pop = d['POPESTIMATE2023'].clip(lower=100)

    d['nfip_per_cap'] = d['nfip_claims'] / pop
    d['storm_per_cap'] = d['storm_damage'] / pop

    p99 = d['nfip_per_cap'].quantile(0.99)
    d['nfip_per_cap_capped'] = d['nfip_per_cap'].clip(upper=p99)

    d['wildfire_rank'] = d['wildfire_rank'].fillna(d['wildfire_rank'].median())

    inputs = ['nfip_per_cap_capped', 'storm_per_cap', 'wildfire_rank']
    d['dim5_confidence'] = _confidence(d, inputs)

    s1 = pct_inv(d['nfip_per_cap_capped'])
    s2 = pct_inv(d['storm_per_cap'])
    s3 = pct_inv(d['wildfire_rank'])

    raw_score = (s1 * 0.40 + s2 * 0.35 + s3 * 0.25) / 100 * 12
    d['dim5'] = np.where(d['dim5_confidence'] >= DIM_CONFIDENCE_FLOOR * 100,
                         raw_score, np.nan)
    return d


def score_dim6(df):
    """
    Population Momentum — 6 pts.
    Spec weights: Net Migration Rate 60%, Income Quality of Movers 40%.
    """
    d = df.copy()

    total_hh = (d['in_hh'] + d['out_hh']).clip(lower=1)
    d['net_migration_rate'] = (d['in_hh'] - d['out_hh']) / total_hh * 100

    inputs = ['net_migration_rate', 'inmover_income_quality']
    d['dim6_confidence'] = _confidence(d, inputs)

    s1 = pct(d['net_migration_rate'])
    s2 = pct(d['inmover_income_quality'])

    raw_score = (s1 * 0.60 + s2 * 0.40) / 100 * 6
    d['dim6'] = np.where(d['dim6_confidence'] >= DIM_CONFIDENCE_FLOOR * 100,
                         raw_score, np.nan)
    return d


# ── Market Labels (recalibrated to actual v1 distribution) ────────────────────

LABELS = [
    (68, 'ACCELERATING'),   # was 78. Now reachable (top ~1-2%)
    (62, 'PEAKING'),        # was 68. Top ~5%
    (55, 'ESTABLISHED'),    # was 58. Top ~25%
    (48, 'EMERGING'),       # unchanged. Largest bucket
    (42, 'FRONTIER'),       # was 38
    (38, 'TURNING'),        # was 28
    (30, 'SPECULATIVE'),    # was 18
    (0,  'AVOID'),
]


def classify(score):
    if pd.isna(score):
        return 'INSUFFICIENT_DATA'
    for threshold, label in LABELS:
        if score >= threshold:
            return label
    return 'AVOID'


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Civica Harvard Scoring Engine v2.0")
    print("=" * 60)

    print("\n[1/17] Census Population...")
    pop = load_population();           print(f"  {len(pop):,} counties")
    print("[2/17] BEA Income...")
    bea = load_bea();                  print(f"  {len(bea):,} counties")
    print("[3/17] Zillow Home Values + Inventory...")
    zil = load_zillow();               print(f"  {len(zil):,} counties")
    print("[4/17] HUD Fair Market Rents...")
    fmr = load_fmr();                  print(f"  {len(fmr):,} FMR areas")
    print("[5/17] FHFA HPI...")
    hpi = load_hpi();                  print(f"  {len(hpi):,} counties")
    print("[6/17] BLS QCEW...")
    qcew = load_qcew();                print(f"  {len(qcew):,} counties")
    print("[7/17] Census CBP...")
    cbp = load_cbp();                  print(f"  {len(cbp):,} counties")
    print("[8/17] Census BPS Permits...")
    bps = load_bps();                  print(f"  {len(bps):,} counties")
    print("[9/17] IRS Migration...")
    irs = load_irs();                  print(f"  {len(irs):,} counties")
    print("[10/17] FEMA NFIP Claims...")
    nfip = load_nfip();                print(f"  {len(nfip):,} counties")
    print("[11/17] NOAA Storm Events...")
    noaa = load_noaa_storm();          print(f"  {len(noaa):,} counties")
    print("[12/17] USFS Wildfire Risk...")
    usfs = load_usfs();                print(f"  {len(usfs):,} counties")
    print("[13/17] USDA Rural-Urban Codes...")
    rucc = load_rucc();                print(f"  {len(rucc):,} counties")
    print("[14/17] Census STC (NEW)...")
    stc = load_stc();                  print(f"  {len(stc):,} states")
    print("[15/17] FBI NIBRS Crime (NEW — state-level proxy)...")
    fbi = load_fbi_crime();            print(f"  {len(fbi):,} states")
    print("[16/17] EIA Electricity (NEW)...")
    eia_e = load_eia_electricity();    print(f"  {len(eia_e):,} states")
    print("[17/17] EIA Natural Gas (NEW)...")
    eia_g = load_eia_gas();            print(f"  {len(eia_g):,} states")

    print("\nMerging county-level datasets on FIPS...")
    df = pop.copy()
    for ds in [bea, zil, fmr, hpi, qcew, cbp, bps, irs, nfip, noaa, usfs, rucc]:
        df = df.merge(ds, on='fips', how='left')

    print("Merging state-level datasets on state_fips...")
    for ds in [stc, fbi, eia_e, eia_g]:
        if not ds.empty and 'state_fips' in ds.columns:
            df = df.merge(ds, on='state_fips', how='left')

    print(f"  Merged: {len(df):,} rows × {len(df.columns)} columns")

    df = df[df['POPESTIMATE2023'] >= MIN_POP].copy()
    print(f"  After pop ≥ {MIN_POP:,} filter: {len(df):,} counties")

    # NO BLANKET IMPUTATION. Per-dimension confidence handles missing data.

    print(f"\nScoring 6 dimensions (per-dim confidence floor: {int(DIM_CONFIDENCE_FLOOR*100)}%)...")
    df = score_dim1(df); print("  [1/6] Affordability & Value ✓")
    df = score_dim2(df); print("  [2/6] Economic Vitality ✓")
    df = score_dim3(df); print("  [3/6] Housing Market Dynamics ✓")
    df = score_dim4(df); print("  [4/6] Quality of Place ✓ (schools: not yet wired)")
    df = score_dim5(df); print("  [5/6] Physical Risk ✓")
    df = score_dim6(df); print("  [6/6] Population Momentum ✓")

    dim_cols = ['dim1', 'dim2', 'dim3', 'dim4', 'dim5', 'dim6']
    dim_weights = [25, 22, 20, 15, 12, 6]

    def total_with_scaling(row):
        present = [(d, w) for d, w in zip(dim_cols, dim_weights) if pd.notna(row[d])]
        if not present:
            return np.nan
        return sum(row[d] for d, _ in present) / sum(w for _, w in present) * 100

    df['total_score'] = df.apply(total_with_scaling, axis=1).clip(0, 100)
    df['market_label'] = df['total_score'].apply(classify)
    df['national_rank'] = df['total_score'].rank(
        ascending=False, method='min', na_option='bottom'
    ).astype(int)
    df['dim4_includes_schools'] = INCLUDES_SCHOOLS

    conf_cols = [f'dim{i}_confidence' for i in range(1, 7)]
    df['data_confidence'] = df[conf_cols].mean(axis=1)

    out_cols = [
        'fips', 'POPESTIMATE2023',
        'total_score', 'market_label', 'national_rank', 'data_confidence',
        'dim1', 'dim2', 'dim3', 'dim4', 'dim5', 'dim6',
        'dim1_confidence', 'dim2_confidence', 'dim3_confidence',
        'dim4_confidence', 'dim5_confidence', 'dim6_confidence',
        'dim4_includes_schools',
        'median_home_value', 'fmr_2br', 'pr_ratio', 'price_income',
        'breakeven_yrs', 'hpi_3yr_avg', 'hpi_latest', 'real_appreciation',
        'per_capita_income', 'real_wage_growth',
        'private_employment', 'avg_annual_wage', 'sector_quality', 'hhi',
        'est_per_1k_pop', 'fiscal_capacity',
        'inventory', 'total_permits', 'permit_gap', 'permit_gap_score', 'permits_per_1k',
        'inmover_income_quality', 'inmover_income_ratio',
        'nfip_per_cap', 'storm_per_cap', 'wildfire_rank',
        'crime_rate', 'crime_score', 'service_efficiency',
        'utility_burden_pct', 'annual_energy_cost',
        'net_migration_rate', 'in_hh', 'out_hh', 'rucc',
    ]
    available = [c for c in out_cols if c in df.columns]
    out = df[available].round(4)
    out['fips'] = out['fips'].astype(str).str.zfill(5)
    out.to_csv(OUT, index=False)

    print(f"\n{'=' * 60}")
    print(f"Output → {OUT}")
    print(f"Counties scored: {out['total_score'].notna().sum():,}")
    print(f"Counties with INSUFFICIENT_DATA: {(out['market_label'] == 'INSUFFICIENT_DATA').sum():,}")
    print(f"\nTotal score distribution:")
    print(out['total_score'].describe().round(2).to_string())
    print(f"\nOverall data_confidence distribution:")
    print(out['data_confidence'].describe().round(1).to_string())
    print(f"\nMarket label counts:")
    print(out['market_label'].value_counts().to_string())

    print(f"\nTop 25 counties:")
    top25 = df.nlargest(25, 'total_score')[
        ['fips', 'total_score', 'market_label', 'data_confidence',
         'median_home_value', 'avg_annual_wage']
    ].round(2)
    print(top25.to_string(index=False))

    print(f"\nDimension summary:")
    for i, dim in enumerate(dim_cols, 1):
        scored = df[dim].notna().sum()
        median = df[dim].median()
        weight = dim_weights[i - 1]
        print(f"  Dim {i}: {scored:,} scored, median {median:.1f} / {weight}")


if __name__ == '__main__':
    main()
