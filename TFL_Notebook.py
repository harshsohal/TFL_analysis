# Databricks notebook source
# MAGIC %md
# MAGIC ## This Notebook is designed to fetch the latest tube line results from the TFL Open API https://api.tfl.gov.uk/Line/Mode/tube/Status, the data is then stored in sql tables using databricks notebooks functionality.
# MAGIC ##The notebook uses delta table format and medallion framework enriching the data quality as data moves from one layer to the next.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Importing necessary libraries

# COMMAND ----------

import requests
import time
import datetime as dt
from pyspark.sql.types import ArrayType,MapType,StringType,StructType,StructField
from pyspark.sql.functions import lit,col,from_json,coalesce,explode,current_timestamp


# COMMAND ----------

# MAGIC %md
# MAGIC ## Source data API documentation link
# MAGIC
# MAGIC https://api-portal.tfl.gov.uk/api-details#api=Line&operation=Line_StatusByModeByPathModesQueryDetailQuerySeverityLevel

# COMMAND ----------

# MAGIC %md
# MAGIC ## Source data fetching using API

# COMMAND ----------

currentdatetime=dt.datetime.now().strftime("%Y%m%d_%H%M%S")
# print(currentdatetime)

dbutils.widgets.text("stagingDir", "/FileStore/TFL/staging")
dbutils.widgets.text("bronzeDir", "/FileStore/TFL/bronze")
dbutils.widgets.text("silverDir", "/FileStore/TFL/silver")
dbutils.widgets.text("archiveDir", "/FileStore/TFL/archive")
dbutils.widgets.text("API_noOfTries", "3")


url='https://api.tfl.gov.uk/line/mode/tube/status'   #Url to fetch status of tubes

stagingDir = dbutils.widgets.get('stagingDir')
bronzeDir = dbutils.widgets.get('bronzeDir')
silverDir = dbutils.widgets.get('silverDir')
archiveDir = dbutils.widgets.get('archiveDir')
API_noOfTries = dbutils.widgets.get('API_noOfTries')

noOfTries = int(API_noOfTries)
for count in range(noOfTries):
  try:
    response=requests.get(url)
    response.raise_for_status()

    if response != None and response.status_code == 200:
      print('Writing data to staging folder')
      dbutils.fs.put(stagingDir + f"/input_{currentdatetime}.json",response.text)
      print('Following file written in staging folder:', f"input_{currentdatetime}.json")
      break
  except Exception as e:
    print ('Problem accessing: {}' .format (url))
    print (e)
    if count == noOfTries-1:
      dbutils.notebook.exit(e)   # Exit the notebook with error message after given no of unsuccessful attempts
  time.sleep (10)  # wait for 10 seconds before retrying


# COMMAND ----------


# Define custom schema
schema = StructType([
      StructField("$type",StringType(),True),
      StructField("created",StringType(),True),
      StructField("crowding",StringType(),True),
      StructField("disruptions",StringType(),True),
      StructField("id",StringType(),True),
      StructField("lineStatuses",StringType(),True),
      StructField("modeName",StringType(),True),
      StructField("modified",StringType(),True),
      StructField("name",StringType(),True),
      StructField("routeSections",StringType(),True),
      StructField("serviceTypes",StringType(),True)
  ])


# Reading data into spark dataframe from staging file
df_input = spark.read.option("multiline","true").schema(schema).json(stagingDir + f"/input_{currentdatetime}.json")
df_input=df_input.withColumn('IsloadedtoSilver',lit('N')).withColumn('created_timestamp',lit(current_timestamp()))
df_input=df_input.withColumnRenamed('$type','type')  #renaming the column


# COMMAND ----------

# MAGIC %md
# MAGIC ## Creating delta tables in bronze and silver layer

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS bronze;
# MAGIC CREATE SCHEMA IF NOT EXISTS silver;
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS bronze.tubestatus (
# MAGIC   identity_key bigint GENERATED BY DEFAULT AS IDENTITY,
# MAGIC   `type` string,
# MAGIC   created string,
# MAGIC   crowding string,
# MAGIC   disruptions string,
# MAGIC   `id` string,
# MAGIC   lineStatuses string,
# MAGIC   modeName string,
# MAGIC   modified string,
# MAGIC   `name` string,
# MAGIC   routeSections string,
# MAGIC   serviceTypes string,
# MAGIC   IsloadedtoSilver string,
# MAGIC   created_timestamp timestamp
# MAGIC ) USING DELTA LOCATION '${bronzeDir}/tubestatus';
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS silver.tubestatus (
# MAGIC   identity_key bigint,
# MAGIC   `current_timestamp` timestamp,
# MAGIC   line string,
# MAGIC   statusSeverity int,
# MAGIC   statusSeverityDescription string,
# MAGIC   disruption_reason string,
# MAGIC   created_timestamp timestamp
# MAGIC ) USING DELTA LOCATION '${silverDir}/tubestatus';

# COMMAND ----------

# MAGIC %md
# MAGIC ## Loading data in bronze layer

# COMMAND ----------

df_input.write.format("delta").mode("append").saveAsTable("bronze.tubestatus")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Moving the staging input file to archive layer after loading to bronze is completed

# COMMAND ----------

dbutils.fs.mv(stagingDir + f"/input_{currentdatetime}.json", archiveDir + f"/input_{currentdatetime}.json")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reading data from bronze layer, formatting and cleansing followed by loading to silver layer

# COMMAND ----------

df_bronze=spark.read.table('bronze.tubestatus').filter("IsloadedtoSilver=='N'").select('identity_key','id','lineStatuses','IsloadedtoSilver','created_timestamp').withColumn('lineStatuses',from_json("lineStatuses",ArrayType(MapType(StringType(),StringType()))))
df_bronze=df_bronze.withColumn('lineStatuses_explode',explode('lineStatuses'))

df_silver=df_bronze.select('identity_key',col('created_timestamp').alias('current_timestamp'),coalesce('lineStatuses_explode.lineId','id').alias('line'),col('lineStatuses_explode.statusSeverity').cast('int').alias('statusSeverity'),'lineStatuses_explode.statusSeverityDescription',col('lineStatuses_explode.reason').alias('disruption_reason'),lit(current_timestamp()).alias('created_timestamp'))


# COMMAND ----------

# MAGIC %md
# MAGIC ## Loading data in silver layer

# COMMAND ----------

df_silver.write.format("delta").mode("append").saveAsTable("silver.tubestatus")

# COMMAND ----------

# MAGIC %md
# MAGIC updating IsloadedtoSilver flag in bronze layer table after load to silver layer is complete

# COMMAND ----------

spark.sql("UPDATE bronze.tubestatus set IsloadedtoSilver='Y' where IsloadedtoSilver='N';").show()

# COMMAND ----------

# MAGIC %sql
# MAGIC
# MAGIC select * from silver.tubestatus LIMIT 5;

# COMMAND ----------

dbutils.notebook.exit("The notebook is executed successfully")
