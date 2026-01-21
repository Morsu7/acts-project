# ACTS (Autonomous City Traffic Simulation)

Project for the **Distributed Systems** course at University of Bologna / Cesena Campus.

ACTS simulates urban traffic using a decentralized Multi-Agent System (MAS). Instead of a central server controlling every light, each intersection and vehicle is an independent agent. They communicate locally to negotiate rights-of-way, mimicking a real peer-to-peer network topology.

![Screenshot](docs/screenshot.png)
*(Note: Visualized using Mesa NetworkModule to show logical connections)*

## Key Features

* **Graph-Based Topology:** We moved away from standard grid-based simulations. The city is modeled as a NetworkX graph where nodes are intersections and edges are roads.
* **Decentralized Logic:** Vehicles calculate paths based on local graph data.
* **Visualization:** Real-time view of the network state (Red nodes = Occupied, Green/Grey = Free).

## Project Structure

* `src/acts/core`: Main simulation loop and graph generation.
* `src/acts/agents`: Logic for Vehicles (movement) and Infrastructure.
* `src/acts/visualization`: Server setup using Mesa's NetworkModule.
* `src/acts/utils`: Helper scripts for topology generation (Random Geometric Graph).

## Installation & Run

You need **Python 3.10+**.

### 1. Local Setup (Recommended)

Clone the repo and install dependencies in editable mode (this is important for imports to work):

```bash
# Create venv
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements and the package itself
pip install -e .