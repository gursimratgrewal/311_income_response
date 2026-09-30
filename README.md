# Does the speed of 311 Service Response in San Francisco varies by Census Tract Income level of the area.
**Team Members**
|  Name        |    Task                |
|--------------|------------------------|
| Yunfan       |  PDF contract and documentation|
| Gursimrat    |  Git setup and readme  |
| Eric | GCP setup and git branches|
| Vansh | Python: Fetch API and data|
| Prashasti | Python: Parse and store into GCP|


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

** Integration Goal **

When we look at all these different datasets, we can see if the service response differs across income levels taking into consideration other factors like type of request, size of the population and weather of the area. 











