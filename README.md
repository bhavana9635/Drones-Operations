# Skylark Drones – Operations Coordinator AI

AI assistant to help Skylark manage **pilots**, **drones**, and **missions** with a simple web UI and Google Sheets as the source of truth.

---

## Live Demo

Hosted app: **[link coming soon]**

---

## Features

- **Roster Management**
  - View/filter pilots by status, location, skills.
  - Update pilot status (Available / Assigned / On Leave) with 2‑way Google Sheets sync.
  - Add and delete pilots.

- **Assignment & Urgent Missions**
  - Match pilots to missions based on skills, certifications, location, and availability.
  - Detect urgent missions and suggest the best backup pilots with explanations.

- **Drone Fleet**
  - View full fleet with status and location.
  - Update drone status (Available / Deployed / Maintenance) with sync to Sheets.
  - Add and delete drones.

- **Conflict Detection**
  - Double booking for overlapping missions.
  - Skill/certification mismatches.
  - Pilot vs mission location mismatches.
  - Drones in/near maintenance while assigned.

---

## Tech Stack

- **Frontend / UI**: Streamlit (`app.py`)
- **Logic / Agent**: Python (`agent_logic.py`)
- **Data & Sync**: Google Sheets via `gspread` (`sheets_manager.py`)
- **Data Model**: `pilot_roster`, `drone_fleet`, `missions` sheets

---

## Running Locally

pip install -r requirements.txt
streamlit run app.py
