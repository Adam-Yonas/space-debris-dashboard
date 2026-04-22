import json
import math
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import os
DATA_DIR = Path(os.getcwd()) / "data"

ALTITUDE_BINS_FILE = DATA_DIR / "altitude_bins.json"
ORBITAL_REGIMES_FILE = DATA_DIR / "orbital_regimes.json"
ORBIT_TRACKS_FILE = DATA_DIR / "orbit_tracks.json"

app = FastAPI(title="Space Debris Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path):
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Missing data file: {path.name}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def gaussian_weight(delta: float, sigma: float) -> float:
    return math.exp(-0.5 * (delta / sigma) ** 2)


def angular_difference_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 360
    return 360 - diff if diff > 180 else diff


def compute_orbit_risk(
    orbital_regimes,
    altitude_km: float,
    inclination_deg: float,
    eccentricity: float,
    raan_deg: float,
    mission_years: float,
):
    sigma_altitude_km = 75
    sigma_inclination_deg = 5
    sigma_eccentricity = 0.01
    sigma_raan_deg = 20

    weighted_risk = 0.0
    close_matches = 0

    for obj in orbital_regimes:
        altitude_delta = altitude_km - obj["altitude_km"]
        inclination_delta = inclination_deg - obj["inclination_deg"]
        eccentricity_delta = eccentricity - obj.get("eccentricity", 0.0)
        raan_delta = angular_difference_deg(raan_deg, obj.get("raan_deg", 0.0))

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
    normalized_score = min(100, round((weighted_risk / max_reference) * 100))

    if normalized_score <= 30:
        risk_level = "Low"
    elif normalized_score <= 70:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "weighted_risk": weighted_risk,
        "risk_score": normalized_score,
        "risk_level": risk_level,
        "close_matches": close_matches,
        "duration_factor": round(duration_factor, 3),
    }


def get_recommendation(
    orbital_regimes,
    altitude_km: float,
    inclination_deg: float,
    eccentricity: float,
    raan_deg: float,
    mission_years: float,
    current_score: int,
):
    candidate_offsets = [-150, -100, -50, 50, 100, 150]
    best_option = None

    for offset in candidate_offsets:
        candidate_altitude = altitude_km + offset
        if candidate_altitude <= 0:
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
                }

    if best_option is None:
        return "No clearly better nearby altitude band was found with the current simplified model."

    return (
        f"A nearby lower-risk option is approximately "
        f"{best_option['altitude_km']} km at the same inclination and eccentricity."
    )


class OrbitAssessmentRequest(BaseModel):
    altitude_km: float = Field(..., ge=160, le=40000)
    inclination_deg: float = Field(..., ge=0, le=180)
    eccentricity: float = Field(0.0, ge=0, le=0.2)
    mission_years: float = Field(1.0, gt=0, le=20)
    raan_deg: float = Field(0.0, ge=0, le=360)


@app.get("/")
def root():
    return {"message": "Space Debris Dashboard API running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/altitude-bins")
def get_altitude_bins():
    return load_json(ALTITUDE_BINS_FILE)


@app.get("/orbital-regimes")
def get_orbital_regimes(limit: int = 500):
    data = load_json(ORBITAL_REGIMES_FILE)
    return data[:limit]


@app.get("/orbit-tracks")
def get_orbit_tracks(limit: int = 40):
    data = load_json(ORBIT_TRACKS_FILE)
    return data[:limit]


@app.post("/assess-orbit")
def assess_orbit(payload: OrbitAssessmentRequest):
    orbital_regimes = load_json(ORBITAL_REGIMES_FILE)

    risk_result = compute_orbit_risk(
        orbital_regimes=orbital_regimes,
        altitude_km=payload.altitude_km,
        inclination_deg=payload.inclination_deg,
        eccentricity=payload.eccentricity,
        raan_deg=payload.raan_deg,
        mission_years=payload.mission_years,
    )

    recommendation = get_recommendation(
        orbital_regimes=orbital_regimes,
        altitude_km=payload.altitude_km,
        inclination_deg=payload.inclination_deg,
        eccentricity=payload.eccentricity,
        raan_deg=payload.raan_deg,
        mission_years=payload.mission_years,
        current_score=risk_result["risk_score"],
    )

    return {
        "input": payload.model_dump(),
        "result": risk_result,
        "recommendation": recommendation,
    }
