# Description about TFL_Notebook.py

The TFL_Notebook.py file is build to download the latest line status of the tube running under TFL. 
The data is fetched from TFL Open API https://api.tfl.gov.uk/Line/Mode/tube/Status and stored in sql tables using databricks notebooks functionality.

The code manages the data flow from source to staging followed by bronze and silver layer enriching the data quality as it moves across the different layers.
Finally the data is loaded into silver.tubestatus table where major columns like current_timestamp, line, status, disruption_reason are available for further analysis.


The API documentation for source data is available in following link:
https://api-portal.tfl.gov.uk/api-details#api=Line&operation=Line_StatusByModeByPathModesQueryDetailQuerySeverityLevel

Following is the request parameters details for the source data API being used
![image](https://github.com/harshsohal/TFL_analysis/assets/174956070/2417085a-53ed-48d4-96ae-a77cbafdcc54)

