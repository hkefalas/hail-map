import pandas as pd
from config import HAIL_REPORTS_DIR
from datetime import datetime
import os

# Load today's report
today_str = datetime.today().strftime("%Y-%m-%d")
filepath = os.path.join(HAIL_REPORTS_DIR, f"{today_str}.csv")

if os.path.exists(filepath):
    df = pd.read_csv(filepath)
    print("Columns:", df.columns.tolist())
    print("First row:", df.iloc[0].to_dict())
else:
    print("File not found.")
    