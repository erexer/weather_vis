import calendar
import os

import pandas as pd
import pydeck as pdk
import streamlit as st

# Set page configuration
st.set_page_config(page_title="Weather Visualization", layout="wide")

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
    "DSNW": "Days with Snowfall ≥ 1 inch",
}


# --- DATA LOADING ---
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)

        # Scenario 1: Raw Data (Has specific dates, e.g., "2023-01-01")
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"])
            df["Month"] = df["DATE"].dt.month
            df["Month_Name"] = df["DATE"].dt.month_name()

            # Season Mapping
            season_map = {
                12: "Winter",
                1: "Winter",
                2: "Winter",
                3: "Spring",
                4: "Spring",
                5: "Spring",
                6: "Summer",
                7: "Summer",
                8: "Summer",
                9: "Autumn",
                10: "Autumn",
                11: "Autumn",
            }
            df["Season"] = df["DATE"].dt.month.map(season_map)

        # Scenario 2: Pre-Processed Data (Already has Month/Season, no specific Date)
        elif "Month" in df.columns:
            # Create a helper Month_Name column for display
            df["Month_Name"] = df["Month"].apply(lambda x: calendar.month_name[x])
            # Ensure Season exists (if not in file, map it)
            if "Season" not in df.columns:
                season_map = {
                    12: "Winter",
                    1: "Winter",
                    2: "Winter",
                    3: "Spring",
                    4: "Spring",
                    5: "Spring",
                    6: "Summer",
                    7: "Summer",
                    8: "Summer",
                    9: "Autumn",
                    10: "Autumn",
                    11: "Autumn",
                }
                df["Season"] = df["Month"].map(season_map)

        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


# --- MAIN APP ---
st.title("Weather Data Visualizer")
st.markdown(
    "Explore weather patterns. The example data are pulled from NOAA's [Climate Data Online](https://www.ncei.noaa.gov/cdo-web/) for Seattle, WA."
)

# Sidebar for controls
st.sidebar.header("Data Settings")

# File Loading
current_dir = os.path.dirname(os.path.abspath(__file__))
default_path = os.path.join(current_dir, "data", "seattle_weather_monthly_norms.csv")

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

    # Determine default selection priority: PRCP -> TMAX -> First available
    if "PRCP" in available_metrics:
        default_index = available_metrics.index("PRCP")
    elif "TMAX" in available_metrics:
        default_index = available_metrics.index("TMAX")
    else:
        default_index = 0

    # Use a format function to show nice names in the dropdown, but keep the code as the value
    metric_code = st.sidebar.selectbox(
        "Select Data Type",
        available_metrics,
        format_func=lambda x: f"{DATA_DEFINITIONS[x]} ({x})",
        index=default_index,
    )

    metric_name = DATA_DEFINITIONS[metric_code]

    # --- 2. TIME AGGREGATION ---
    st.sidebar.subheader("Time Filters")
    time_mode = st.sidebar.radio(
        "Aggregation Mode", ["All Time", "By Season", "By Month"]
    )

    filtered_df = df.copy()
    filter_description = "All Time Average"

    if time_mode == "By Season":
        season = st.sidebar.selectbox(
            "Select Season", ["Winter", "Spring", "Summer", "Autumn"]
        )
        filtered_df = filtered_df[filtered_df["Season"] == season]
        filter_description = f"Average for {season}"

    elif time_mode == "By Month":
        month_index = st.sidebar.slider("Select Month", 1, 12, 1, format="%d")
        # Update: Use calendar to get name (works without a DATE column)
        month_name = calendar.month_name[month_index]
        filtered_df = filtered_df[filtered_df["Month"] == month_index]
        filter_description = f"Average for {month_name}"

    # --- 3. AGGREGATION LOGIC ---
    agg_df = (
        filtered_df.groupby(["STATION", "NAME", "LATITUDE", "LONGITUDE"])[metric_code]
        .mean()
        .reset_index()
    )
    agg_df = agg_df.dropna(subset=[metric_code])

    # --- 4. VISUALIZATION ---

    # 0. MAP APPEARANCE CONTROLS
    st.sidebar.markdown("---")

    # Try to detect default theme (defaults to "dark" if unknown)
    try:
        default_theme = st.get_option("theme.base")
    except:
        default_theme = "dark"

    # We use a checkbox for the Dot Outline because Python can't auto-detect
    # dynamic theme changes in the browser.
    use_light_mode_dots = st.sidebar.checkbox(
        "Optimize Dots for Light Mode", value=(default_theme == "light")
    )

    # Set dot outline color based on checkbox
    if use_light_mode_dots:
        dot_line_color = [0, 0, 0]  # Black outline for Light Maps
    else:
        dot_line_color = [255, 255, 255]  # White outline for Dark Maps

    # 1. Determine Units
    UNIT_MAP = {
        "TAVG": "°F",
        "TMAX": "°F",
        "TMIN": "°F",
        "PRCP": "Inches",
        "DT32": "Days",
        "DP01": "Days",
        "DP10": "Days",
        "DSND": "Days",
        "DSNW": "Days",
    }
    unit_label = UNIT_MAP.get(metric_code, "")

    # 2. Get Date Range
    if "DATE" in filtered_df.columns:
        start_date = filtered_df["DATE"].min().strftime("%b %Y")
        end_date = filtered_df["DATE"].max().strftime("%b %Y")
        date_range_str = f"({start_date} - {end_date})"
    else:
        date_range_str = "(Climatological Average)"

    # 3. Update Header
    st.subheader(f"Map: {metric_name} {date_range_str}")

    if agg_df.empty:
        st.warning("No data available for this selection.")
    else:
        # --- A. PREPARE DATA ---
        agg_df["formatted_val"] = agg_df[metric_code].apply(
            lambda x: f"{x:.2f} {unit_label}"
        )

        # --- B. COLOR SCALE ---
        color_range = [
            [65, 182, 196],
            [127, 205, 187],
            [199, 233, 180],
            [237, 248, 177],
            [253, 212, 158],
            [227, 26, 28],
        ]

        min_val = agg_df[metric_code].min()
        max_val = agg_df[metric_code].max()
        gradient_style = "linear-gradient(to right, rgb(65, 182, 196), rgb(127, 205, 187), rgb(199, 233, 180), rgb(237, 248, 177), rgb(253, 212, 158), rgb(227, 26, 28))"

        # --- C. LEGEND (AUTO-THEMED) ---
        # We use var(--text-color) and var(--secondary-background-color)
        # so this HTML automatically matches your Streamlit theme.
        st.markdown(
            f"""
            <div style='background-color: var(--secondary-background-color); padding: 10px; border-radius: 5px; margin-bottom: 10px; border: 1px solid var(--secondary-background-color);'>
                <p style='color: var(--text-color); margin: 0; font-size: 14px; font-weight: bold;'>
                    {metric_name} Scale
                </p>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-top: 5px;'>
                    <span style='color: var(--text-color); font-family: monospace;'>{min_val:.1f} {unit_label}</span>
                    <div style='flex-grow: 1; height: 10px; background: {gradient_style}; margin: 0 10px; border-radius: 5px;'></div>
                    <span style='color: var(--text-color); font-family: monospace;'>{max_val:.1f} {unit_label}</span>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        # --- D. MAP LAYERS ---
        heatmap_layer = pdk.Layer(
            "HeatmapLayer",
            data=agg_df,
            get_position="[LONGITUDE, LATITUDE]",
            get_weight=metric_code,
            opacity=0.6,
            pickable=False,
            radius_pixels=50,
            intensity=1,
            threshold=0.05,
            color_range=color_range,
        )

        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=agg_df,
            get_position="[LONGITUDE, LATITUDE]",
            get_radius=250,
            get_fill_color=[50, 50, 50, 150],
            get_line_color=dot_line_color,  # Dynamic outline color
            get_line_width=20,
            pickable=True,
            auto_highlight=True,
        )

        view_state = pdk.ViewState(
            latitude=47.6062, longitude=-122.3321, zoom=8, pitch=0
        )

        tooltip_html = {
            "html": "<b>{NAME}</b><br/>" + f"{metric_name}: <b>{{formatted_val}}</b>",
            "style": {"backgroundColor": "steelblue", "color": "white"},
        }

        st.pydeck_chart(
            pdk.Deck(
                map_style=None,  # <--- Setting this to None allows Streamlit to auto-set the style
                initial_view_state=view_state,
                layers=[heatmap_layer, scatter_layer],
                tooltip=tooltip_html,
            )
        )

        st.caption(f"Visualizing {len(agg_df)} stations.")

        # --- E. DATA TABLE ---
        st.write("---")
        st.subheader("Top Stations")

        display_df = agg_df[["NAME", metric_code]].sort_values(
            by=metric_code, ascending=False
        )
        display_df.columns = ["Station", f"{metric_name} ({unit_label})"]

        st.dataframe(
            display_df.style.format({f"{metric_name} ({unit_label})": "{:.2f}"}),
            use_container_width=True,
            height=400,
        )
