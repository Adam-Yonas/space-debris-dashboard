import json
import math
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "space_debris.db"

app = FastAPI(title="Space Debris Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrbitAssessmentRequest(BaseModel):
    altitude_km: float = Field(..., ge=160, le=40000)
    inclination_deg: float = Field(..., ge=0, le=180)
    eccentricity: float = Field(0.0, ge=0, le=0.2)
    mission_years: float = Field(1.0, gt=0, le=20)
    raan_deg: float = Field(0.0, ge=0, le=360)


class AIOrbitPlanRequest(BaseModel):
    mission_goal: str = Field(..., min_length=5, max_length=1000)
    altitude_km: float = Field(..., ge=160, le=40000)
    inclination_deg: float = Field(..., ge=0, le=180)
    eccentricity: float = Field(0.0, ge=0, le=0.2)
    mission_years: float = Field(1.0, gt=0, le=20)
    raan_deg: float = Field(0.0, ge=0, le=360)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def db_available() -> bool:
    return DB_FILE.exists()


def gaussian_weight(delta: float, sigma: float) -> float:
    return math.exp(-0.5 * (delta / sigma) ** 2)


def angular_difference_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return 360 - diff if diff > 180 else diff


def synthetic_orbital_regimes() -> list[dict]:
    objects = []

    for i in range(525):
        objects.append(
            {
                "object_name": f"SYNTHETIC PAYLOAD {i + 1}",
                "altitude_km": 400 + (i % 9) * 70,
                "inclination_deg": 50 + (i % 7) * 7,
                "eccentricity": 0.001 + (i % 5) * 0.0005,
                "raan_deg": (i * 11) % 360,
            }
        )

    for i in range(1111):
        objects.append(
            {
                "object_name": f"SYNTHETIC DEBRIS {i + 1}",
                "altitude_km": 500 + (i % 12) * 55,
                "inclination_deg": 45 + (i % 10) * 5,
                "eccentricity": 0.001 + (i % 8) * 0.0007,
                "raan_deg": (i * 17) % 360,
            }
        )

    for i in range(10):
        objects.append(
            {
                "object_name": f"SYNTHETIC ROCKET BODY {i + 1}",
                "altitude_km": 650 + (i % 5) * 90,
                "inclination_deg": 53 + (i % 4) * 8,
                "eccentricity": 0.002,
                "raan_deg": (i * 31) % 360,
            }
        )

    return objects


def fetch_all_orbital_regimes() -> list[dict]:
    if not db_available():
        return synthetic_orbital_regimes()

    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                """
                SELECT object_name, altitude_km, inclination_deg, eccentricity, raan_deg
                FROM orbital_regimes
                """
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return synthetic_orbital_regimes()


def fetch_orbital_regimes(limit: int) -> list[dict]:
    return fetch_all_orbital_regimes()[:limit]


def compute_orbit_risk(
    orbital_regimes: list[dict],
    altitude_km: float,
    inclination_deg: float,
    eccentricity: float,
    raan_deg: float,
    mission_years: float,
) -> dict:
    sigma_altitude_km = 75
    sigma_inclination_deg = 5
    sigma_eccentricity = 0.01
    sigma_raan_deg = 20

    weighted_risk = 0.0
    close_matches = 0

    for obj in orbital_regimes:
        obj_altitude = float(obj.get("altitude_km", 0.0))
        obj_inclination = float(obj.get("inclination_deg", 0.0))
        obj_eccentricity = float(obj.get("eccentricity", 0.0))
        obj_raan = float(obj.get("raan_deg", 0.0))

        altitude_delta = altitude_km - obj_altitude
        inclination_delta = inclination_deg - obj_inclination
        eccentricity_delta = eccentricity - obj_eccentricity
        raan_delta = angular_difference_deg(raan_deg, obj_raan)

        altitude_weight = gaussian_weight(altitude_delta, sigma_altitude_km)
        inclination_weight = gaussian_weight(inclination_delta, sigma_inclination_deg)
        eccentricity_weight = gaussian_weight(eccentricity_delta, sigma_eccentricity)
        raan_weight = gaussian_weight(raan_delta, sigma_raan_deg)

        combined_weight = (
            altitude_weight
            * inclination_weight
            * eccentricity_weight
            * raan_weight
        )

        weighted_risk += combined_weight

        if (
            abs(altitude_delta) <= 50
            and abs(inclination_delta) <= 3
            and abs(eccentricity_delta) <= 0.005
            and raan_delta <= 15
        ):
            close_matches += 1

    duration_factor = max(0.25, math.sqrt(mission_years))
    weighted_risk *= duration_factor

    max_reference = max(10, len(orbital_regimes) * 0.02)
    risk_score = min(100, round((weighted_risk / max_reference) * 100))

    if risk_score <= 30:
        risk_level = "Low"
    elif risk_score <= 70:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "weighted_risk": round(weighted_risk, 4),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "close_matches": close_matches,
        "duration_factor": round(duration_factor, 3),
    }


def get_recommendation(
    orbital_regimes: list[dict],
    altitude_km: float,
    inclination_deg: float,
    eccentricity: float,
    raan_deg: float,
    mission_years: float,
    current_score: int,
) -> str:
    candidate_offsets = [-150, -100, -50, 50, 100, 150]
    best_option: Optional[dict] = None

    for offset in candidate_offsets:
        candidate_altitude = altitude_km + offset
        if candidate_altitude <= 160:
            continue

        result = compute_orbit_risk(
            orbital_regimes,
            candidate_altitude,
            inclination_deg,
            eccentricity,
            raan_deg,
            mission_years,
        )

        score = result["risk_score"]

        if score < current_score:
            if best_option is None or score < best_option["score"]:
                best_option = {
                    "altitude_km": round(candidate_altitude, 1),
                    "score": score,
                    "risk_level": result["risk_level"],
                }

    if best_option is None:
        return (
            "No clearly better nearby altitude band was found with the current "
            "simplified model."
        )

    return (
        f"A nearby lower-risk option is approximately "
        f"{best_option['altitude_km']} km at the same inclination and eccentricity."
    )


def evaluate_orbit(
    orbital_regimes: list[dict],
    altitude_km: float,
    inclination_deg: float,
    eccentricity: float,
    raan_deg: float,
    mission_years: float,
) -> dict:
    risk_result = compute_orbit_risk(
        orbital_regimes=orbital_regimes,
        altitude_km=altitude_km,
        inclination_deg=inclination_deg,
        eccentricity=eccentricity,
        raan_deg=raan_deg,
        mission_years=mission_years,
    )

    recommendation = get_recommendation(
        orbital_regimes=orbital_regimes,
        altitude_km=altitude_km,
        inclination_deg=inclination_deg,
        eccentricity=eccentricity,
        raan_deg=raan_deg,
        mission_years=mission_years,
        current_score=risk_result["risk_score"],
    )

    return {
        "result": risk_result,
        "recommendation": recommendation,
    }


def build_candidate_orbits(
    altitude_km: float,
    inclination_deg: float,
    eccentricity: float,
    raan_deg: float,
    mission_years: float,
) -> list[dict]:
    raw_candidates = [
        {
            "altitude_km": altitude_km,
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
        {
            "altitude_km": max(160, altitude_km - 50),
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
        {
            "altitude_km": altitude_km + 50,
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
        {
            "altitude_km": max(160, altitude_km - 100),
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
        {
            "altitude_km": altitude_km + 100,
            "inclination_deg": inclination_deg,
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
        {
            "altitude_km": altitude_km,
            "inclination_deg": max(0, inclination_deg - 2),
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
        {
            "altitude_km": altitude_km,
            "inclination_deg": min(180, inclination_deg + 2),
            "eccentricity": eccentricity,
            "raan_deg": raan_deg,
            "mission_years": mission_years,
        },
    ]

    seen = set()
    unique_candidates = []

    for candidate in raw_candidates:
        key = (
            round(candidate["altitude_km"], 3),
            round(candidate["inclination_deg"], 3),
            round(candidate["eccentricity"], 6),
            round(candidate["raan_deg"], 3),
            round(candidate["mission_years"], 3),
        )

        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    return unique_candidates


def score_candidate_for_goal(candidate: dict, result: dict, mission_goal: str) -> float:
    goal = mission_goal.lower()
    score = float(result["risk_score"])

    altitude = float(candidate["orbit"]["altitude_km"])
    inclination = float(candidate["orbit"]["inclination_deg"])

    if "under 650" in goal and altitude > 650:
        score += 20
    if "under 600" in goal and altitude > 600:
        score += 20
    if "under 550" in goal and altitude > 550:
        score += 20

    if "long mission" in goal or "5-year" in goal or "10-year" in goal:
        if altitude < 400:
            score += 10

    if "earth observation" in goal or "polar" in goal:
        if inclination < 80:
            score += 15

    if "low altitude" in goal and altitude > 700:
        score += 10

    if "safer" in goal or "low risk" in goal or "lower-risk" in goal:
        score -= 5

    return score


def generate_local_ai_summary(
    mission_goal: str,
    current_orbit: dict,
    current_assessment: dict,
    best_candidate: Optional[dict],
) -> str:
    current_result = current_assessment["result"]
    current_score = current_result["risk_score"]
    current_level = current_result["risk_level"]
    current_matches = current_result["close_matches"]

    goal_text = mission_goal.strip()
    goal = goal_text.lower()

    if best_candidate is None:
        return (
            f"For the mission goal '{goal_text}', the current orbit is assessed as "
            f"{current_level.lower()} risk with a score of {current_score}/100 and "
            f"{current_matches} nearby tracked-object matches. No clearly better nearby "
            f"candidate was identified in this local search, so the current orbit may "
            f"already be near the best available option within this simplified model. "
            f"A good next step would be testing a wider altitude or inclination range."
        )

    candidate_orbit = best_candidate["orbit"]
    candidate_result = best_candidate["result"]

    candidate_score = candidate_result["risk_score"]
    candidate_level = candidate_result["risk_level"]
    delta = current_score - candidate_score

    if delta >= 20:
        improvement_text = "a strong reduction in modeled debris risk"
    elif delta >= 10:
        improvement_text = "a meaningful reduction in modeled debris risk"
    elif delta > 0:
        improvement_text = "a modest reduction in modeled debris risk"
    else:
        improvement_text = "roughly similar modeled risk"

    caution_text = (
        "this recommendation only reflects the debris-risk model and does not include "
        "coverage, drag, propulsion, or regulatory constraints"
    )

    if candidate_orbit["altitude_km"] < current_orbit["altitude_km"]:
        caution_text = (
            "the lower altitude could reduce modeled debris exposure but may increase "
            "drag and station-keeping needs"
        )
    elif candidate_orbit["altitude_km"] > current_orbit["altitude_km"]:
        caution_text = (
            "the higher altitude may improve local modeled risk, but it may affect "
            "mission lifetime and operational tradeoffs differently"
        )
    elif abs(candidate_orbit["inclination_deg"] - current_orbit["inclination_deg"]) >= 1.5:
        caution_text = (
            "the inclination change may affect ground coverage and mission geometry"
        )

    goal_notes = []

    if "under 650" in goal:
        goal_notes.append("it stays within the requested altitude limit")
    if "under 600" in goal:
        goal_notes.append("it stays within the tighter altitude ceiling")
    if "earth observation" in goal or "polar" in goal:
        goal_notes.append("it better matches high-inclination observation-style orbits")
    if "long mission" in goal or "5-year" in goal or "10-year" in goal:
        goal_notes.append("it avoids pushing too low in altitude for a longer mission")

    goal_reason = ""
    if goal_notes:
        goal_reason = " It is preferred because " + ", and ".join(goal_notes) + "."

    return (
        f"For the mission goal '{goal_text}', the current orbit is assessed as "
        f"{current_level.lower()} risk with a score of {current_score}/100 and "
        f"{current_matches} nearby tracked-object matches. The best nearby option from "
        f"this search is approximately {candidate_orbit['altitude_km']} km altitude, "
        f"{candidate_orbit['inclination_deg']}° inclination, eccentricity "
        f"{candidate_orbit['eccentricity']}, and RAAN {candidate_orbit['raan_deg']}°. "
        f"That candidate scores {candidate_score}/100 ({candidate_level.lower()} risk), "
        f"which suggests {improvement_text}.{goal_reason} The main caution is that {caution_text}."
    )


def generate_synthetic_orbit_track(index: int) -> dict:
    altitude = 400 + (index % 20) * 35
    inclination_rad = math.radians(35 + (index % 10) * 6)
    radius = 6371 + altitude

    x_values = []
    y_values = []
    z_values = []

    for step in range(120):
        theta = 2 * math.pi * step / 119
        x = radius * math.cos(theta)
        y = radius * math.sin(theta) * math.cos(inclination_rad)
        z = radius * math.sin(theta) * math.sin(inclination_rad)

        x_values.append(round(x, 2))
        y_values.append(round(y, 2))
        z_values.append(round(z, 2))

    return {
        "object_name": f"SYNTHETIC OBJECT {index + 1}",
        "altitude_km": altitude,
        "inclination_deg": round(math.degrees(inclination_rad), 2),
        "x": x_values,
        "y": y_values,
        "z": z_values,
    }


@app.get("/")
def root():
    return {"message": "Space Debris Dashboard API running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/altitude-bins")
def get_altitude_bins():
    if db_available():
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT altitude_bin_km, count
                    FROM altitude_bins
                    ORDER BY altitude_bin_km
                    """
                ).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            pass

    objects = fetch_all_orbital_regimes()
    bins = {}

    for obj in objects:
        altitude = float(obj.get("altitude_km", 0.0))
        bin_key = int(altitude // 100) * 100
        bins[bin_key] = bins.get(bin_key, 0) + 1

    return [
        {"altitude_bin_km": altitude_bin, "count": count}
        for altitude_bin, count in sorted(bins.items())
    ]


@app.get("/orbital-regimes")
def get_orbital_regimes(limit: int = 500):
    return fetch_orbital_regimes(limit)


@app.get("/orbit-tracks")
def get_orbit_tracks(limit: int = 40):
    if db_available():
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT object_name, altitude_km, inclination_deg, x_json, y_json, z_json
                    FROM orbit_tracks
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [
                {
                    "object_name": row["object_name"],
                    "altitude_km": row["altitude_km"],
                    "inclination_deg": row["inclination_deg"],
                    "x": json.loads(row["x_json"]),
                    "y": json.loads(row["y_json"]),
                    "z": json.loads(row["z_json"]),
                }
                for row in rows
            ]
        except Exception:
            pass

    return [generate_synthetic_orbit_track(i) for i in range(limit)]


@app.post("/assess-orbit")
def assess_orbit(payload: OrbitAssessmentRequest):
    orbital_regimes = fetch_all_orbital_regimes()

    assessment = evaluate_orbit(
        orbital_regimes=orbital_regimes,
        altitude_km=payload.altitude_km,
        inclination_deg=payload.inclination_deg,
        eccentricity=payload.eccentricity,
        raan_deg=payload.raan_deg,
        mission_years=payload.mission_years,
    )

    return {
        "input": payload.model_dump(),
        "result": assessment["result"],
        "recommendation": assessment["recommendation"],
    }


@app.post("/ai-orbit-plan")
def ai_orbit_plan(payload: AIOrbitPlanRequest):
    orbital_regimes = fetch_all_orbital_regimes()

    current_orbit = payload.model_dump()

    current_assessment = evaluate_orbit(
        orbital_regimes=orbital_regimes,
        altitude_km=payload.altitude_km,
        inclination_deg=payload.inclination_deg,
        eccentricity=payload.eccentricity,
        raan_deg=payload.raan_deg,
        mission_years=payload.mission_years,
    )

    candidates = build_candidate_orbits(
        altitude_km=payload.altitude_km,
        inclination_deg=payload.inclination_deg,
        eccentricity=payload.eccentricity,
        raan_deg=payload.raan_deg,
        mission_years=payload.mission_years,
    )

    candidate_assessments = []

    for candidate in candidates:
        assessment = evaluate_orbit(
            orbital_regimes=orbital_regimes,
            altitude_km=candidate["altitude_km"],
            inclination_deg=candidate["inclination_deg"],
            eccentricity=candidate["eccentricity"],
            raan_deg=candidate["raan_deg"],
            mission_years=candidate["mission_years"],
        )

        candidate_assessments.append(
            {
                "orbit": candidate,
                "result": assessment["result"],
                "recommendation": assessment["recommendation"],
            }
        )

    best_candidate = None
    best_adjusted_score = float("inf")

    for candidate in candidate_assessments:
        adjusted_score = score_candidate_for_goal(
            candidate=candidate,
            result=candidate["result"],
            mission_goal=payload.mission_goal,
        )

        if adjusted_score < best_adjusted_score:
            best_adjusted_score = adjusted_score
            best_candidate = candidate

    if best_candidate is not None:
        current_score = current_assessment["result"]["risk_score"]
        best_raw_score = best_candidate["result"]["risk_score"]

        if best_raw_score >= current_score:
            best_candidate = None

    ai_summary = generate_local_ai_summary(
        mission_goal=payload.mission_goal,
        current_orbit=current_orbit,
        current_assessment=current_assessment,
        best_candidate=best_candidate,
    )

    return {
        "current_orbit": current_orbit,
        "current_assessment": current_assessment,
        "candidate_assessments": candidate_assessments,
        "best_candidate": best_candidate,
        "ai_summary": ai_summary,
        "planner_type": "local-rule-based",
    }
