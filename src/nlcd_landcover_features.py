# Load required libraries
import pandas as pd
import geopandas as gpd
from pathlib import Path
import rasterio
from rasterio.mask import mask


# Define the paths and constants
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_NLCD_DIR = DATA_DIR / "raw" / "nlcd"

METADATA_PATH = DATA_DIR / "interim" / "trap_metadata.csv"
TRAP_COUNT_PATH = PROCESSED_DIR / "stopwhitefly_trap_weekly_counts_with_metadata.csv"

INTERIM_GEOSPATIAL_DIR = DATA_DIR / "interim" / "geospatial"
BUFFER_OUTPUT_PATH = INTERIM_GEOSPATIAL_DIR / "trap_buffers_500m_1km.gpkg"

PROCESSED_MERGED_FILE = PROCESSED_DIR / "stopwhitefly_trap_weekly_counts_with_nlcd_landcover.csv"
PROCESSED_NLCD_FEATURES = PROCESSED_DIR / "site_year_landcover_features_nlcd.csv"

PROJECTED_CRS = "EPSG:26917"

METADATA_REQ_COLS = [
    'site_id', 
    'latitude', 
    'longitude'
]

NLCD_CLASS_GROUPS = {
    "water": [11],
    "developed": [21, 22, 23, 24],
    "barren": [31],
    "forest": [41, 42, 43],
    "shrub_scrub": [52],
    "grassland_herbaceous": [71],
    "pasture_hay": [81],
    "cultivated_crops": [82],
    "wetlands": [90, 95],
}

EXPECTED_GROUPS = [
    "water",
    "developed",
    "barren",
    "forest",
    "shrub_scrub",
    "grassland_herbaceous",
    "pasture_hay",
    "cultivated_crops",
    "wetlands"
]

EXPECTED_RADII = [500, 1000]

EXPECTED_FEATURE_COLUMNS = [
    'water_fraction_500m',
    'developed_fraction_500m',
    'barren_fraction_500m',
    'forest_fraction_500m',
    'shrub_scrub_fraction_500m',
    'grassland_herbaceous_fraction_500m',
    'pasture_hay_fraction_500m',
    'cultivated_crops_fraction_500m',
    'wetlands_fraction_500m',
    'water_fraction_1000m',
    'developed_fraction_1000m',
    'barren_fraction_1000m',
    'forest_fraction_1000m',
    'shrub_scrub_fraction_1000m',
    'grassland_herbaceous_fraction_1000m',
    'pasture_hay_fraction_1000m',
    'cultivated_crops_fraction_1000m',
    'wetlands_fraction_1000m'
 ]




# Function 1:
def load_and_validate_trap_metadata(path: Path) -> pd.DataFrame:
    """
    Loads and validates the trap metadata
    
    Inputs:
        - Path to trap metadata CSV file

    Outputs:
        - Trap metadata pandas df
    """
    print("Starting Function 1: Loading and validating trap metadata")

    # Read the trap metadata and store as data frame
    metadata_df = pd.read_csv(path, dtype={"site_id": "string"})

    # Verify if the parsed dataset is empty
    if metadata_df.empty:
        raise ValueError("The parsed trap metadata df is empty.")

    # Verify all the three required columns are present
    missing_cols = []
    for col in METADATA_REQ_COLS:
        if col not in metadata_df.columns.tolist():
            missing_cols.append(col)

    if len(missing_cols) != 0:
        raise ValueError(f"There are missing required columns in the parsed metadata: {missing_cols}")

    # Strip blank spaces (if any) from each of the site IDs
    metadata_df["site_id"] = metadata_df["site_id"].str.strip()

    # Validate if there are blank spaces as site IDs
    blank_site_ids = metadata_df.loc[metadata_df["site_id"] == "", ]
    if blank_site_ids.shape[0] != 0:
        raise ValueError(f"There are {len(blank_site_ids)} blank site IDs. Row indexes: {blank_site_ids.index.tolist()}")

    # Verify if the site ID column has NULL values
    missing_sites = metadata_df.loc[metadata_df["site_id"].isna(), ]
    if missing_sites.shape[0] != 0:
        raise ValueError(f"The 'site_id' column has {len(missing_sites)} missing values. Row indexes: {missing_sites.index.tolist()}")

    # Verify if there are duplicate site IDs
    duplicated_sites = metadata_df["site_id"].duplicated()
    if duplicated_sites.any():
        dup_values = metadata_df.loc[duplicated_sites, "site_id"]
        raise ValueError(f"There are duplicated 'site_id' column values: {list(dup_values)}")

    # Verify if there are missing values in the Latitude column
    missing_latitude = metadata_df["latitude"].isna()
    if missing_latitude.any():
        raise ValueError(f"There are {missing_latitude.sum()} missing values in the 'latitude' column.")

    # Verify if there are missing values in the Longitude column
    missing_longitude = metadata_df["longitude"].isna()
    if missing_longitude.any():
        raise ValueError(f"There are {missing_longitude.sum()} missing values in the 'longitude' column.")

    # Verify if there are non-numeric values in the Latitude column
    # If not, then set the column dtype as float
    bad_latitude = pd.to_numeric(metadata_df["latitude"], errors="coerce").isna()
    if bad_latitude.any():
        bad_lat_rows = metadata_df.loc[bad_latitude, "latitude"]
        raise ValueError(f"There are non-numeric values in the column 'latitude': {bad_lat_rows.tolist()}")

    metadata_df["latitude"] = metadata_df["latitude"].astype("float")

    # Verify if there are non-numeric values in the Longitude column
    # If not, then set the column dtype as float
    bad_longitude = pd.to_numeric(metadata_df["longitude"], errors="coerce").isna()
    if bad_longitude.any():
        bad_lon_rows = metadata_df.loc[bad_longitude, "longitude"]
        raise ValueError(f"There are non-numeric values in the column 'longitude': {bad_lon_rows.tolist()}")

    metadata_df["longitude"] = metadata_df["longitude"].astype("float")

    # Verify if the Latitude values lie in the valid range
    if (metadata_df["latitude"].min() < -90) or (metadata_df["latitude"].max() > 90):
        raise ValueError("Latitude column has values outside the permissible bounds.")

    # Verify if the Longitude values lie in the valid range
    if (metadata_df["longitude"].min() < -180) or (metadata_df["longitude"].max() > 180):
        raise ValueError("Longitude column has values outside the permissible bounds.")

    return metadata_df





# Function 2:
def load_and_validate_weekly_trap_counts():
    """
    Loads and validates weekly whitefly trap counts

    Inputs:
        - Path to weekly trap counts CSV file

    Outputs:
        - Weekly whitefly counts pandas df
    """

# Function 3:
def create_projected_trap_points():
    """
    1. Builds the trap metadata geo df with geographic CRS
    2. Reprojects the geo df onto a meter-based CRS

    Inputs:
        - Trap metadata pandas df
        - Projected CRS

    Outputs:
        - Trap metadata GeoDataFrame with meter-based CRS
    """

# Function 4:
def build_validate_save_buffers():
    """
    1. Create 500m and 1km buffers around trap sites
    2. Validate if buffer counts equal to the trap site counts
    3. Validate every site_id has exactly one 500m and one 1000m buffer
    3. Combine the two buffer layers and validate the resulting df shape
    4. Save the buffer layers as GeoPackage for later use

    Inputs:
        - Trap metadata GeoDataFrame
        - List of buffer radii
        - OUTPUT PATH to save buffers

    Outputs:
        - Buffers GeoDataFrame
    """

# Function 5:
def discover_and_validate_nlcd_rasters():
    """
    Validate rasters- whether they are readable, number of layers, nodata values

    Inputs:
        - Path to raw NLCD directory
    
    Outputs:
        - Dictionary containing {landcover_year: raster_path}
    """

# Function 6:
def resolve_trap_years_to_nlcd_years():
    """
    Builds a year resolution df that maps trap years to their corresponding raster 
    years. For trap years that do not have corresponding raster years, fall back 
    to the most recent available raster year, not later than itself.

    Inputs:
        - weekly trap counts df
        - {landcover_year: raster_path} dictionary

    Outputs:
        - A pandas df with 'trap_year', 'landcover_year_used', and 'year_matched' columns
    """

# Function 7:
def extract_nlcd_class_counts():
    """
    Extract long-form NLCD class counts for required raster years by-
        - looping through each of the raster years in the year-resolution table
        - reproject buffers to each raster CRS
        - verify each buffer overlaps the raster
        - mask and count valid NLCD classes
        - reject unmapped classes and buffers with zero valid pixels                
    
    Inputs:
        - NLCD raster paths dictionary
        - year-resolution df
        - Validated buffers geo df
        - Dictionary mapping landcover class codes to the landcover classes

    Outputs:
        - A long class-count pandas dataframe with columns- 'site_id', 'trap_label', 
          'buffer_radius_m', 'landcover_year', 'landcover_code', 'pixel_count', 
          'total_valid_pixels'                                                                             
    """                                                             

# Function 8:
def aggregate_nlcd_class_codes_to_broad_classes():
    """
    1. Create a dataframe with total valid pixel counts for each (site x buffer x year)
    2. Create a dataframe with grouped pixel counts for each (site x buffer x year x landcover group)
    3. Merge the two dataframes
    4. Calculate NLCD landcover group fractions
    5. Create modeling-ready wide table
    6. Rename the columns
    7. Validate if any of the expected feature columns is missing
    8. Re-order the columns

    Inputs:
        - NLCD features df
        - List of expected NLCD feature columns

    Outputs:
        - A pivoted pandas df with NLCD features as columns
    """

# Function 9:
def build_and_validate_nlcd_feature_table():
    """
    1. Add the columns 'landcover_year_used', 'year_matched', and 'landcover_source'
    2. Re-arrange the columns

    Inputs:
        - The aggregated pandas df with NLCD features as columns
        - year-resolution df 
        - weekly whitefly trap counts df

    Outputs:
        - A pandas df with 18 NLCD features as columns along with additional 
        metadata columns like 'site_id', 'trap_label', 'trap_year', 
        'landcover_year_used', 'year_matched', and 'landcover_source'
    """

# Function 10:
def merge_landcover_features_with_weekly_whitefly_counts():
    """
    1. Left merge trap counts df with landcover feature table using (site_id x trap_year)
    2. Validate the merged table for missingness and duplication

    Inputs:
        - weekly whitefly counts df
        - landcover feature table
    
    Outputs:
        - A pandas df containing weekly whitefly counts along with NLCD features
    """

# Function 11:
def save_processed_outputs():
    """
    1. Saves the NLCD landcover feature table as CSV
    2. Saves the table containing weekly trap counts merged with NLCD features 

    Inputs:
        - NLCD landcover feature table      
        - Merged table containing weekly counts with NLCD features

    Output:
        - Path to the output NLCD feature table file
        - Path to the output merged table
    """

# Function 12:
def main():
    """
    Defines the main function to orchestrate the workflow
    """ 


if __name__ == "__main__":
    main()
