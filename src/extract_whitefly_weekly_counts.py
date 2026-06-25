# LOAD REQUIRED LIBRARIES
from pathlib import Path
import requests
from urllib.parse import urlparse, urljoin
import pandas as pd
import re
import time

# CONSTANTS AND FOLDER PATHS
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
LOG_DIR = PROJECT_ROOT / "outputs" / "extraction_logs"

METADATA_FILE_PATH = INTERIM_DATA_DIR / "trap_metadata.csv"
EXTRACTED_COUNT_FILE_PATH = INTERIM_DATA_DIR / "stopwhitefly_weekly_counts.csv"
MERGED_DATASET_PATH = PROCESSED_DATA_DIR / "stopwhitefly_trap_weekly_counts_with_metadata.csv"
SUCCESS_LOG_PATH = LOG_DIR / "stopwhitefly_extraction_log.csv"
FAILURE_LOG_PATH = LOG_DIR / "stopwhitefly_extraction_failures.csv"

METADATA_MAP_SOURCE_URL = (
    "https://maps.eddmaps.org/point/trap/relativecatch/index.cfm?"
    "sub=10378&proj=1441&project=1441&lat=31.35&lng=-83.60&zoom=10.5"
    "&map=136&shownodata=1&maxzoom=12&circlemarker&expiredata=14"
    )

"""
WEEKLY_CHART_BASE = (
        "https://maps.eddmaps.org/line/sitedatabyyear/"
       f"?aggregate=sum&sub=10378&project=1441&proj=1441&site={site_id}&showdate"
)
"""

WEEKLY_CHART_BASE_URL = "https://maps.eddmaps.org/line/sitedatabyyear/"
AGGREGATE = "sum"
SUB_ID = "10378"
PROJECT_ID = "1441"
PROJ_ID = "1441"
SHOWDATE_VALUE = "showdate"


REQUEST_TIMEOUT = 20 # seconds
REQUEST_DELAY = 1 # seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

RAW_METADATA_COLUMNS = [
    "SITEID", "SITENAME", "LAT", "LON", "STATUS", "FIRSTREPORT", "LASTREPORT"
]

EXPECTED_METADATA_COLUMNS = [
    "site_id", "trap_label", "latitude", "longitude", "status", "first_report", 
    "last_report"
]

DATA_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

print("Project Root Folder:", PROJECT_ROOT.resolve())
print("\nMetadata file path:", METADATA_FILE_PATH.resolve())
print("\nWeekly count file path:", EXTRACTED_COUNT_FILE_PATH.resolve())
print("\nMerged dataset file path:", MERGED_DATASET_PATH.resolve())
print("\nSuccessful data extraction log file:", SUCCESS_LOG_PATH.resolve())
print("\nFailed data extraction log file:", FAILURE_LOG_PATH.resolve())

################################################################################
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ METADATA TABLE EXTRACTION ~~~~~~~~~~~~~~~~~~~~~ #
################################################################################

map_source_keywords = [
    "data.cfc", "relativecatch", "loadClustering"
]

def extract_metadata_table(url):
    print("Extracting metadata table for trap sites:")

    response_map_source = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response_map_source.raise_for_status()

    status_code_map_source_url = response_map_source.status_code
    print("Map source URL response status code:", status_code_map_source_url)

    print("Map source URL content-type:", response_map_source.headers.get("Content-Type"))

    map_source_response_html_length = len(response_map_source.text)
    print("Length of map source response HTML:", map_source_response_html_length)

    if map_source_response_html_length == 0:
        raise ValueError("Map source HTML response was empty.")

    print("Are Keywords present?")
    for keyword in map_source_keywords:
        print(f"{keyword}:", keyword in response_map_source.text)

    pattern = r'"(data\.cfc[^"]+)"'
    match = re.search(pattern, response_map_source.text)

    print("Found AJAX endpoint:", match is not None)

    if match is None:
        raise ValueError("Could not find metadata AJAX endpoint in map source HTML.")

    print("Matched AJAX relative endpoint:", match.group(1))

    parsed = urlparse(url)
    query_string = parsed.query
    print("Original iframe query string:", query_string)

    metadata_ajax_url = urljoin(
        url,
        match.group(1) + query_string
    )

    print("AJAX URL for metadata:", metadata_ajax_url)

    response_ajax_metadata_url = requests.get(
        metadata_ajax_url, headers=HEADERS, timeout=REQUEST_TIMEOUT
        )
    response_ajax_metadata_url.raise_for_status()

    status_code_ajax_metadata_url = response_ajax_metadata_url.status_code
    print("Status code of metadata AJAX URL:", status_code_ajax_metadata_url)

    ajax_metadata_response_html_length = len(response_ajax_metadata_url.text)

    if ajax_metadata_response_html_length == 0:
        raise ValueError("Metadata AJAX response was empty.")

    try:
        metadata_parsed_json = response_ajax_metadata_url.json()
    except Exception as e:
        print(f"The AJAX metadata response cannot be parsed as JSON: {e}")
        print("Raw response snippet:", metadata_parsed_json.text[:300])
        raise

    required_json_keys = {"records", "columns", "count"}
    missing_json_keys = required_json_keys - set(metadata_parsed_json)

    if missing_json_keys:
        raise ValueError(f"Metadata JSON missing required keys: {missing_json_keys}")

    print("Metadata JSON Keys:", metadata_parsed_json.keys())
    print("\nMetadata JSON keys has 'columns':", "columns" in metadata_parsed_json.keys())
    print("\nMetadata JSON keys has 'records':", "records" in metadata_parsed_json.keys())
    print("\nMetadata JSON keys has 'count':", "count" in metadata_parsed_json.keys())

    print("\nMetadata Columns:", metadata_parsed_json["columns"])

    if len(metadata_parsed_json["records"]) == 0:
        raise ValueError("Metadata JSON contains zero records.")

    print("\nMetadata first record:")
    print(metadata_parsed_json["records"][0])

    return metadata_parsed_json


################################################################################
# ~~~~~~~~~~~~~~~~~~~~~~~ METADATA TABLE CLEANING ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
################################################################################

def clean_metadata_table(metadata_json):
    # build raw dataframe from JSON results
    df = pd.DataFrame(
        metadata_json["records"],
        columns=metadata_json["columns"]
    )

    # validate if required raw columns exist
    missing_required_columns = set(RAW_METADATA_COLUMNS) - set(df.columns)

    if missing_required_columns:
        raise ValueError(f"Required raw metadata columns are missing: {missing_required_columns}")

    # filter the raw dataframe for required raw columns only
    df_filtered = df[RAW_METADATA_COLUMNS].copy()

    # rename columns
    df_cleaned = df_filtered.rename(
        columns = {
            "SITEID": "site_id",
            "SITENAME": "trap_label",
            "LAT": "latitude",
            "LON": "longitude",
            "STATUS": "status",
            "FIRSTREPORT": "first_report",
            "LASTREPORT": "last_report",
        }
    )

    # explicitly set the data types for columns
    df_cleaned["first_report"] = pd.to_datetime(df_cleaned["first_report"], errors="coerce")
    df_cleaned["last_report"] = pd.to_datetime(df_cleaned["last_report"], errors="coerce")
    df_cleaned["latitude"] = pd.to_numeric(df_cleaned["latitude"], errors="coerce")
    df_cleaned["longitude"] = pd.to_numeric(df_cleaned["longitude"], errors="coerce")
    df_cleaned["site_id"] = pd.to_numeric(df_cleaned["site_id"], errors="coerce")

    # validate for missing values in critical columns
    critical_metadata_columns = ["site_id", "latitude", "longitude"]
    print("Missing values in the columns:", df_cleaned[critical_metadata_columns].isna().sum())

    for col in critical_metadata_columns:
        if df_cleaned[col].isna().any():
            raise ValueError(f"Metadata contains missing {col} values.")

    # convert numeric columns to integer and floats after verifying there is no missing values
    df_cleaned["site_id"] = df_cleaned["site_id"].astype(int)
    df_cleaned["latitude"] = df_cleaned["latitude"].astype(float)
    df_cleaned["longitude"] = df_cleaned["longitude"].astype(float)

    # Validate site ID uniqueness
    if df_cleaned["site_id"].duplicated().any():
        duplicated_site_ids = df_cleaned.loc[
            df_cleaned["site_id"].duplicated(), "site_id"
        ].tolist()
        raise ValueError(f"Metadata contains duplicated site_id values: {duplicated_site_ids}")

    # Summary of cleaned metadata table
    print("Shape of Metadata table:", df_cleaned.shape)
    print("Number of unique site IDs:", df_cleaned["site_id"].nunique())
    print("Status counts:")
    print(df_cleaned["status"].value_counts(dropna=False))
    print("First 5 rows:", df_cleaned.head())
    
    return df_cleaned 


################################################################################
# ~~~~~~~~~~~~~~~~~~~~~~~~~~ SAVE CLEANED METADATA TABLE ~~~~~~~~~~~~~~~~~~~~~ #
################################################################################

def save_cleaned_metadata(df, output_path):
    # create the parent directories if not created earlier
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # save as csv file
    df.to_csv(output_path, index = False)

    # print output file full path
    print("Metadata has been saved to the file:", output_path.resolve())

    # smoke test to verify if saved file can be read properly
    metadata_saved_df = pd.read_csv(output_path)

    # verify if the shape matches
    if metadata_saved_df.shape != df.shape:
        raise ValueError(
            f"Saved metadata shape mis-match. "
            f"Original: {df.shape}, Saved: {metadata_saved_df.shape}"
        )

    print("First 5 rows of saved CSV file:")
    print(metadata_saved_df.head())


################################################################################
# ~~~~~~~~~~~~~~~~~~~~ WEEKLY WHITEFLY TRAP COUNT EXTRACTION ~~~~~~~~~~~~~~~~~ #
################################################################################

def extract_weekly_whitefly_counts(
        site_id, base_url, aggregate, sub_id, project_id, 
        proj_id, showdate_value,
        verbose=True,
        ):
    
    # build the weekly chart URL
    weekly_chart_url = (
        f"{base_url}?aggregate={aggregate}&sub={sub_id}&project={project_id}"
        f"&proj={proj_id}&site={site_id}&{showdate_value}"
    )

    # request a response and check its status
    response = requests.get(weekly_chart_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    if verbose:
        print("Response Checks:")
        print("Status Code:", response.status_code)
        print("Content-Type:", response.headers.get("Content-Type"))
        print("Response Length:", len(response.text))

    # verify response is not empty
    if len(response.text) == 0:
        raise ValueError(f"Weekly chart HTML response was empty for site_id={site_id}")

    # Find the data.cfm AJAX endpoint inside chart HTML
    pattern = r'url:\s*"(data\.cfm[^"]+)"'
    matched_ajax_url = re.search(pattern, response.text)

    if verbose:
        print("Found AJAX URL endpoint:", matched_ajax_url is not None)

    # verify match is not empty
    if matched_ajax_url is None:
        raise ValueError(f"Could not find weekly AJAX endpoint for site_id={site_id}")

    if verbose:
        print("Matched AJAX relative endpoint:", matched_ajax_url.group(1))

    # build the AJAX Endpoint URL
    ajax_url_endpoint = urljoin(
        weekly_chart_url, matched_ajax_url.group(1)
    )

    if verbose:
        print(f"URL for weekly count data for site '{site_id}':", ajax_url_endpoint)

    # request from AJAX endpoint and check for its status
    response_ajax_endpoint = requests.get(ajax_url_endpoint, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response_ajax_endpoint.raise_for_status()

    if verbose:
        print("AJAX endpoint response checks:")
        print("Status Code:", response_ajax_endpoint.status_code)
        print("Content-Type:", response_ajax_endpoint.headers.get("Content-Type"))
        print("Response Length:", len(response_ajax_endpoint.text))

    # verify AJAX endpoint response is not empty
    if len(response_ajax_endpoint.text) == 0:
        raise ValueError(f"Weekly AJAX response was empty for site_id={site_id}")

    # get the JSON response
    weekly_count_data_json = response_ajax_endpoint.json()

    # ensures JSON response is a list
    if not isinstance(weekly_count_data_json, list):
        raise ValueError(f"Weekly count JSON was not a list for site_id={site_id}")

    # verify JSON response is not empty
    if len(weekly_count_data_json) == 0:
        raise ValueError(f"Weekly count JSON contains zero year-series for site_id={site_id}")

    # build the weekly count data frame from the JSON response
    rows = []
    for series in weekly_count_data_json:
        # check if required keys are present in the series
        if "id" not in series or "values" not in series:
            raise ValueError(f"Weekly series missing required keys for site_id={site_id}: {series.keys()}")
        
        series_year = series["id"]

        for record in series["values"]:
            # check if the required keys are present in the record
            if "label" not in record or "value" not in record:
                raise ValueError(f"Point record missing label/value for site_id={site_id}: {record}")
            
            plotted_date = record["label"]
            date_collected = series_year + "-" + plotted_date[5:]
            count = record["value"]

            row = {
                "site_id": site_id,
                "year": series_year,
                "plotted_date": plotted_date,
                "date_collected": date_collected,
                "whitefly_count": count
                }

            rows.append(row)

    weekly_whitefly_count_df = pd.DataFrame(rows)

    # check for zero rows after flattening
    if weekly_whitefly_count_df.empty:
        raise ValueError(f"Weekly count dataframe is empty for site_id={site_id}")

    # explicitly set output column data types
    weekly_whitefly_count_df["site_id"] = weekly_whitefly_count_df["site_id"].astype(int)
    weekly_whitefly_count_df["year"] = weekly_whitefly_count_df["year"].astype(int)
    weekly_whitefly_count_df["plotted_date"] = pd.to_datetime(
        weekly_whitefly_count_df["plotted_date"], errors="coerce"
        )
    weekly_whitefly_count_df["date_collected"] = pd.to_datetime(
        weekly_whitefly_count_df["date_collected"], errors="coerce"
        )
    weekly_whitefly_count_df["whitefly_count"] = pd.to_numeric(
        weekly_whitefly_count_df["whitefly_count"], errors="coerce"
        )

    if verbose:
        print("Summary of weekly count data extraction:")
        print("Shape:", weekly_whitefly_count_df.shape)
        print("Rows by year:", weekly_whitefly_count_df.groupby("year").size())

    return weekly_whitefly_count_df 



################################################################################
# ~~~~~~~~~~ WHITEFLY WEEKLY COUNT DATA EXTRACTION FROM ALL SITES ~~~~~~~~~~~~ #
################################################################################

def extract_whitefly_counts_for_all_sites(metadata_df):
    print("Extracting weekly whitefly counts for all the sites.")

    # extract site IDs from the metadata df
    site_ids = metadata_df["site_id"].tolist()

    dataframes = []
    success_log = []
    failure_log = []

    # Loop over site IDs to extract weekly counts
    for site_id in site_ids:
        try:
            print(f"Extracting data for the site_id={site_id}")
            weekly_whitefly_count_df = extract_weekly_whitefly_counts(
                site_id=site_id,
                base_url=WEEKLY_CHART_BASE_URL,
                aggregate=AGGREGATE,
                sub_id=SUB_ID,
                project_id=PROJECT_ID,
                proj_id=PROJ_ID,
                showdate_value=SHOWDATE_VALUE,
                verbose=False
            )

            dataframes.append(weekly_whitefly_count_df)

            success_log.append(
                {
                    "site_id": site_id,
                    "status": "success",
                    "n_rows": len(weekly_whitefly_count_df),
                    "first_date": weekly_whitefly_count_df["date_collected"].min(),
                    "last_date": weekly_whitefly_count_df["date_collected"].max(),
                }
            )

        except Exception as e:
            failure_log.append({
                "site_id": site_id,
                "status": "failed",
                "error_message": str(e)
            })

        # Give a short delay between the requests
        time.sleep(REQUEST_DELAY)

    if not dataframes:
        raise ValueError("No weekly count dataframes were successfully extracted.")

    # All sites data frame for weekly whitefly counts
    all_weekly_df = pd.concat(dataframes, ignore_index=True)

    success_log_df = pd.DataFrame(success_log)

    failure_log_df = pd.DataFrame(failure_log)

    # Validate uniqueness of rows
    if all_weekly_df.duplicated(subset=["site_id", "date_collected"], keep=False).any():
        print("There are duplicated rows in the data frame:")
        print(
            all_weekly_df.loc[
                all_weekly_df.duplicated(subset=["site_id", "date_collected"], keep=False),
                ["site_id", "date_collected"]
                ]
            )
        raise ValueError("Duplicate site_id x date_collected rows found in weekly dataset.")

    print("Summary:")
    print("Shape:", all_weekly_df.shape)
    print("Number of unique sites:", all_weekly_df["site_id"].nunique())
    print("Number of missing rows:")
    print(all_weekly_df.isna().sum())

    print("First 5 weekly count rows:")
    print(all_weekly_df.head())

    print("Success Log:")
    print(success_log_df.head())

    print("Failure Log:")
    print(failure_log_df.head())

    return all_weekly_df, success_log_df, failure_log_df



################################################################################
# ~~~~~~~~ SAVE ALL SITES WEEKLY DATA FRAME, SUCCESS LOG, FAILURE LOG ~~~~~~~~ #
################################################################################

def save_all_sites_extraction_data_and_logs(
        all_weekly_df, weekly_data_file_path, 
        success_log_df, success_log_file_path, 
        failure_log_df, failure_log_file_path
        ):
    
    weekly_data_file_path.parent.mkdir(parents=True, exist_ok=True)
    success_log_file_path.parent.mkdir(parents=True, exist_ok=True)
    failure_log_file_path.parent.mkdir(parents=True, exist_ok=True)

    if failure_log_df.empty:
        failure_log_df = pd.DataFrame(
            columns=["site_id", "status", "error_message"]
        )

    all_weekly_df.to_csv(weekly_data_file_path, index=False)
    success_log_df.to_csv(success_log_file_path, index=False)
    failure_log_df.to_csv(failure_log_file_path, index=False)

    # Read each file back as a smoke test
    all_weekly_df = pd.read_csv(weekly_data_file_path)
    print("First 5 rows of saved weekly count data frame:")
    print(all_weekly_df.head())
    print("Shape:", all_weekly_df.shape)

    success_log_df = pd.read_csv(success_log_file_path)
    print("First 5 rows of saved success log data frame:")
    print(success_log_df.head())
    print("Shape:", success_log_df.shape)

    failure_log_df = pd.read_csv(failure_log_file_path)
    print("First 5 rows of saved failure log data frame:")
    print(failure_log_df.head())
    print("Shape:", failure_log_df.shape)



################################################################################
# ~~~~~~~~~~~~ MERGE WEEKLY COUNT DATA WITH SITE METADATA AND SAVE ~~~~~~~~~~~ #
################################################################################

def merge_whitefly_count_with_site_metadata(
        whitefly_count_df, metadata_df, merged_data_file_path):

    # ensure parent directories are created
    merged_data_file_path.parent.mkdir(parents=True, exist_ok=True)

    # merge count data with site metadata
    merged_df = whitefly_count_df.merge(
        metadata_df,
        on=["site_id"],
        how="left"
    )

    print("Shape of weekly count df:", whitefly_count_df.shape)
    print("Shape of merged df:", merged_df.shape)

    # ensure merged df has same number of rows to that of whitefly count df
    if merged_df.shape[0] != whitefly_count_df.shape[0]:
        raise ValueError("There is shape mismatch between merged df and whitefly count df.")

    print("Column-wise total missing values in the merged df:")
    print(merged_df.isna().sum())

    # save merged dataset as CSV file
    merged_df.to_csv(merged_data_file_path, index=False)

    # smoke test for the saved dataset
    saved_merged_df = pd.read_csv(merged_data_file_path)

    print("Merged dataset is saved at:", merged_data_file_path.resolve())
    print("First 5 rows:")
    print(saved_merged_df.head())

    return merged_df


################################################################################
# ~~~~~~~~~~~~~~~~ MAIN FUNCTION TO ORCHESTRATE THE WORKFLOW ~~~~~~~~~~~~~~~~~ #
################################################################################

def main():
    print("Starting StopWhitefly weekly count extraction workflow.\n")

    # Extract metadata JSON
    metadata_json = extract_metadata_table(url=METADATA_MAP_SOURCE_URL)

    # 1). create a cleaned metadata df from JSON outputs
    cleaned_metadata_df = clean_metadata_table(metadata_json=metadata_json)

    # 2). save cleaned metadata file
    save_cleaned_metadata(df=cleaned_metadata_df, output_path=METADATA_FILE_PATH)

    # 3). extract weekly whitefly counts for all sites
    all_weekly_df, success_log_df, failure_log_df = extract_whitefly_counts_for_all_sites(
        metadata_df=cleaned_metadata_df)

    # 4). save whitefly count data, success log, and failure log
    save_all_sites_extraction_data_and_logs(
        all_weekly_df=all_weekly_df, 
        weekly_data_file_path=EXTRACTED_COUNT_FILE_PATH, 
        success_log_df=success_log_df, 
        success_log_file_path=SUCCESS_LOG_PATH, 
        failure_log_df=failure_log_df, 
        failure_log_file_path=FAILURE_LOG_PATH
        )

    # 5). Merge the weekly whitefly count data with site metadata and save
    merged_df = merge_whitefly_count_with_site_metadata(
        whitefly_count_df=all_weekly_df, 
        metadata_df=cleaned_metadata_df, 
        merged_data_file_path=MERGED_DATASET_PATH
        )

    print("Summary:")
    print("Shape of cleaned metadata df:", cleaned_metadata_df.shape)
    print("Metadata df is saved at:", METADATA_FILE_PATH.resolve())
    print("Shape of all sites weekly whitefly counts df:", all_weekly_df.shape)
    print("Whitefly count df is saved at:", EXTRACTED_COUNT_FILE_PATH.resolve())
    print("Successful site extractions:", len(success_log_df))
    print("Failed site extractions:", len(failure_log_df))
    print("Shape of final merged df:", merged_df.shape)
    print("Final merged dataset is saved at:", MERGED_DATASET_PATH.resolve())

    print("\nStopWhitefly extraction workflow completed successfully.")

    
if __name__ == "__main__":
    main()







