import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_SERVER_URL = os.getenv("API_SERVICE_URL")

# Claude Opus 5.5 suggestion to create variables after asking how to
# map income and weather quartiles to a map of SF
TOP_CATEGORIES = 10      # service categories shown as sidebar checkboxes
MAP_HEIGHT = 550         # pixel height of each neighborhood map

RAINY_DAY_MM = 1.0 # Used Claude recommendation for a "light rain" in mm
NEIGHBORHOOD_GEOJSON_URL = "https://data.sfgov.org/resource/j2bu-swwd.geojson" 
QUARTILE_COLORS = [[239, 243, 255, 190],   # Q1 (lightest)
                   [189, 215, 231, 190],
                   [107, 174, 214, 190],
                   [33, 113, 181, 190]]    # Q4 (darkest)
