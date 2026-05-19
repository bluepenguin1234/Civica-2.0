"""Compare county_scores.csv (v1) with county_scores_v2.csv (v2). Show top movers."""
import pandas as pd

v1 = pd.read_csv('county_scores.csv', dtype={'fips': str})
v2 = pd.read_csv('county_scores_v2.csv', dtype={'fips': str})

merged = v1.merge(
    v2[['fips', 'total_score', 'market_label', 'data_confidence']],
    on='fips', how='outer', suffixes=('_v1', '_v2')
)
merged['score_delta'] = merged['total_score_v2'] - merged['total_score_v1']
merged['label_changed'] = merged['market_label_v1'] != merged['market_label_v2']

print(f"v1 scored: {v1['total_score'].notna().sum():,}")
print(f"v2 scored: {v2['total_score'].notna().sum():,}")
print(f"In both: {merged['score_delta'].notna().sum():,}")
print(f"Labels changed: {merged['label_changed'].sum():,}")

print(f"\nScore delta distribution:")
print(merged['score_delta'].describe().round(2).to_string())

print(f"\nTop 15 risers (v2 - v1):")
print(merged.nlargest(15, 'score_delta')[
    ['fips', 'total_score_v1', 'market_label_v1',
     'total_score_v2', 'market_label_v2', 'score_delta', 'data_confidence']
].to_string(index=False))

print(f"\nTop 15 fallers (v2 - v1):")
print(merged.nsmallest(15, 'score_delta')[
    ['fips', 'total_score_v1', 'market_label_v1',
     'total_score_v2', 'market_label_v2', 'score_delta', 'data_confidence']
].to_string(index=False))

SPOT_CHECK_FIPS = {
    '12099': 'Palm Beach FL (v1 #1, expect: ACCELERATING or PEAKING)',
    '17031': 'Cook IL (v1 ESTABLISHED, expect: ESTABLISHED)',
    '18057': 'Hamilton IN (v1 top 3, expect: top 10)',
    '47187': 'Williamson TN (v1 top 3, expect: top 10)',
    '36061': 'Manhattan NY (v1 ESTABLISHED 66.1, expect: PEAKING or ESTABLISHED)',
}
print(f"\nSpot checks:")
for fips, label in SPOT_CHECK_FIPS.items():
    row = merged[merged['fips'] == fips]
    if row.empty:
        print(f"  {fips} {label}: NOT FOUND")
        continue
    r = row.iloc[0]
    print(f"  {fips} {label}")
    print(f"    v1: {r['total_score_v1']:.1f} {r['market_label_v1']}")
    print(f"    v2: {r['total_score_v2']:.1f} {r['market_label_v2']}  (conf {r['data_confidence']:.0f}%)")
