#!/usr/bin/env python3
"""
Civica Scoring Engine v1.2
Harvard-style 6-dimension housing market analysis for all US counties.

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
    """Census Population Estimates 2025 — base universe of counties."""
    df = pd.read_csv(
        f'{DATA}/census_population/co-est2025-alldata.csv',
        encoding='latin1'
    )
    df = df[df['SUMLEV'] == 50].copy()  # county level only
    df['fips'] = df.apply(lambda r: to_fips5(r['STATE'], r['COUNTY']), axis=1)
    # Build output explicitly from 2025 vintage columns to avoid duplicate-column
    # conflicts (the file also contains POPESTIMATE2023 as a historical column).
    out = pd.DataFrame({'fips': df['fips']})
    out['POPESTIMATE2023']       = df['POPESTIMATE2025'].values
    out['RNETMIG2023']           = df['RNETMIG2025'].values
    out['RDOMESTICMIG2023']      = df['RDOMESTICMIG2025'].values
    out['RINTERNATIONALMIG2023'] = df['RINTERNATIONALMIG2025'].values
    out['NETMIG2023']            = df['NETMIG2025'].values
    out['DOMESTICMIG2023']       = df['DOMESTICMIG2025'].values
    return out.dropna(subset=['fips'])


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
    # Nominal 4-year growth — compare to cumulative CPI for real gains
    df['income_4yr_growth']  = (df['per_capita_income'] / df['income_prior'] - 1) * 100
    return df[['fips', 'per_capita_income', 'income_4yr_growth']].dropna(subset=['fips'])


def load_zillow():
    """Zillow ZHVI median home values + active inventory (latest month).

    Returns (county_df, state_hv_medians, state_inv_medians).
    State-level medians are computed from ALL counties in the Zillow file before
    any Census FIPS filtering. This lets main() impute counties whose FIPS changed
    (e.g., Connecticut planning regions post-2022) with the correct state median
    rather than the national median.
    """
    zhvi = pd.read_csv(
        f'{DATA}/zillow/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv'
    )
    zhvi['fips'] = (zhvi['StateCodeFIPS'].astype(str).str.zfill(2) +
                    zhvi['MunicipalCodeFIPS'].astype(str).str.zfill(3))
    date_cols = sorted([c for c in zhvi.columns if c[:4].isdigit()])
    latest    = date_cols[-1]
    yr3_back  = [c for c in date_cols if c.startswith(str(int(latest[:4]) - 3))]
    zhvi['median_home_value']  = pd.to_numeric(zhvi[latest], errors='coerce')
    zhvi['home_value_3yr_ago'] = pd.to_numeric(zhvi[yr3_back[0] if yr3_back else latest], errors='coerce')
    # Total appreciation from January of year-3 to latest month (~3.8 yrs, not annualized)
    zhvi['home_appreciation_total_3yr'] = (
        zhvi['median_home_value'] / zhvi['home_value_3yr_ago'] - 1
    ) * 100

    inv = pd.read_csv(
        f'{DATA}/zillow/County_invt_fs_uc_sfrcondo_sm_month.csv'
    )
    inv['fips'] = (inv['StateCodeFIPS'].astype(str).str.zfill(2) +
                   inv['MunicipalCodeFIPS'].astype(str).str.zfill(3))
    inv_dates    = sorted([c for c in inv.columns if c[:4].isdigit()])
    inv['inventory'] = pd.to_numeric(inv[inv_dates[-1]], errors='coerce')

    # State-level medians from the full Zillow county universe (before Census FIPS filtering).
    # Zillow still carries old county FIPS (e.g., CT pre-2022 counties) that have no match
    # in the current Census pop file, so these medians are richer than what the merged df can
    # compute on its own.
    zhvi['_state'] = zhvi['StateCodeFIPS'].astype(str).str.zfill(2)
    inv['_state']  = inv['StateCodeFIPS'].astype(str).str.zfill(2)
    state_hv  = zhvi.dropna(subset=['median_home_value']).groupby('_state')['median_home_value'].median()
    state_inv = inv.dropna(subset=['inventory']).groupby('_state')['inventory'].median()

    county_df = zhvi[['fips', 'median_home_value', 'home_appreciation_total_3yr']].merge(
        inv[['fips', 'inventory']], on='fips', how='left'
    )
    return county_df, state_hv, state_inv


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
    """BLS QCEW wages, employment size, sector quality score, HHI. Uses 2024 if available, falls back to 2023."""
    qcew_2024 = f'{DATA}/bls_qcew/2024.annual.singlefile.csv'
    qcew_2023 = f'{DATA}/bls_qcew/2023.annual.singlefile.csv'
    qcew_path = qcew_2024 if os.path.exists(qcew_2024) else qcew_2023
    print(f"    Streaming BLS QCEW ({os.path.basename(qcew_path)})...")
    totals, sectors = [], []

    for chunk in pd.read_csv(
        qcew_path,
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

    # Sector quality weights — ratios reflect BLS OEWS median wages by supersector
    # relative to the all-private median. Professional/Finance consistently 30-40%
    # above private median; Retail/Manufacturing 20-40% below. See METHODOLOGY.md §14.6.
    WEIGHTS = {
        '54': 1.30,  # Professional, Scientific, Technical (OEWS: ~40% above median)
        '52': 1.30,  # Finance & Insurance (OEWS: ~35% above median)
        '62': 1.00,  # Healthcare & Social Assistance (near median)
        '61': 1.00,  # Educational Services (near median)
        '23': 0.80,  # Construction (cyclical; ~10% above median but volatile)
        '44': 0.60,  # Retail Trade (OEWS: ~25% below median)
        '45': 0.60,  # Retail Trade
        '31': 0.60,  # Manufacturing (secular US employment decline; ~10% below median)
        '32': 0.60,
        '33': 0.60,
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
    df = pd.read_csv(f'{DATA}/census_cbp/cbp23co.txt', dtype=str, low_memory=False)
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
        f'{DATA}/census_bps/co2025a.txt',
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
    # Require ≥10 households on each side to produce a reliable average AGI
    m['in_avg_agi']  = np.where(m['in_hh']  >= 10, m['in_agi']  / m['in_hh'],  np.nan)
    m['out_avg_agi'] = np.where(m['out_hh'] >= 10, m['out_agi'] / m['out_hh'], np.nan)
    # Ratio > 1 means higher-income people moving in than leaving (positive demand signal)
    m['inmover_income_ratio'] = np.where(
        (m['in_hh'] >= 10) & (m['out_hh'] >= 10),
        m['in_avg_agi'] / m['out_avg_agi'],
        np.nan
    )
    return m[['fips', 'inmover_income_ratio', 'in_hh', 'out_hh']]


def load_nfip():
    """FEMA NFIP: flood insurance claims paid, 2015-2024 (10-year window)."""
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
        df = df[df['yr'].between(2015, 2024)]  # enforce documented 10-year window
    return df.groupby('fips')['paid'].sum().reset_index().rename(columns={'paid': 'nfip_claims'})


def load_noaa_storm():
    """NOAA Storm Events 2019-2023: property damage by county."""
    print("    Reading NOAA Storm Events (5 files, ~323 MB)...")
    parts = []
    storm_dir = f'{DATA}/noaa_storm_events'
    for fn in sorted(os.listdir(storm_dir)):
        if not fn.endswith('.csv'):
            continue
        # Only include files for years in the documented 5-year window (2020-2024)
        # NOAA filenames follow pattern: StormEvents_details-ftp_v1.0_d{YYYY}_*.csv
        if not any(f'_d{y}_' in fn for y in range(2020, 2025)):
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

    Violent crime codes — UCR Part 1 definition (murder, sex offenses, robbery,
    aggravated assault). Simple assault (13B) and intimidation (13C) are excluded
    because they are not UCR Part 1 violent crimes and would inflate county rates
    relative to published FBI statistics.
      09A=Murder/Non-Negligent Manslaughter, 09B=Negligent Manslaughter,
      11A=Rape, 11B=Sodomy, 11C=Sexual Assault w/ Object, 11D=Fondling,
      120=Robbery, 13A=Aggravated Assault
    """
    print("    Streaming FBI NIBRS 2024 (5.8 GB) — this takes ~10 minutes...")

    # UCR Part 1 violent crimes only — excludes 13B (simple assault), 13C (intimidation),
    # and 100 (kidnapping), which are not in the standard FBI violent crime rate definition.
    VIOLENT = {'09A', '09B', '11A', '11B', '11C', '11D', '120', '13A'}

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

    # Monthly ownership cost: P&I (7% 30yr 80% LTV) + property tax (1.2%) + insurance (0.5%).
    # KNOWN LIMITATION: 1.2% property tax is the national median effective rate.
    # Actual rates range 0.28% (HI) to 2.23% (NJ/IL) — error up to $340/mo at $400k home value.
    r = 0.07 / 12
    mortgage_factor = r / (1 - (1 + r) ** -360)
    d['monthly_piti'] = (
        d['median_home_value'] * 0.80 * mortgage_factor
        + d['median_home_value'] * 0.012 / 12
        + d['median_home_value'] * 0.005 / 12
    )

    # Breakeven: years to recover 20% down payment through monthly cost savings vs. renting.
    # When PITI < FMR (buying immediately beats renting), breakeven = 0 — best possible score.
    monthly_savings = d['monthly_piti'] - d['fmr_2br']
    d['breakeven_yrs'] = np.where(
        monthly_savings <= 0,
        0.0,  # buying cheaper than renting from day 1
        (d['median_home_value'] * 0.20 / (monthly_savings * 12)).clip(0, 30)
    )

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
    s2 = pct(d['sector_quality'])      # 25%: OEWS-calibrated sector mix (Prof/Finance premium)
    s3 = pct_inv(d['hhi'])            # 25%: lower HHI = more diversified = more resilient
    s4 = pct(d['income_4yr_growth'])   # 15%: nominal income trajectory (BEA per capita growth)

    d['dim2'] = (s1*0.35 + s2*0.25 + s3*0.25 + s4*0.15) / 100 * 22
    return d


def score_dim3(df):
    """Housing Market Dynamics — 20 pts.
    3yr Appreciation Trend 35% | Current Momentum 15% | Supply Tightness 30% | Permit Pipeline 20%
    """
    d = df.copy()
    s1 = pct(d['hpi_3yr_avg'])   # 35%: FHFA 3-yr avg annual appreciation (sustained trend)
    s2 = pct(d['hpi_latest'])    # 15%: FHFA latest annual HPI change (current momentum)

    # Normalize inventory by population to remove county-size bias (r=0.83 with raw count).
    # inventory_per_1k is a proxy for market tightness; months-of-supply would be ideal
    # but requires a Zillow sales-count file not currently downloaded. See METHODOLOGY.md §14.
    d['inventory_per_1k'] = d['inventory'] / d['POPESTIMATE2023'].clip(lower=100) * 1000
    s3 = pct_inv(d['inventory_per_1k'])  # 30%: lower listings per 1k = tighter market

    # KNOWN LIMITATION: higher permits = better is a demand-response proxy.
    # Correct metric is permits ÷ projected household formation (permit-gap ratio), but that
    # requires ACS projections, which violates the no-survey-data policy. See METHODOLOGY.md §14.1.
    s4 = pct(d['total_permits']) # 20%: Census BPS new units permitted (supply pipeline)

    d['dim3'] = (s1*0.35 + s2*0.15 + s3*0.30 + s4*0.20) / 100 * 20
    return d


def score_dim4(df):
    """Quality of Place — 15 pts.
    Crime Rate 35% | Urban Access 40% | Amenity Density 25%

    Crime: FBI NIBRS 2024 violent offenses per 100k residents (UCR Part 1 definition).
    Counties without NIBRS coverage (nibrs_imputed=1, set in main() before median fill)
    receive their RUCC-tier median rate so non-reporting is not mistaken for low crime.
    """
    d = df.copy()

    # Crime rate per 100k — lower is better
    d['violent_per100k'] = (
        d['violent_offenses'] /
        d['POPESTIMATE2023'].clip(lower=100) * 100_000
    )

    # Impute non-reporting counties with RUCC-tier median using the nibrs_imputed flag
    # (set before global median fill in main() so it correctly identifies missing counties)
    d['rucc_tier'] = pd.cut(
        d['rucc'].fillna(5),
        bins=[0, 3, 6, 9],
        labels=['metro', 'micro', 'rural']
    )
    tier_medians = (
        d[d['nibrs_imputed'] == 0]
        .groupby('rucc_tier')['violent_per100k']
        .median()
    )
    mask = d['nibrs_imputed'] == 1
    d.loc[mask, 'violent_per100k'] = d.loc[mask, 'rucc_tier'].map(tier_medians)
    d['violent_per100k'] = d['violent_per100k'].fillna(d['violent_per100k'].median())

    s1 = pct_inv(d['violent_per100k'])  # 35%: lower crime rate = better
    s2 = pct_inv(d['rucc'])             # 40%: USDA RUCC — metro counties score higher
                                         # (metro proximity predicts resale liquidity; see §14)
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
    s2 = pct(d['inmover_income_ratio'])  # 40%: in-mover AGI ÷ out-mover AGI (IRS SOI)
                                         # ratio > 1.0 means higher-income people arriving than leaving

    d['dim6'] = (s1*0.60 + s2*0.40) / 100 * 6
    return d


# ── Market Labels ──────────────────────────────────────────────────────────────

# Thresholds calibrated to the empirical score distribution (mean≈50, std≈7.5, range 21–73).
# v1.2 distribution (post CT-ZHVI fix, UCR Part 1 crime):
# ACCELERATING (14) · PEAKING (143) · ESTABLISHED (558) · EMERGING (1236) ·
# FRONTIER (703) · TURNING (152) · SPECULATIVE (12) · AVOID (2)
LABELS = [
    (68, 'ACCELERATING'),   # top ~0.1%: all signals aligned and prices still defensible
    (62, 'PEAKING'),        # strong momentum approaching affordability ceiling
    (55, 'ESTABLISHED'),    # healthy balanced market, sustainable fundamentals
    (46, 'EMERGING'),       # improving fundamentals, early-mover opportunity
    (38, 'FRONTIER'),       # below-average market, higher uncertainty
    (30, 'TURNING'),        # softening demand, watch for continued weakness
    (26, 'SPECULATIVE'),    # poor fundamentals, momentum-only pricing risk
    (0,  'AVOID'),          # systemic weakness across multiple dimensions
]


def classify(score):
    for threshold, label in LABELS:
        if score >= threshold:
            return label
    return 'AVOID'


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Civica Harvard Scoring Engine v1.2")
    print("=" * 60)

    print("\n[1/14]  Census Population...")
    pop  = load_population();  print(f"          {len(pop):,} counties")

    print("[2/14]  BEA Income...")
    bea  = load_bea();         print(f"          {len(bea):,} counties")

    print("[3/14]  Zillow Home Values + Inventory...")
    zil, _zhvi_state_hv, _zhvi_state_inv = load_zillow()
    print(f"          {len(zil):,} counties")

    print("[4/14]  HUD Fair Market Rents...")
    fmr  = load_fmr();         print(f"          {len(fmr):,} FMR areas")

    print("[5/14]  FHFA HPI...")
    hpi  = load_hpi();         print(f"          {len(hpi):,} counties")

    print("[6/14]  BLS QCEW...")
    qcew = load_qcew();        print(f"          {len(qcew):,} counties")

    print("[7/14]  Census CBP...")
    cbp  = load_cbp();         print(f"          {len(cbp):,} counties")

    print("[8/14]  Census BPS Permits...")
    bps  = load_bps();         print(f"          {len(bps):,} counties")

    print("[9/14]  IRS Migration...")
    irs  = load_irs();         print(f"          {len(irs):,} counties")

    print("[10/14] FEMA NFIP Claims...")
    nfip = load_nfip();        print(f"          {len(nfip):,} counties")

    print("[11/14] NOAA Storm Events...")
    noaa = load_noaa_storm();  print(f"          {len(noaa):,} counties")

    print("[12/14] USFS Wildfire Risk...")
    usfs = load_usfs();        print(f"          {len(usfs):,} counties")

    print("[13/14] USDA Rural-Urban Codes...")
    rucc = load_rucc();        print(f"          {len(rucc):,} counties")

    print("[14/14] FBI NIBRS Crime (2024)...")
    nibrs = load_nibrs_crime(); print(f"          {len(nibrs):,} counties with crime data")

    # ── Merge ────────────────────────────────────────────────────────────────
    print("\nMerging all datasets on FIPS...")
    df = pop.copy()
    for ds in [bea, zil, fmr, hpi, qcew, cbp, bps, irs, nfip, noaa, usfs, rucc, nibrs]:
        df = df.merge(ds, on='fips', how='left')
    print(f"  Merged: {len(df):,} rows × {len(df.columns)} columns")

    # Require minimum population to score (very small counties have sparse data)
    df = df[df['POPESTIMATE2023'] >= 5_000].copy()
    print(f"  After pop ≥ 5,000 filter: {len(df):,} counties")

    # Flag counties with no NIBRS data BEFORE median fill so score_dim4 can
    # apply RUCC-tier imputation to the correct counties (not median-filled ones)
    df['nibrs_imputed'] = df['violent_offenses'].isna().astype(int)

    # Flag counties with no Zillow ZHVI BEFORE any home value imputation.
    # This flag is exported to county_scores.csv so downstream tools can warn users.
    df['zhvi_imputed'] = df['median_home_value'].isna().astype(int)

    # State-level ZHVI imputation for counties missing home value data.
    # Uses state medians from the full Zillow county file (_zhvi_state_hv/_zhvi_state_inv),
    # which includes old county FIPS that no longer appear in Census (e.g., CT pre-2022
    # counties 09001-09015). This prevents CT planning regions (09110-09190) from being
    # imputed with the ~$236k national median when CT's actual median is ~$380k.
    df['_state'] = df['fips'].str[:2]
    _hv_miss  = df['zhvi_imputed'] == 1
    _inv_miss = df['inventory'].isna()
    df.loc[_hv_miss,  'median_home_value'] = df.loc[_hv_miss,  '_state'].map(_zhvi_state_hv)
    df.loc[_inv_miss, 'inventory']          = df.loc[_inv_miss, '_state'].map(_zhvi_state_inv)
    df.drop(columns=['_state'], inplace=True)
    n_zhvi_state = _hv_miss.sum() - df['median_home_value'].isna().sum()
    n_zhvi_nat   = df['median_home_value'].isna().sum()
    if _hv_miss.any():
        print(f"  ZHVI imputed (state-level): {n_zhvi_state}, (national fallback): {n_zhvi_nat}")

    # Fill remaining missing values with national medians so every county gets a score.
    # Note: counties with missing inputs receive the median score for those metrics,
    # not a reduced score. See METHODOLOGY.md §4 for accurate description of this behavior.
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
        'median_home_value', 'fmr_2br', 'pr_ratio', 'price_income',
        'breakeven_yrs', 'monthly_piti', 'hpi_3yr_avg', 'hpi_latest',
        'home_appreciation_total_3yr',  # Zillow total gain ~3.8yr, not annualized
        'per_capita_income', 'income_4yr_growth',
        'private_employment', 'avg_annual_wage', 'sector_quality', 'hhi',
        'inventory', 'inventory_per_1k', 'total_permits', 'inmover_income_ratio',
        'nfip_per_cap', 'storm_per_cap', 'wildfire_rank',
        'RNETMIG2023', 'RDOMESTICMIG2023', 'rucc',
        'est_per_1k', 'in_hh', 'out_hh',
        'violent_offenses', 'violent_per100k', 'nibrs_imputed',
        'zhvi_imputed',
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
