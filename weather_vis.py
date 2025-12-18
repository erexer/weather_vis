import streamlit as st
import pandas as pd
import pydeck as pdk
import os

# Set page configuration
st.set_page_config(page_title="Seattle Weather Visualization", layout="wide")

# --- MAPPINGS ---
# Based on NOAA GSOM documentation
DATA_DEFINITIONS = {
    "TAVG": "Average Temperature",
    "TMAX": "Maximum Temperature",
    "TMIN": "Minimum Temperature",
    "PRCP": "Total Precipitation",
    "DT32": "Days with Min Temp ≤ 32°F (Freezing)",
    "DP01": "Days with Precip ≥ 0.01 inch",
    "DP10": "Days with Precip ≥ 0.10 inch",
    "DSND": "Days with Snow Depth ≥ 1 inch",
    "DSNW": "Days with Snowfall ≥ 1 inch"
}

# --- DATA LOADING ---
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        
        # Standardize Date
        df['DATE'] = pd.to_datetime(df['DATE'])
        
        # Create helper columns
        df['Month'] = df['DATE'].dt.month
        df['Month_Name'] = df['DATE'].dt.month_name()
        
        # Season Mapping
        season_map = {
            12: 'Winter', 1: 'Winter', 2: 'Winter',
            3: 'Spring', 4: 'Spring', 5: 'Spring',
            6: 'Summer', 7: 'Summer', 8: 'Summer',
            9: 'Autumn', 10: 'Autumn', 11: 'Autumn'
        }
        df['Season'] = df['DATE'].dt.month.map(season_map)
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# --- MAIN APP ---
st.title("Seattle Weather Data Visualizer")
st.markdown("Explore weather patterns in the Seattle area using NOAA Climate Data.")

# Sidebar for controls
st.sidebar.header("Data Settings")

# Robust File Loading
current_dir = os.path.dirname(os.path.abspath(__file__))
default_path = os.path.join(current_dir, "seattle_weather.csv")

uploaded_file = st.sidebar.file_uploader("Upload your NOAA CSV file", type=["csv"])

if uploaded_file is not None:
    df = load_data(uploaded_file)
elif os.path.exists(default_path):
    df = load_data(default_path)
else:
    st.error("File not found. Please upload a CSV.")
    df = None

if df is not None:
    # --- 1. DATA SELECTION ---
    # Filter available columns based on the definitions we know
    available_metrics = [col for col in DATA_DEFINITIONS.keys() if col in df.columns]
    
    if not available_metrics:
        st.error("The dataset does not contain the expected weather columns.")
        st.stop()

    # Use a format function to show nice names in the dropdown, but keep the code as the value
    metric_code = st.sidebar.selectbox(
        "Select Data Type", 
        available_metrics, 
        format_func=lambda x: f"{DATA_DEFINITIONS[x]} ({x})",
        index=available_metrics.index('TMAX') if 'TMAX' in available_metrics else 0
    )
    
    metric_name = DATA_DEFINITIONS[metric_code]
    
    # --- 2. TIME AGGREGATION ---
    st.sidebar.subheader("Time Filters")
    time_mode = st.sidebar.radio("Aggregation Mode", ["All Time", "By Season", "By Month"])
    
    filtered_df = df.copy()
    filter_description = "All Time Average"
    
    if time_mode == "By Season":
        season = st.sidebar.selectbox("Select Season", ["Winter", "Spring", "Summer", "Autumn"])
        filtered_df = filtered_df[filtered_df['Season'] == season]
        filter_description = f"Average for {season}"
        
    elif time_mode == "By Month":
        month_index = st.sidebar.slider("Select Month", 1, 12, 1, format="%d")
        month_name = pd.to_datetime(f"2023-{month_index}-01").month_name()
        filtered_df = filtered_df[filtered_df['Month'] == month_index]
        filter_description = f"Average for {month_name}"

    # --- 3. AGGREGATION LOGIC ---
    agg_df = filtered_df.groupby(['STATION', 'NAME', 'LATITUDE', 'LONGITUDE'])[metric_code].mean().reset_index()
    agg_df = agg_df.dropna(subset=[metric_code])
    
    # --- 4. VISUALIZATION ---
    
    # 1. Determine Units
    UNIT_MAP = {
        "TAVG": "°F", "TMAX": "°F", "TMIN": "°F",
        "PRCP": "Inches",
        "DT32": "Days", "DP01": "Days", "DP10": "Days", "DSND": "Days", "DSNW": "Days"
    }
    unit_label = UNIT_MAP.get(metric_code, "")

    # 2. Get Date Range
    if not filtered_df.empty:
        start_date = filtered_df['DATE'].min().strftime('%b %Y')
        end_date = filtered_df['DATE'].max().strftime('%b %Y')
        date_range_str = f"({start_date} - {end_date})"
    else:
        date_range_str = "(No Date Range)"

    # 3. Update Header
    st.subheader(f"Map: {metric_name} {date_range_str}")
    
    if agg_df.empty:
        st.warning("No data available for this selection.")
    else:
        # --- A. PREPARE DATA ---
        agg_df["formatted_val"] = agg_df[metric_code].apply(lambda x: f"{x:.2f} {unit_label}")

        # --- B. COLOR SCALE & LEGEND ---
        color_range = [
            [65, 182, 196], [127, 205, 187], [199, 233, 180],
            [237, 248, 177], [253, 212, 158], [227, 26, 28]
        ]
        
        min_val = agg_df[metric_code].min()
        max_val = agg_df[metric_code].max()
        gradient_style = "linear-gradient(to right, rgb(65, 182, 196), rgb(127, 205, 187), rgb(199, 233, 180), rgb(237, 248, 177), rgb(253, 212, 158), rgb(227, 26, 28))"
        
        # Legend HTML
        st.markdown(f"""
            <div style='background-color: #262730; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
                <p style='color: white; margin: 0; font-size: 14px; font-weight: bold;'>
                    {metric_name} Scale
                </p>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-top: 5px;'>
                    <span style='color: white; font-family: monospace;'>{min_val:.1f} {unit_label}</span>
                    <div style='flex-grow: 1; height: 10px; background: {gradient_style}; margin: 0 10px; border-radius: 5px;'></div>
                    <span style='color: white; font-family: monospace;'>{max_val:.1f} {unit_label}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # --- C. MAP (PYDECK) ---
        heatmap_layer = pdk.Layer(
            "HeatmapLayer",
            data=agg_df,
            get_position='[LONGITUDE, LATITUDE]',
            get_weight=metric_code,
            opacity=0.6,
            pickable=False,
            radius_pixels=50,
            intensity=1,
            threshold=0.05,
            color_range=color_range
        )
        
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=agg_df,
            get_position='[LONGITUDE, LATITUDE]',
            get_radius=250, 
            get_fill_color=[50, 50, 50, 150],
            get_line_color=[255, 255, 255],
            get_line_width=20,
            pickable=True, 
            auto_highlight=True
        )

        view_state = pdk.ViewState(
            latitude=47.6062, longitude=-122.3321, zoom=8, pitch=0
        )
        
        tooltip_html = {
            "html": "<b>{NAME}</b><br/>" + f"{metric_name}: <b>{{formatted_val}}</b>",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }
        
        st.pydeck_chart(pdk.Deck(
            map_style=None, 
            initial_view_state=view_state,
            layers=[heatmap_layer, scatter_layer], 
            tooltip=tooltip_html
        ))
        
        st.caption(f"Visualizing {len(agg_df)} stations.")
        
        # --- D. DATA TABLE (Moved Below Map) ---
        st.write("---") # Horizontal separator line
        st.subheader("Top Stations")
        
        display_df = agg_df[['NAME', metric_code]].sort_values(by=metric_code, ascending=False)
        display_df.columns = ['Station', f"{metric_name} ({unit_label})"]
        
        # Use st.dataframe with use_container_width=True to fill the width
        st.dataframe(
            display_df.style.format({f"{metric_name} ({unit_label})": "{:.2f}"}), 
            use_container_width=True,
            height=400
        )

st.markdown("These data are pulled from [Climate Data Online](https://www.ncei.noaa.gov/cdo-web/).")