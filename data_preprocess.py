import pandas as pd
import os

# Load original data
file_path = "seattle_weather.csv"
df = pd.read_csv(file_path)

# Convert DATE to datetime to extract month
df['DATE'] = pd.to_datetime(df['DATE'])
df['Month'] = df['DATE'].dt.month

# Define metrics to keep and aggregate
# We use the keys from https://www.ncei.noaa.gov/data/gsom/doc/GSOM_documentation.pdf
metrics = ["TAVG", "TMAX", "TMIN", "PRCP", "DT32", "DP01", "DP10", "DSND", "DSNW"]
# Filter to only metrics that actually exist in the dataframe
available_metrics = [m for m in metrics if m in df.columns]

# Grouping columns
group_cols = ['STATION', 'NAME', 'LATITUDE', 'LONGITUDE', 'Month']

# Create the aggregated dataframe (Monthly Norms)
df_agg = df.groupby(group_cols)[available_metrics].mean().reset_index()

# Pre-calculate Season 
season_map = {
    12: 'Winter', 1: 'Winter', 2: 'Winter',
    3: 'Spring', 4: 'Spring', 5: 'Spring',
    6: 'Summer', 7: 'Summer', 8: 'Summer',
    9: 'Autumn', 10: 'Autumn', 11: 'Autumn'
}
df_agg['Season'] = df_agg['Month'].map(season_map)

# Save to CSV
output_path = "seattle_weather_monthly_norms.csv"
df_agg.to_csv(output_path, index=False)

# Check sizes
original_size = os.path.getsize(file_path)
new_size = os.path.getsize(output_path)

print(f"Original Rows: {len(df)}")
print(f"New Rows: {len(df_agg)}")
print(f"Original Size: {original_size/1024:.2f} KB")
print(f"New Size: {new_size/1024:.2f} KB")
print(df_agg.head())