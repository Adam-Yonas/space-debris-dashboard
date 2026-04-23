import json
import sqlite3
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "data" / "space_debris.db"

EARTH_RADIUS_KM = 6378.137

def mean_motion_to_altitude_km(mean_motion_rev_per_day: float) -> float:
    """
    Approximate orbital altitude from mean motion using Kepler's third law.
    Assumes near-circular orbit.
    """
    mu = 398600.4418  # km^3/s^2
    n = mean_motion_rev_per_day * 2 * 3.141592653589793 / 86400.0  # rad/s
    a = (mu / (n ** 2)) ** (1 / 3)  # semi-major axis in km
    altitude = a - EARTH_RADIUS_KM
    return altitude

def main() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        raw_rows = conn.execute("SELECT payload_json FROM raw_objects").fetchall()

    objects = [json.loads(row["payload_json"]) for row in raw_rows]

    bins = defaultdict(int)

    for obj in objects:
        mean_motion = obj.get("MEAN_MOTION")
        if mean_motion is None:
            continue

        try:
            altitude = mean_motion_to_altitude_km(float(mean_motion))
            bin_km = int(altitude // 50) * 50   # 50 km bins
            bins[bin_km] += 1
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    results = [
        {"altitude_bin_km": k, "count": v}
        for k, v in sorted(bins.items())
    ]

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS altitude_bins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                altitude_bin_km REAL NOT NULL,
                count INTEGER NOT NULL
            )
            """
        )
        conn.execute("DELETE FROM altitude_bins")
        conn.executemany(
            "INSERT INTO altitude_bins (altitude_bin_km, count) VALUES (?, ?)",
            [(row["altitude_bin_km"], row["count"]) for row in results],
        )
        conn.commit()

    print(f"Processed {len(objects)} objects")
    print(f"Saved altitude bins to {DB_FILE} (table: altitude_bins)")

if __name__ == "__main__":
    main()