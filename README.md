# UAS Post-Failure Trajectory Simulator

A simulator for analyzing the **post-failure trajectory of Unmanned Aircraft Systems (UAS)** based on aircraft characteristics, weather conditions, and initial flight parameters.

The system models how a drone behaves after a failure event and provides visualization and impact analysis results.

---

# Features

- Simulates **post-failure trajectories** of UAS
- Uses **airport weather conditions** based on ICAO codes
- Generates a **3D glide path visualization**
- Calculates **estimated impact energy**
- Supports two types of aircraft:
  - **Quadcopters**
  - **Fixed-wing aircraft**
- Includes a **modifiable aircraft database**

---

# How to Run

## Option 1 – Run the Python Application

Execute the main application file:

```bash
python app.py
```

Then open the **locally hosted website** displayed in the terminal.

---

## Option 2 – Run the Standalone Application

Alternatively, run the executable located inside the **/dist** folder.

This version functions as a **standalone application** and does not require Python to be run manually.

---

# How the Simulator Works

The simulator combines several inputs to model the aircraft trajectory after a failure:

- **Selected UAS system**
  - Aircraft specifications are stored in an internal database
- **Weather conditions**
  - Retrieved using the airport **ICAO code**
- **Initial flight conditions**
  - User-defined position and velocity

Using these parameters, the system calculates the **post-failure flight path** and generates simulation outputs.

---

# Simulation Outputs

The simulator provides:

- **Post-failure trajectory**
- **3D glide path visualization**
- **Estimated impact energy**

These results help analyze the **behavior and potential risks of UAS during failure scenarios**.

---

# Aircraft Database

All UAS information is stored in a **modifiable database**, allowing users to:

- Add new aircraft
- Modify existing parameters
- Extend simulation capabilities

---

# Project Status

Project development was **completed on 6 September 2024**.

