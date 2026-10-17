'''
File containing all of the visuals for the deployed streamlit app
    Visuals include:
        1. Two bar charts diplaying median service hours by income quartiel (with and without weather)
        2. Neigborhood maps of SF displaying income by quartile and median service time by quartile
        3. A barchart displaying median service time by issue type
        4. Tables summarizing the processed rows stored in the bucket
'''
import pandas as pd
import streamlit as st

from user_definition import API_SERVER_URL, TOP_CATEGORIES, MAP_HEIGHT
from dashboard_functions import (neighborhood_table, ordered_chart_data,
                                 prepare_cases, prepare_summary,
                                 quartile_geojson, quartile_map,
                                 resolution_by_quartile_and_weather,
                                 retrieve_data_from_api,
                                 retrieve_neighborhood_shapes,
                                 summarize_resolution)


# Another product of Claude Opus 5.5 when troubleshooting Streamlit slowdowns
# Streamlit re-runs this script on every click, so cache the API calls
# for an hour instead of calling the API each time.
@st.cache_data(ttl=3600, show_spinner="Loading data from the processing API...")
def load_data() -> tuple:
    """Return (summary, cases) from the processing API's /summary and /data."""
    summary = prepare_summary(retrieve_data_from_api(API_SERVER_URL, "/summary"))
    cases = prepare_cases(retrieve_data_from_api(API_SERVER_URL, "/data"),
                          summary)
    return summary, cases

# Asked Claude Opus 5.5 to build a map of SF in streamlit
@st.cache_data(ttl=86400)
def load_neighborhood_shapes() -> dict:
    """Neighborhood outlines for the maps, cached for a day."""
    return retrieve_neighborhood_shapes()

# Asked Claude Opus 5.5 for streamlit code to produce each individual 
# chart type. Map and quartile code was produced by Claude
if __name__ == '__main__':
    #st.set_page_config(layout="wide")
    st.title("Does SF 311 Response Speed Vary by Neighborhood Income?")
    summary, data = load_data()

    if data.empty:
        st.warning(f"No cases returned by {API_SERVER_URL}/data. "
                   "Run POST /process on the processing API first.")
        st.stop()

    with st.sidebar:
        st.write("Filter by Service Category")
        top_categories = data["service_category"].value_counts()\
            .head(TOP_CATEGORIES).index.tolist()
        top_categories.sort()
        selected_categories = []
        for category in top_categories:
            if st.checkbox(f"{category}",
                           value=True,
                           key=f"checkbox_{category}"):
                selected_categories.append(category)
        include_other = st.checkbox("All other categories", value=True,
                                    key="checkbox_other")

        st.write("Filter by Weather")
        selected_weather = []
        for condition in ["Dry", "Rainy", "Unknown"]:
            if st.checkbox(condition, value=True,
                           key=f"checkbox_{condition}"):
                selected_weather.append(condition)

    in_category = data["service_category"].isin(selected_categories)
    if include_other:
        in_category = in_category |\
            ~data["service_category"].isin(top_categories)
    filtered_df = data[in_category & data["weather"].isin(selected_weather)]

    if filtered_df.empty:
        st.write("No cases match the selected filters.")
        st.stop()

    st.write(f"**{len(filtered_df):,}** closed cases from "
             f"**{filtered_df['date'].min()}** to "
             f"**{filtered_df['date'].max()}** across "
             f"**{filtered_df['neighborhood'].nunique()}** neighborhoods.")

    # Income quartile
    st.subheader("Median hours to close by neighborhood income quartile")
    quartile_summary = summarize_resolution(filtered_df, "income_quartile")
    st.bar_chart(ordered_chart_data(quartile_summary, "median hours"))

    # Income quartile and weather
    st.subheader("Median hours to close by income quartile and weather")
    weather_df = resolution_by_quartile_and_weather(filtered_df)
    if weather_df.empty:
        st.write("No weather data for the selected cases.")
    else:
        st.bar_chart(weather_df, stack=False)

    # Two quartile maps
    st.subheader("Income vs. service time by neighborhood")
    st.write("Q1 (lightest) = lowest 25% of neighborhoods, "
             "Q4 (darkest) = highest 25%")
    table = neighborhood_table(filtered_df, summary)
    shapes = load_neighborhood_shapes()
    st.write("**Median household income quartile**")
    st.pydeck_chart(quartile_map(
        quartile_geojson(shapes, table, "median_household_income",
                         "income_quartile"),
        "Income $"),
        use_container_width=True, height=MAP_HEIGHT)
    st.write("**Average hours to close quartile**")
    st.pydeck_chart(quartile_map(
        quartile_geojson(shapes, table, "avg_hours", "hours_quartile"),
        "Avg hours"),
        use_container_width=True, height=MAP_HEIGHT)

    # Neighborhoods lowest to highest income
    st.subheader("Neighborhoods, ordered from lowest to highest income")
    neighborhood_summary = dict(zip(table["neighborhood"],
                                    table["median_hours"]))
    st.bar_chart(ordered_chart_data(neighborhood_summary, "median hours"))
    st.dataframe(table,
                 hide_index=True,
                 column_config={
                     "median_household_income": st.column_config.NumberColumn(
                         format="$%d")})

    # Service categories
    st.subheader("Slowest service categories (median hours) by income quartile")
    slowest = summarize_resolution(filtered_df, "service_category", top_n=10,
                                   sort_by_value=True)
    category_df = filtered_df[filtered_df["service_category"]
                              .isin(slowest.keys())]
    pivot = category_df.pivot_table(index="service_category",
                                    columns="income_quartile",
                                    values="hours_to_close",
                                    aggfunc="median",
                                    observed=True).round(1)
    st.dataframe(pivot.loc[list(slowest.keys())])
