'''
Functions used by the 311 Income Response dashboard (dashboard.py).

Data is pulled from the transform API (api/transform.py),
which cleaned and joined the 311, ACS, weather and neighborhood files

Neighborhood outlines for the maps come from DataSF 
'''
import pandas as pd
import pydeck as pdk # Claude Opus 5.5 recommended pydeck to produce maps 
import requests

RAINY_DAY_MM = 1.0 # Used Claude recommendation for a "light rain" in mm
NEIGHBORHOOD_GEOJSON_URL = "https://data.sfgov.org/resource/j2bu-swwd.geojson" 
QUARTILE_COLORS = [[239, 243, 255, 190],   # Q1 (lightest)
                   [189, 215, 231, 190],
                   [107, 174, 214, 190],
                   [33, 113, 181, 190]]    # Q4 (darkest)

# Retrieve data from processing API
def retrieve_data_from_api(api_server_url: str, endpoint: str) -> pd.DataFrame:
    """
    Call a get endpoint of the processing API and return its list of
    records as a DataFrame.
    """
    response = requests.get(f"{api_server_url.rstrip('/')}{endpoint}",
                            timeout=60)
    response.raise_for_status() # Claude Opus 5.5 suggested this function to raise exception
    return pd.DataFrame(response.json())

# Segment income and median service time into quartiles
# Asked Claude Opus 5.5 how to create quartile labels
def quartile_labels(n_groups: int) -> list:
    """["Q1 (low)", "Q2", "Q3", "Q4 (high)"] for n_groups=4."""
    labels = [f"Q{i}" for i in range(1, n_groups + 1)]
    labels[0] += " (low)"
    labels[-1] += " (high)"
    return labels

# Asked Claude Opus 5.5 how to sort by quartile to return a df for streamlit
def add_quartile(df: pd.DataFrame, 
                 value_column: str,
                 quartile_column: str) -> pd.DataFrame:
    """
    Add quartile_column with each row's quartile of value_column,
    from "Q1 (lowest)" to "Q4 (highest)". Uses fewer groups when there
    are fewer than 4 rows.
    """
    df = df.copy()
    n_groups = min(4, len(df))
    if n_groups == 0:
        df[quartile_column] = pd.Series(dtype="category")
        return df
    df[quartile_column] = pd.qcut(df[value_column].rank(method="first"),
                                  n_groups, labels=quartile_labels(n_groups))
    return df


def prepare_summary(summary: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the /summary rows and add each neighborhood's income quartile.
    """
    df = summary.copy()
    for column in ["median_household_income", "total_population",
                   "cases", "median_hours"]:
        df[column] = pd.to_numeric(df[column], errors="coerce") # Claude Opus 5.5 provided the "errors="coerce" during troubleshooting
    df = df.dropna(subset=["median_household_income"])
    df["median_household_income"] = df["median_household_income"].round(0)
    df = add_quartile(df, "median_household_income", "income_quartile")
    return df.sort_values("median_household_income").reset_index(drop=True)

# Use Claude Opus 5.5 to troubleshoot duplicate data when creating charts for streamlit
def prepare_cases(data: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the /data rows
    """
    df = data.drop_duplicates(subset=["service_request_id"],
                              keep="last").copy()
    for column in ["hours_to_close", "lat", "lng", "precipitation",
                   "temperature_2m"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["hours_to_close"])
    df["service_category"] = df["service_category"].fillna("Unknown")

    df["weather"] = "Unknown"
    df.loc[df["precipitation"] < RAINY_DAY_MM, "weather"] = "Dry"
    df.loc[df["precipitation"] >= RAINY_DAY_MM, "weather"] = "Rainy"

    return df.merge(summary[["neighborhood", "income_quartile"]],
                    on="neighborhood", how="inner")


# Summaries for charts
def summarize_resolution(df: pd.DataFrame,
                         group_column: str,
                         top_n: int | None = None,
                         sort_by_value: bool = False) -> dict:
    """
    Median service time from 311
    """
    if df.empty:
        return {}
    medians = df.groupby(group_column, observed=True)["hours_to_close"]\
        .median().round(1)
    if sort_by_value:
        medians = medians.sort_values(ascending=False)
    if top_n is not None:
        medians = medians.head(top_n)
    return medians.to_dict()

# Asked Claude Opus 5.5 how to sort by quartile to return a df for streamlit
def resolution_by_quartile_and_weather(df: pd.DataFrame) -> pd.DataFrame:
    """
    Median service time with income quartiles vs income levels ad weather
    """
    known = df[df["weather"] != "Unknown"]
    if known.empty:
        return pd.DataFrame()
    return known.pivot_table(index="income_quartile", columns="weather",
                             values="hours_to_close", aggfunc="median",
                             observed=True).round(1)

# Asked Claude Opus 5.5 how to display neighborhood table in streamlit
def neighborhood_table(df: pd.DataFrame,
                       summary: pd.DataFrame) -> pd.DataFrame:
    """
    Neighbohoods sorted by income and population from /summary with
    median service hours from 311 Data
    """
    if df.empty:
        return pd.DataFrame()
    hours = df.groupby("neighborhood", as_index=False).agg(
        cases=("service_request_id", "count"),
        median_hours=("hours_to_close", "median"),
        avg_hours=("hours_to_close", "mean"))
    table = summary[["neighborhood", "income_quartile",
                     "median_household_income", "total_population"]]\
        .merge(hours, on="neighborhood", how="inner")
    table["cases_per_1k_people"] = (table["cases"] * 1000 /
                                    table["total_population"]).round(1)
    table = table.round({"median_hours": 1, "avg_hours": 1})
    return table.sort_values("median_household_income")\
        .reset_index(drop=True)


def ordered_chart_data(summary: dict, value_name: str) -> pd.DataFrame:
    """
    Dict for bar charts
    """
    return pd.DataFrame(
        {value_name: list(summary.values())},
        index=pd.CategoricalIndex(list(summary.keys()),
                                  categories=list(summary.keys()),
                                  ordered=True))


# Asked Claude Opus 5.5 how to display a map with quartile overlays for streamlit
# Income per neighborhood and median service time quartile maps
def retrieve_neighborhood_shapes() -> dict:
    """SF neighborhood outlines."""
    response = requests.get(NEIGHBORHOOD_GEOJSON_URL,
                            timeout=60)
    response.raise_for_status()
    return response.json()

# Asked Claude Opus 5.5 how to display a map with quartile overlays for streamlit
def quartile_geojson(shapes: dict, 
                     table: pd.DataFrame,
                     value_column: str,
                     quartile_column: str) -> dict:
    """
    Copy each neighborhood shape that has data in table, adding its
    quartile, value and fill color as properties.
    """
    table = add_quartile(table, value_column, quartile_column)
    labels = list(table[quartile_column].cat.categories)
    lookup = table.set_index("neighborhood")
    features = []
    for feature in shapes["features"]:
        name = feature["properties"]["nhood"]
        if name not in lookup.index:
            continue
        quartile = lookup.loc[name, quartile_column]
        color = QUARTILE_COLORS[labels.index(quartile)]
        features.append({
            "type": "Feature",
            "geometry": feature["geometry"],
            "properties": {"nhood": name,
                           "quartile": quartile,
                           "value": round(float(lookup.loc[name,
                                                           value_column]), 1),
                           "color": color}})
    return {"type": "FeatureCollection", "features": features}

# Asked Claude Opus 5.5 how to display a map with quartile overlays for streamlit
def quartile_map(geojson: dict, value_label: str) -> pdk.Deck: 
    """Neighborhood map by """
    layer = pdk.Layer("GeoJsonLayer", geojson,
                      filled=True, stroked=True, pickable=True,
                      get_fill_color="properties.color",
                      get_line_color=[90, 90, 90],
                      line_width_min_pixels=1)
    view = pdk.ViewState(latitude=37.76, longitude=-122.44, zoom=11.3)
    return pdk.Deck(layers=[layer], initial_view_state=view,
                    tooltip={"text": "{nhood}\n{quartile}  " +
                             value_label + ": {value}"})
