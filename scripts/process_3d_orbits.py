import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = PROJECT_ROOT / "data" / "raw_data.json"
OUTPUT_FILE = PROJECT_ROOT / "data" / "orbit_tracks.json"

EARTH_RADIUS_KM = 6378.137
MU = 398600.4418  # km^3/s^2


def mean_motion_to_semi_major_axis_km(mean_motion_rev_per_day: float) -> float:
    n = mean_motion_rev_per_day * 2 * math.pi / 86400.0  # rad/s
    return (MU / (n ** 2)) ** (1 / 3)


def rotation_matrix(raan, inc, argp):
    cos_O = math.cos(raan)
    sin_O = math.sin(raan)
    cos_i = math.cos(inc)
    sin_i = math.sin(inc)
    cos_w = math.cos(argp)
    sin_w = math.sin(argp)

    # Perifocal -> ECI
    return [
        [
            cos_O * cos_w - sin_O * sin_w * cos_i,
            -cos_O * sin_w - sin_O * cos_w * cos_i,
            sin_O * sin_i,
        ],
        [
            sin_O * cos_w + cos_O * sin_w * cos_i,
            -sin_O * sin_w + cos_O * cos_w * cos_i,
            -cos_O * sin_i,
        ],
        [
            sin_w * sin_i,
            cos_w * sin_i,
            cos_i,
        ],
    ]


def mat_vec_mul(m, v):
    return [
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ]


def build_orbit_track(obj, num_points=96):
    try:
        mean_motion = float(obj["MEAN_MOTION"])
        inc_deg = float(obj["INCLINATION"])
        raan_deg = float(obj.get("RA_OF_ASC_NODE", 0.0))
        argp_deg = float(obj.get("ARG_OF_PERICENTER", 0.0))
        mean_anomaly_deg = float(obj.get("MEAN_ANOMALY", 0.0))
        eccentricity = float(obj.get("ECCENTRICITY", 0.0))
    except (KeyError, TypeError, ValueError):
        return None

    # Clamp to keep this visualization stable
    if mean_motion <= 0:
        return None
    if eccentricity < 0 or eccentricity >= 0.2:
        eccentricity = 0.0  # keep it simple for now

    a = mean_motion_to_semi_major_axis_km(mean_motion)

    inc = math.radians(inc_deg)
    raan = math.radians(raan_deg)
    argp = math.radians(argp_deg)
    mean_anomaly = math.radians(mean_anomaly_deg)

    rot = rotation_matrix(raan, inc, argp)

    xs, ys, zs = [], [], []

    for k in range(num_points):
        # Approximate true anomaly by uniform sweep
        nu = 2 * math.pi * k / num_points + mean_anomaly

        r = a * (1 - eccentricity ** 2) / (1 + eccentricity * math.cos(nu))

        # Position in perifocal frame
        r_pf = [r * math.cos(nu), r * math.sin(nu), 0.0]

        # Rotate into ECI frame
        r_eci = mat_vec_mul(rot, r_pf)

        xs.append(round(r_eci[0], 3))
        ys.append(round(r_eci[1], 3))
        zs.append(round(r_eci[2], 3))

    return {
        "object_name": obj.get("OBJECT_NAME", "Unknown"),
        "altitude_km": round(a - EARTH_RADIUS_KM, 3),
        "inclination_deg": inc_deg,
        "x": xs,
        "y": ys,
        "z": zs,
    }


def main():
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        raw_objects = json.load(f)

    tracks = []

    # Keep this lightweight for browser performance
    for obj in raw_objects[:150]:
        track = build_orbit_track(obj)
        if track is not None:
            tracks.append(track)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tracks, f, indent=2)

    print(f"Saved {len(tracks)} orbit tracks to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()