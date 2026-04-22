import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = PROJECT_ROOT / "data" / "raw_data.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "altitude_bins.json"

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
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        objects = json.load(f)

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

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Processed {len(objects)} objects")
    print(f"Saved altitude bins to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()