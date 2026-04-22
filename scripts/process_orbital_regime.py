import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = PROJECT_ROOT / "data" / "raw_data.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "orbital_regimes.json"

EARTH_RADIUS_KM = 6378.137


def mean_motion_to_altitude_km(mean_motion_rev_per_day: float) -> float:
    mu = 398600.4418  # km^3/s^2
    n = mean_motion_rev_per_day * 2 * 3.141592653589793 / 86400.0  # rad/s
    a = (mu / (n ** 2)) ** (1 / 3)  # km
    return a - EARTH_RADIUS_KM


def main() -> None:
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        objects = json.load(f)

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

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2)

    print(f"Processed {len(processed)} orbital regime records")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()