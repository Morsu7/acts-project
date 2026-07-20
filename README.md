# ACTS: Autonomous City Traffic Simulation

ACTS is a decentralized, event-driven Multi-Agent System (MAS) for the simulation of urban traffic dynamics. Developed for the Distributed Systems course at the University of Bologna (Cesena Campus), the system replaces centralized traffic control with a peer-to-peer network where each intersection and vehicle acts as an independent autonomous agent.

## Architectural Overview

ACTS focuses on decentralization, asynchronous communication, and fault tolerance:

* **Decentralized Consensus:** Traffic lights negotiate green phases using distributed mutual exclusion mechanisms. Conflicts are resolved deterministically through Lamport Clocks and tie-breaking algorithms, ensuring stability and preventing deadlocks.
* **Event-Driven Backbone:** Agents operate in isolated execution contexts and communicate exclusively through asynchronous message passing using Redis as a message broker.
* **Fault Tolerance:** The system implements heartbeat protocols and health checks. Agents detect neighbor failures and automatically transition into safe fallback states without requiring centralized control.
* **Dynamic Routing:** Vehicles use constrained pathfinding algorithms powered by NetworkX to dynamically recalculate routes according to traffic conditions, traffic signal states, and local topology.
* **Graph-Based City Model:** The urban environment is represented as a directed NetworkX graph, where nodes correspond to intersections and edges represent road segments. This enables the simulation of complex city layouts beyond simple grid structures.

---

## Infrastructure

* **Simulation Engine:** Mesa (Agent-Based Modeling framework)
* **Communication Layer:** Redis Pub/Sub event bus
* **Environment Management:** Docker & Docker Compose
* **Programming Language:** Python 3.10+

---

## Project Structure

```
src/
├── acts/
│   ├── core/              # Simulation orchestration and main execution loop
│   ├── agents/            # Autonomous Vehicle and Traffic Light agents
│   ├── city_model/        # City topology generation and graph models
│   ├── visualization/     # Web-based control plane and visualization
│   └── utils/             # Messaging utilities and shared algorithms
│
tests/                     # Unit and integration tests
start.sh                   # Automated setup and execution script
docker-compose.yml         # Redis infrastructure definition
requirements.txt           # Python dependencies
```

---

# Getting Started

## Prerequisites

Make sure the following software is installed:

* Python 3.10 or higher
* Docker
* Docker Compose

# Installation & Execution

## Automated Setup (Recommended)

The repository provides a startup script that automatically:

1. Configures the Python environment.
2. Starts the Redis message broker.
3. Creates the virtual environment if it does not exist.
4. Installs Python dependencies.
5. Runs the test suite.
6. Starts the ACTS simulation.

Run:

```bash
chmod +x start.sh
./start.sh
```

The script automatically configures:

```bash
PYTHONPATH=<project-root>/src
```

so that the ACTS package can be correctly imported.

# Manual Execution

If you prefer to run the system manually:

## 1. Start Redis

```bash
docker compose up -d redis
```

## 2. Create and activate the virtual environment

### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Python path

### Linux/macOS

```bash
export PYTHONPATH=$PWD/src
```

### Windows PowerShell

```powershell
$env:PYTHONPATH="$PWD/src"
```

## 5. Run tests

```bash
pytest
```

## 6. Start ACTS

```bash
python -m acts
```

# Web Interface

Once ACTS is running, the simulation dashboard is available at:

```
http://localhost:8521
```

The interface provides a real-time visualization of:

* City topology and road network.
* Vehicle movements.
* Traffic light states.
* Agent interactions.

# Development Notes

ACTS is designed as a distributed simulation environment where each component behaves as an autonomous agent.

The main design principles are:

* No centralized traffic controller.
* Asynchronous communication between agents.
* Local decision-making.
* Distributed coordination through logical clocks.
* Resilient behavior under node failures.

# License

This project was developed as part of the Distributed Systems course at the University of Bologna (Cesena Campus).
