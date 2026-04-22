let orbitTracks = [];
let currentUserOrbit = null;

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed: ${response.status} ${text}`);
  }

  return await response.json();
}

async function loadOrbitTracks() {
  orbitTracks = await fetchJson("http://127.0.0.1:8000/orbit-tracks?limit=40");
  render3DPlot();
}

function buildEarthSphere() {
  const earthRadiusKm = 6378.137;
  const uSteps = 40;
  const vSteps = 40;

  const x = [];
  const y = [];
  const z = [];

  for (let i = 0; i <= uSteps; i++) {
    const theta = Math.PI * i / uSteps;
    const xRow = [];
    const yRow = [];
    const zRow = [];

    for (let j = 0; j <= vSteps; j++) {
      const phi = 2 * Math.PI * j / vSteps;
      xRow.push(earthRadiusKm * Math.sin(theta) * Math.cos(phi));
      yRow.push(earthRadiusKm * Math.sin(theta) * Math.sin(phi));
      zRow.push(earthRadiusKm * Math.cos(theta));
    }

    x.push(xRow);
    y.push(yRow);
    z.push(zRow);
  }

  return {
    type: "surface",
    x,
    y,
    z,
    opacity: 0.85,
    showscale: false,
    hoverinfo: "skip",
    colorscale: [
      [0, "#1b2a6b"],
      [1, "#355caa"]
    ]
  };
}

function buildUserOrbitTrack(altitudeKm, inclinationDeg, eccentricity = 0, raanDeg = 0, numPoints = 128) {
  const earthRadiusKm = 6378.137;
  const semiMajorAxis = earthRadiusKm + altitudeKm;

  const inc = inclinationDeg * Math.PI / 180;
  const raan = raanDeg * Math.PI / 180;

  const x = [];
  const y = [];
  const z = [];

  for (let k = 0; k <= numPoints; k++) {
    const nu = 2 * Math.PI * k / numPoints;

    const r = semiMajorAxis * (1 - eccentricity ** 2) / (1 + eccentricity * Math.cos(nu));

    // Perifocal frame
    const xp = r * Math.cos(nu);
    const yp = r * Math.sin(nu);

    // Rotate by inclination and RAAN; arg of perigee assumed 0 for user display
    const xe = xp * Math.cos(raan) - yp * Math.sin(raan) * Math.cos(inc);
    const ye = xp * Math.sin(raan) + yp * Math.cos(raan) * Math.cos(inc);
    const ze = yp * Math.sin(inc);

    x.push(xe);
    y.push(ye);
    z.push(ze);
  }

  return { x, y, z };
}

function render3DPlot() {
  const traces = [buildEarthSphere()];

  for (const track of orbitTracks) {
    traces.push({
      type: "scatter3d",
      mode: "lines",
      x: track.x,
      y: track.y,
      z: track.z,
      line: {
        width: 2,
        color: "#7ea6ff"
      },
      opacity: 0.45,
      name: track.object_name,
      hovertemplate:
        `<b>${track.object_name}</b><br>` +
        `Altitude: ${track.altitude_km} km<br>` +
        `Inclination: ${track.inclination_deg}°<extra></extra>`
    });
  }

  if (currentUserOrbit) {
    const userTrack = buildUserOrbitTrack(
      currentUserOrbit.altitude_km,
      currentUserOrbit.inclination_deg,
      currentUserOrbit.eccentricity,
      currentUserOrbit.raan_deg
    );

    traces.push({
      type: "scatter3d",
      mode: "lines",
      x: userTrack.x,
      y: userTrack.y,
      z: userTrack.z,
      line: {
        width: 7,
        color: "#ff9f43"
      },
      name: "Proposed Orbit",
      hovertemplate:
        `<b>Proposed Orbit</b><br>` +
        `Altitude: ${currentUserOrbit.altitude_km} km<br>` +
        `Inclination: ${currentUserOrbit.inclination_deg}°<br>` +
        `Eccentricity: ${currentUserOrbit.eccentricity}<br>` +
        `RAAN: ${currentUserOrbit.raan_deg}°<extra></extra>`
    });
  }

  const layout = {
    title: "3D Orbit Visualization",
    paper_bgcolor: "#121933",
    plot_bgcolor: "#121933",
    font: {
      color: "#f5f7ff"
    },
    scene: {
      bgcolor: "#121933",
      xaxis: {
        title: "X (km)",
        color: "#f5f7ff",
        gridcolor: "#33406f",
        zerolinecolor: "#33406f"
      },
      yaxis: {
        title: "Y (km)",
        color: "#f5f7ff",
        gridcolor: "#33406f",
        zerolinecolor: "#33406f"
      },
      zaxis: {
        title: "Z (km)",
        color: "#f5f7ff",
        gridcolor: "#33406f",
        zerolinecolor: "#33406f"
      },
      aspectmode: "data",
      camera: {
        eye: { x: 1.4, y: 1.4, z: 0.9 }
      }
    },
    margin: { l: 0, r: 0, t: 50, b: 0 },
    showlegend: false
  };

  Plotly.newPlot("orbit3d", traces, layout, { responsive: true });
}

async function assessOrbitViaApi(payload) {
  return await fetchJson("http://127.0.0.1:8000/assess-orbit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

async function updateAssessment(orbitInput) {
  const selectedOrbitEl = document.getElementById("selectedOrbit");
  const riskScoreEl = document.getElementById("riskScore");
  const riskLevelEl = document.getElementById("riskLevel");
  const matchingObjectsEl = document.getElementById("matchingObjects");
  const missionExposureEl = document.getElementById("missionExposure");
  const recommendationEl = document.getElementById("recommendation");

  const apiResponse = await assessOrbitViaApi(orbitInput);

  const result = apiResponse.result;
  const recommendation = apiResponse.recommendation;

  selectedOrbitEl.textContent =
    `Selected orbit: ${orbitInput.altitude_km} km altitude, ${orbitInput.inclination_deg}° inclination, e=${orbitInput.eccentricity}, ${orbitInput.mission_years} year mission`;

  riskScoreEl.textContent = `Orbital regime risk score: ${result.risk_score} / 100`;
  riskLevelEl.textContent = `Risk level: ${result.risk_level}`;
  matchingObjectsEl.textContent =
    `Nearby matching debris objects in this simplified regime window: ${result.close_matches}`;
  missionExposureEl.textContent =
    `Mission duration multiplier applied: ${result.duration_factor}x`;
  recommendationEl.textContent = recommendation;

  currentUserOrbit = orbitInput;
  render3DPlot();
}

function getFormValues() {
  const altitudeInput = document.getElementById("altitudeInput");
  const inclinationInput = document.getElementById("inclinationInput");
  const eccentricityInput = document.getElementById("eccentricityInput");
  const durationInput = document.getElementById("durationInput");
  const raanInput = document.getElementById("raanInput");

  const altitude = Number(altitudeInput.value);
  const inclination = Number(inclinationInput.value);
  const eccentricity = Number(eccentricityInput.value);
  const missionYears = Number(durationInput.value);
  const raan = raanInput.value === "" ? 0 : Number(raanInput.value);

  if (Number.isNaN(altitude) || altitude < 160) {
    throw new Error("Please enter a valid altitude of at least 160 km.");
  }

  if (Number.isNaN(inclination) || inclination < 0 || inclination > 180) {
    throw new Error("Please enter a valid inclination between 0 and 180 degrees.");
  }

  if (Number.isNaN(eccentricity) || eccentricity < 0 || eccentricity > 0.2) {
    throw new Error("Please enter a valid eccentricity between 0 and 0.2.");
  }

  if (Number.isNaN(missionYears) || missionYears <= 0 || missionYears > 20) {
    throw new Error("Please enter a valid mission duration in years.");
  }

  if (Number.isNaN(raan) || raan < 0 || raan > 360) {
    throw new Error("Please enter a valid RAAN between 0 and 360 degrees.");
  }

  return {
    altitude_km: altitude,
    inclination_deg: inclination,
    eccentricity: eccentricity,
    mission_years: missionYears,
    raan_deg: raan
  };
}

function setupControls() {
  const button = document.getElementById("assessButton");
  const inputIds = [
    "altitudeInput",
    "inclinationInput",
    "eccentricityInput",
    "durationInput",
    "raanInput"
  ];

  async function runAssessment() {
    try {
      const orbitInput = getFormValues();
      await updateAssessment(orbitInput);
    } catch (error) {
      alert(error.message || "Failed to assess orbit.");
      console.error(error);
    }
  }

  button.addEventListener("click", runAssessment);

  for (const id of inputIds) {
    const input = document.getElementById(id);
    input.addEventListener("keydown", async (event) => {
      if (event.key === "Enter") {
        await runAssessment();
      }
    });
  }
}

async function init() {
  try {
    await loadOrbitTracks();
    setupControls();
  } catch (error) {
    console.error(error);
    document.getElementById("resultsCard").innerHTML =
      `<h2>Orbit Assessment</h2><p>Failed to load API data. Make sure the FastAPI server is running at http://127.0.0.1:8000.</p>`;
  }
}

init();