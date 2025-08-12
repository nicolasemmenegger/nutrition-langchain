import sys
import os
# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from app.config import settings

# This file just confirms foods.csv is present; in a richer setup we'd import to a DB table.
if __name__ == "__main__":
    df = pd.read_csv(settings.foods_csv)
    print("Loaded foods:", len(df), "rows from", settings.foods_csv)
    print(df.head())
