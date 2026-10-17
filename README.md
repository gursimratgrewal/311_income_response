# Does the speed of 311 Service Response in San Francisco varies by neighborhood Income level of the area.
**Team Members**
|  Name        |  GithubID       |    Task                |
|--------------|-----------------|------------------------|
| Yunfan       | 399441537       |  contract, docker, Cloud Scheduler job with deployment instructions|
| Gursimrat    | gursimratgrewal |  github repo, README.md, complete code for fetching <file> and one API file data source, Cloud Run services  |
| Eric         | E_Smith_359     | gcp project and bucket, dashboard with graph/chart, Cloud Run services|
| Vansh        | VanshS29362     | draft code fetching api/file data source, complete code fetching <api> data source, Cloud Run services|
| Prashasti    | Prashasti9      | define data structure, code receive and parse/transform data, store into gcp, define functions used by dashboard, Cloud Run services|


----------------------------------------------------------------------------------------------------------
**Problem Statement**
 
We combine San Francisco 311 service request data, American Community Survey data, and Open-Meteo to check whether resolving speed varies on neighborhood median household income and population. Because single dataset cannot show relationship between service request patterns and socioeconomic characteristics, it requires joining geographic and demographic data from multiple sources, while weather conditions are also a important factor affecting resolving time. We will compare response times with major request categories, and weather conditions as additional factors, then visualize the results on neighborhood map. The findings could be useful for municipal government and residents to understand if municipal services are performed consistently across communities in San Francisco.

-------------------------------------------------------------------------------------------------------------

**Data Sources**

| Name | URL| Acquisition method | Data | Access requirements|
|------|----|--------------------|------|--------------------|
| 311 Cases, DataSF | https://data.sfgov.org/City-Infrastructure/311-Cases/vw6y-z8j6 | API | SF311 cases with time and location since 2008 | No requirements
| Analysis Neighborhoods – 2020 census tracts assigned to neighborhoods, DataSF | https://data.sfgov.org/d/sevw-6tgi | File (CSV download) | Maps each SF 2020 census tract (GEOID) to one of 41 Analysis Neighborhoods | No requirements |
| American Community Survey 5-Year Data | https://www.census.gov/data/developers/data-sets/acs-5year.html | API | we only need the Household Income and Total Population and location related data from this source | API key needed, free to register, has ToS |
| Historical Forecast API, Open-Meteo | https://open-meteo.com/en/docs/historical-forecast-api | API | time, location and weather condition | no more than 10,000 daily API calls, no other requirements |

-------------------------------------------------------------------------------------------------------------

**Integration Goal**

When we look at all these different datasets, we can see if the service response differs across income levels taking into consideration other factors like type of request, size of the population and weather of the area.Combining these sources allows us to analyze whether service response times vary across income levels while considering request type, population, and weather, which cannot be observed from single dataset.
For each 311 case we calculate the hours to close. Income and population are joined to the tract to neighborhood file on the tract GEOID, then averaged income and summed population per neighborhood. 311 cases are joined to that table on neighborhood. Weather is summarized per day and joined to 311 cases by date.

-------------------------------------------------------------------------

**Setup Instructions (Locally)**

1. Clone the repository 
```bash
   git clone https://github.com/gursimratgrewal/311_income_response.git
   cd 311_income_response
```
   


2. Create and activate virtual environment
```bash
   python -m venv .venv
   source .venv/bin/activate
```

3. Install requirements
```bash
  pip install -r api/requirements.txt
```

4. Create and set up environment variables.
   
  Create your GCP service account key by following these instructions:-
  
  GCP Console → IAM & Admin → Service Accounts → choose the account → Keys → Add key → Create new key → JSON

  Save .json outside the repo folder and never commit. 
  
  Create your .env file from the template and fill in your own values
  ```bash
  cp .env_template .env
  ```
```
  GCP_PROJECT_ID=your gcp project id
  GCP_BUCKET_NAME=your gcp bucket name
  GCP_SERVICE_ACCOUNT_KEY=path/to/your-service-account-key.json
  CENSUS_API_KEY=your-census-api-key
  API_SERVICE_URL=http://127.0.0.1:8000
```


5. Run the project
```bash
 cd api
 fastapi dev main.py
```
Open http://127.0.0.1:8000/docs to see all routes.

6. Fetch the raw data
  - GET `/fetch/sf311`
  - GET `/fetch/weather`
  - GET `/fetch/acs`
  - GET `/fetch/neighborhoods`

7. Clean raw data
  - GET `/parse/sf311`
  - GET `/parse/weather`
  - GET `/parse/acs`
  - GET `/parse/neighborhoods`

8. Join all the things
 - POST `/process` saves `processed/joined.csv` and `processed/summary.csv` to the bucket
 - GET `/data` and GET `/summary` return them as JSON  

9. Run the dashboard in new terminal
    
 ```bash
cd streamlit
pip install -r requirements.txt
streamlit run streamlit_app.py
```
Open http://localhost:8501

**Deploy to GCP**

1. Log in and make sure your `.env` is filled in, including the key path:
```bash
gcloud auth login
```
2. Run the deploy script from the repo root:
```bash
bash gcloud_command.sh
```
It will:-
- store the service account key in Secret Manager
- deploy the API (`sf311-api-server`), one fetch and one parse service per source (`sf311-fetch-<source>`, `sf311-parse-<source>`), and the dashboard (`sf311-webapp`) to Cloud Run
- create Cloud Scheduler jobs: fetch at 1:00 AM, parse at 2:00 AM, process at 3:00 AM daily


   


**Repository Structure**


```
311_income_response/
├── api/
│   ├── collectors/
│   │   ├── acs.py               # Collects Census ACS income and population (API fetch)
│   │   ├── helper.py            # Shared helper functions for the collectors
│   │   ├── neighborhoods.py     # Downloads the SF census tract to neighborhood CSV file (File based acquisition)
│   │   ├── sf311.py             # Fetches SF 311 cases for a date range (API fetch)
│   │   └── weather.py           # Fetches hourly SF weather from Open-Meteo (API fetch)
│   ├── data_types.py            # Pydantic data types for every source
│   ├── Dockerfile               # Container setup for the API service
│   ├── main.py                  # FastAPI app with all the routes
│   ├── requirements.txt         # Python dependencies for the API
│   ├── storage.py               # GCS connection, upload and download
│   ├── transform.py             # Cleans and joins 311, Census, weather and neighborhood files, stores result in GCS
│   └── user_definition.py       # Settings: env variables, source URLs, column maps and constants
├── streamlit/
│   ├── Dockerfile               # Container setup for the dashboard
│   ├── helper.py                # Helper functions for the dashboard (data loading, quartiles, maps)
│   ├── requirements.txt         # Python dependencies for the dashboard
│   ├── streamlit_app.py         # Streamlit dashboard app
│   └── user_definition.py       # Dashboard settings: API URL, map and chart constants
├── .env_template                # Template for environment variables (copy to .env)
├── .gitignore                   # Files Git should ignore
├── config.sh                    # Deploy settings: region, ports, service names, schedules (reads .env)
├── gcloud_command.sh            # Deploys all Cloud Run services and Cloud Scheduler jobs
└── README.md                    # Project documentation
```

















