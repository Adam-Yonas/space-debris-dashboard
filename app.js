const API_BASE = "https://space-debris-dashboard.onrender.com";

const { createApp, nextTick } = Vue;

createApp({
  data() {
    return {
      orbitTracks: [],
      currentUserOrbit: null,
      loading: false,
      error: "",
      assessment: null,
      recommendation: "",
      form: {
        altitude_km: 550,
        inclination_deg: 97.6,
        eccentricity: 0.001,
        mission_years: 3,
        raan_deg: 0,
      },
    };
  },

  computed: {
    selectedOrbitText() {
      if (!this.currentUserOrbit) return "";
      return `Orbit: ${this.currentUserOrbit.altitude_km} km, ${this.currentUserOrbit.inclination_deg}°`;
    },
    riskScoreText() {
      return this.assessment ? `Risk: ${this.assessment.risk_score}/100` : "";
    },
    riskLevelText() {
      return this.assessment ? `Level: ${this.assessment.risk_level}` : "";
    },
    matchingObjectsText() {
      return this.assessment ? `Nearby objects: ${this.assessment.close_matches}` : "";
    },
    missionExposureText() {
      return this.assessment ? `Duration factor: ${this.assessment.duration_factor}x` : "";
    },
    recommendationText() {
      return this.recommendation || "";
    },
  },

  methods: {
    async fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Request failed: ${response.status} ${text}`);
      }
      return await response.json();
    },

    async loadOrbitTracks() {
      this.orbitTracks = await this.fetchJson(`${API_BASE}/orbit-tracks?limit=40`);
      await nextTick();
      this.render3DPlot();
    },

    buildEarthSphere() {
      const R = 6378.137;
      const x = [];
      const y = [];
      const z = [];

      for (let i = 0; i <= 40; i++) {
        const theta = Math.PI * i / 40;
        const xr = [];
        const yr = [];
        const zr = [];

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
        x,
        y,
        z,
        opacity: 0.85,
        showscale: false,
      };
    },

    buildUserOrbitTrack(alt, incDeg, ecc = 0, raanDeg = 0) {
      const R = 6378.137 + alt;
      const inc = incDeg * Math.PI / 180;
      const raan = raanDeg * Math.PI / 180;
      const x = [];
      const y = [];
      const z = [];

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
    },

    render3DPlot() {
      const traces = [this.buildEarthSphere()];

      for (const track of this.orbitTracks) {
        traces.push({
          type: "scatter3d",
          mode: "lines",
          x: track.x,
          y: track.y,
          z: track.z,
          line: { width: 2, color: "#7ea6ff" },
          opacity: 0.4,
        });
      }

      if (this.currentUserOrbit) {
        const userTrack = this.buildUserOrbitTrack(
          this.currentUserOrbit.altitude_km,
          this.currentUserOrbit.inclination_deg,
          this.currentUserOrbit.eccentricity,
          this.currentUserOrbit.raan_deg
        );

        traces.push({
          type: "scatter3d",
          mode: "lines",
          x: userTrack.x,
          y: userTrack.y,
          z: userTrack.z,
          line: { width: 6, color: "#ff9f43" },
        });
      }

      Plotly.newPlot("orbit3d", traces, {
        paper_bgcolor: "#121933",
        scene: {
          aspectmode: "data",
          bgcolor: "#121933",
        },
        margin: { l: 0, r: 0, t: 40, b: 0 },
      });
    },

    async assessOrbit() {
      this.loading = true;
      this.error = "";

      try {
        const payload = {
          altitude_km: Number(this.form.altitude_km),
          inclination_deg: Number(this.form.inclination_deg),
          eccentricity: Number(this.form.eccentricity),
          mission_years: Number(this.form.mission_years),
          raan_deg: Number(this.form.raan_deg || 0),
        };

        const res = await this.fetchJson(`${API_BASE}/assess-orbit`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        this.assessment = res.result;
        this.recommendation = res.recommendation;
        this.currentUserOrbit = payload;

        await nextTick();
        this.render3DPlot();
      } catch (err) {
        console.error(err);
        this.error = err.message || "Failed to assess orbit.";
      } finally {
        this.loading = false;
      }
    },
  },

  async mounted() {
    try {
      await this.loadOrbitTracks();
    } catch (err) {
      console.error(err);
      this.error = "API not reachable — check deployment";
    }
  },
}).mount("#app");
