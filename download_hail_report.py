import os
import pandas as pd
from datetime import datetime
import requests
import io

# Adjusting import paths for modular structure
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import HAIL_DATA_URL, HAIL_REPORTS_DIR, STATES
from utils import setup_logging, ensure_dir_exists

logger = setup_logging()

def download_hail_report():
    """
    Downloads the daily hail report from the NOAA website, filters it for 
    specific states, and saves it if it doesn't already exist.

    Returns:
        str: The file path of the downloaded or existing hail report.
    """
    ensure_dir_exists(HAIL_REPORTS_DIR, logger)

    today_str = datetime.today().strftime("%Y-%m-%d")
    filepath = os.path.join(HAIL_REPORTS_DIR, f"{today_str}.csv")

    if not os.path.exists(filepath):
        logger.info(f"Downloading hail report from: {HAIL_DATA_URL}")
        try:
            response = requests.get(HAIL_DATA_URL)
            response.raise_for_status()  # Raise an exception for bad status codes

            # 1. Read the raw CSV text into a pandas DataFrame
            df = pd.read_csv(io.StringIO(response.text))

            # 2. Filter based on the keys in your STATES config (e.g., 'MO', 'KS')
            allowed_states = list(STATES.keys())
            
            # NOAA reports usually use 'State' or 'St' as the column header
            if 'State' in df.columns:
                df_filtered = df[df['State'].isin(allowed_states)]
            elif 'St' in df.columns:
                df_filtered = df[df['St'].isin(allowed_states)]
            else:
                # Fallback if column names change unexpectedly
                logger.warning("Could not find 'State' column. Saving all data.")
                df_filtered = df

            # 3. Save the filtered DataFrame to CSV
            df_filtered.to_csv(filepath, index=False)
            
            logger.info(f"Saved filtered hail report ({len(df_filtered)} rows) to: {filepath}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download hail report: {e}")
            raise
        except pd.errors.ParserError as e:
            logger.error(f"Failed to parse CSV data: {e}")
            raise
    else:
        logger.info(f"Using existing hail report: {filepath}")

    return filepath