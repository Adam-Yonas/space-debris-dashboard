// 🔴 CHANGE THIS to your Render URL
const API_BASE = "https://space-debris-api.onrender.com";

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

// ========================
// LOAD DATA FROM API
// ========================
async function loadOrbitTracks() {
  orbitTracks = await fetchJson(`${API_BASE}/orbit-tracks?limit=40`);
  render3DPlot();
}

// ========================
// EARTH SPHERE
// ========================
function buildEarthSphere() {
  const R = 6378.137;
  const x = [], y = [], z = [];

  for (let i = 0; i <= 40; i++) {
    const theta = Math.PI * i / 40;
    const xr = [], yr = [], zr = [];

    for (let j = 0; j <= 40; j++) {
      const phi = 2 * Math.PI * j / 40;
      xr.push(R * Math.sin(theta) * Math.cos(phi));
      yr.push(R * Math.sin(theta) * Math.sin(phi));
      zr.push(R * Math.cos(theta));
    }

    x.push(xr);
    y.push(yr);
    z.push(zr);
  }

  return {
    type: "surface",
    x, y, z,
    opacity: 0.85,
    showscale: false
  };
}

// ========================
// USER ORBIT
// ========================
function buildUserOrbitTrack(alt, incDeg, ecc = 0, raanDeg = 0) {
  const R = 6378.137 + alt;
  const inc = incDeg * Math.PI / 180;
  const raan = raanDeg * Math.PI / 180;

  const x = [], y = [], z = [];

  for (let k = 0; k <= 128; k++) {
    const nu = 2 * Math.PI * k / 128;
    const r = R * (1 - ecc ** 2) / (1 + ecc * Math.cos(nu));

    const xp = r * Math.cos(nu);
    const yp = r * Math.sin(nu);

    const xe = xp * Math.cos(raan) - yp * Math.sin(raan) * Math.cos(inc);
    const ye = xp * Math.sin(raan) + yp * Math.cos(raan) * Math.cos(inc);
    const ze = yp * Math.sin(inc);

    x.push(xe);
    y.push(ye);
    z.push(ze);
  }

  return { x, y, z };
}

// ========================
// 3D PLOT
// ========================
function render3DPlot() {
  const traces = [buildEarthSphere()];

  // Debris orbits
  for (const track of orbitTracks) {
    traces.push({
      type: "scatter3d",
      mode: "lines",
      x: track.x,
      y: track.y,
      z: track.z,
      line: { width: 2, color: "#7ea6ff" },
      opacity: 0.4
    });
  }

  // User orbit
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
      line: { width: 6, color: "#ff9f43" }
    });
  }

  Plotly.newPlot("orbit3d", traces, {
    paper_bgcolor: "#121933",
    scene: { aspectmode: "data" },
    margin: { l: 0, r: 0, t: 40, b: 0 }
  });
}

// ========================
// API CALL FOR RISK
// ========================
async function assessOrbitViaApi(payload) {
  return await fetchJson(`${API_BASE}/assess-orbit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

// ========================
// UPDATE UI
// ========================
async function updateAssessment(input) {
  const res = await assessOrbitViaApi(input);

  const result = res.result;

  document.getElementById("selectedOrbit").textContent =
    `Orbit: ${input.altitude_km} km, ${input.inclination_deg}°`;

  document.getElementById("riskScore").textContent =
    `Risk: ${result.risk_score}/100`;

  document.getElementById("riskLevel").textContent =
    `Level: ${result.risk_level}`;

  document.getElementById("matchingObjects").textContent =
    `Nearby objects: ${result.close_matches}`;

  document.getElementById("missionExposure").textContent =
    `Duration factor: ${result.duration_factor}x`;

  document.getElementById("recommendation").textContent =
    res.recommendation;

  currentUserOrbit = input;
  render3DPlot();
}

// ========================
// INPUT HANDLING
// ========================
function getInputs() {
  return {
    altitude_km: Number(document.getElementById("altitudeInput").value),
    inclination_deg: Number(document.getElementById("inclinationInput").value),
    eccentricity: Number(document.getElementById("eccentricityInput").value),
    mission_years: Number(document.getElementById("durationInput").value),
    raan_deg: Number(document.getElementById("raanInput").value || 0)
  };
}

function setupControls() {
  document.getElementById("assessButton").onclick = async () => {
    try {
      await updateAssessment(getInputs());
    } catch (e) {
      alert(e.message);
    }
  };
}

// ========================
// INIT
// ========================
async function init() {
  try {
    await loadOrbitTracks();
    setupControls();
  } catch (err) {
    console.error(err);
    alert("API not reachable — check deployment");
  }
}

init();
