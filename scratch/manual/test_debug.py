from nselib import capital_market

df = capital_market.price_volume_and_deliverable_position_data(
    symbol="WABAG",
    from_date="01-01-2025",
    to_date="28-06-2026"
)

print(df.shape)
print(df.head())