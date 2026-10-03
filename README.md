# Does the speed of 311 Service Response in San Francisco varies by Census Tract Income level of the area.
**Team Members**
|  Name        |  GithubID       |    Task                |
|--------------|-----------------|------------------------|
| Yunfan       | 399441537       |  PDF contract and documentation.Configure reusable image, create Cloud Scheduler job for AB which collect data regularly, with deployment instructions|
| Gursimrat    | gursimratgrewal |  Git setup and readme. Fetch <file> data source, provide to C with defined data type, build and deploy Cloud Run services  |
| Eric         | E_Smith_359     | GCP setup and git branches. Create web service, display data with dashboard, build and deploy Cloud Run services|
| Vansh        | VanshS29362     | Python: Fetch API and data. Fetch <api> data source, provide to C with defined data type, build and deploy Cloud Run services|
| Prashasti    | Prashasti9      | Python: Parse and store into GCP. Define public data type, receive and clean/transform, store into gcp, define functions used by dashboard, build and deploy Cloud Run services|


----------------------------------------------------------------------------------------------------------
**Problem Statement**
 
We combine San Francisco 311 service request data, American Community Survey data, and Open-Meteo to check whether resolving speed varies on neighborhood median household income and population. Because single dataset cannot show relationship between service request patterns and socioeconomic characteristics, it requires joining geographic and demographic data from multiple sources, while weather conditions are also a important factor affecting resolving time. We will compare response times with major request categories, and weather conditions as additional factors, then visualize the results on neighborhood map. The findings could be useful for municipal government and residents to understand if municipal services are performed consistently across communities in San Francisco.

-------------------------------------------------------------------------------------------------------------

**Data Sources**

| Name | URL| Acquisition method | Data | Access requirements|
|------|----|--------------------|------|--------------------|
| 311 Cases, DataSF | https://data.sf.gov/City-Infrastructure/311-Cases/vw6y-z8j6/about_data | File | SF311 cases with time and location since 2008 | No requirements
| American Community Survey 5-Year Data | https://www.census.gov/data/developers/data-sets/acs-5year.html | API | we only need the Household Income and Total Population and location related data from this source | API key needed, free to register, has ToS |
| Historical Forecast API, Open-Meteo | https://open-meteo.com/en/docs/historical-forecast-api | API | time, location and weather condition | no more than 10,000 daily API calls, no other requirements |

-------------------------------------------------------------------------------------------------------------

**Integration Goal**

When we look at all these different datasets, we can see if the service response differs across income levels taking into consideration other factors like type of request, size of the population and weather of the area.Combining these sources allows us to analyze whether service response times vary across income levels while considering request type, population, and weather, which cannot be observed from single dataset.
We will join 311 latitude and longitude to Census tracts, then use the tract GEOID to join ACS income and population data. Weather data will be joined by date time and lat lon.

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
  pip install -r requirements.txt
```

4. Create a .env file in the project root and add required variables.

  Create .env file from the template and fill in your own values
  ```bash
  cp .env_template.env
  ```
```
  STORAGE_BACKEND=gcs
  GCS_BUCKET_NAME=gcsbucketname
  GOOGLE_APPLICATION_CREDENTIALS=path/to/your-service-account-key.json
  LOCAL_OUTPUT_DIR=./data
  RAW_PREFIX=raw
  HTTP_TIMEOUT_SECONDS=120
   

```

5. Run the project
```bash
 fastapi dev main.py
```


**Repository Structure**

```
311_income_response/
├── .env_template      
├── .gitignore         
├── main.py            
├── process_sf311.py  
├── requirements.txt   
└── README.md          
```
















