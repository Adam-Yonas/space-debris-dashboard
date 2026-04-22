import json
import os
from pathlib import Path

import requests

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "raw_data.json"

# Use a smaller group first so you can prove the pipeline works
URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=json"

def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(URL, timeout=30)
        print("Status Code:", response.status_code)

        if response.status_code == 200:
            data = response.json()

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"Downloaded {len(data)} objects")
            print(f"Saved to: {OUTPUT_FILE}")

        else:
            print("Request failed.")
            print(response.text)

    except requests.RequestException as e:
        print("Network error:", e)
    except json.JSONDecodeError as e:
        print("JSON parse error:", e)
    except Exception as e:
        print("Unexpected error:", e)

if __name__ == "__main__":
    main()