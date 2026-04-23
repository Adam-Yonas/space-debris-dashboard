import json
import os
import sqlite3
from pathlib import Path

import requests

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_FILE = DATA_DIR / "space_debris.db"

# Use a smaller group first so you can prove the pipeline works
URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json"

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(URL, timeout=30)
        print("Status Code:", response.status_code)

        if response.status_code == 200:
            data = response.json()
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS raw_objects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute("DELETE FROM raw_objects")
                conn.executemany(
                    "INSERT INTO raw_objects (payload_json) VALUES (?)",
                    [(json.dumps(response_object),) for response_object in data],
                )
                conn.commit()

            print(f"Downloaded {len(data)} objects")
            print(f"Saved to: {DB_FILE} (table: raw_objects)")

        else:
            print("Request failed.")
            print(response.text)

    except requests.RequestException as e:
        print("Network error:", e)
    except ValueError as e:
        print("JSON parse error:", e)
    except Exception as e:
        print("Unexpected error:", e)

if __name__ == "__main__":
    main()