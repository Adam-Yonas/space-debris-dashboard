import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "data" / "space_debris.db"

EARTH_RADIUS_KM = 6378.137


def mean_motion_to_altitude_km(mean_motion_rev_per_day: float) -> float:
    mu = 398600.4418  # km^3/s^2
    n = mean_motion_rev_per_day * 2 * 3.141592653589793 / 86400.0  # rad/s
    a = (mu / (n ** 2)) ** (1 / 3)  # km
    return a - EARTH_RADIUS_KM


def main() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        raw_rows = conn.execute("SELECT payload_json FROM raw_objects").fetchall()
    objects = [json.loads(row["payload_json"]) for row in raw_rows]

    processed = []

    for obj in objects:
        mean_motion = obj.get("MEAN_MOTION")
        inclination = obj.get("INCLINATION")
        eccentricity = obj.get("ECCENTRICITY", 0)
        raan = obj.get("RA_OF_ASC_NODE", 0)
        object_name = obj.get("OBJECT_NAME", "Unknown")

        if mean_motion is None or inclination is None:
            continue

        try:
            altitude_km = mean_motion_to_altitude_km(float(mean_motion))
            inclination_deg = float(inclination)
            eccentricity_value = float(eccentricity)
            raan_deg = float(raan)

            processed.append(
                {
                    "object_name": object_name,
                    "altitude_km": round(altitude_km, 3),
                    "inclination_deg": round(inclination_deg, 3),
                    "eccentricity": round(eccentricity_value, 6),
                    "raan_deg": round(raan_deg, 3),
                }
            )
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orbital_regimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_name TEXT NOT NULL,
                altitude_km REAL NOT NULL,
                inclination_deg REAL NOT NULL,
                eccentricity REAL NOT NULL DEFAULT 0.0,
                raan_deg REAL NOT NULL DEFAULT 0.0
            )
            """
        )
        conn.execute("DELETE FROM orbital_regimes")
        conn.executemany(
            """
            INSERT INTO orbital_regimes (
                object_name, altitude_km, inclination_deg, eccentricity, raan_deg
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    row["object_name"],
                    row["altitude_km"],
                    row["inclination_deg"],
                    row["eccentricity"],
                    row["raan_deg"],
                )
                for row in processed
            ],
        )
        conn.commit()

    print(f"Processed {len(processed)} orbital regime records")
    print(f"Saved to: {DB_FILE} (table: orbital_regimes)")


if __name__ == "__main__":
    main()