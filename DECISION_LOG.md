# Decision Log — Skylark Drones Operations Coordinator AI (Prototype)

## Context & Goal
Build a lightweight “operations coordinator” agent that helps manage **pilots**, **drones**, and **missions** with **2‑way Google Sheets sync**, a **conversational interface**, and robust **conflict detection** (double bookings, skill/cert gaps, maintenance, and location mismatches).

## Key Assumptions
- **Data source of truth**: Google Sheets is the system of record; the app loads from Sheets into pandas DataFrames on startup and on refresh.
- **Worksheets (“tabs”)**: The sheet tabs are named exactly:
  - `pilot_roster.csv`
  - `drone_fleet.csv`
  - `missions.csv`
  (If a spreadsheet has only one worksheet, we fall back to using it.)
- **Schema**: CSV/Sheet headers match the sample structure (e.g., `pilot_id`, `drone_id`, `project_id`, `skills`, `certifications`, `maintenance_due`).
- **Skills/certs encoding**: `skills`, `certifications`, `required_skills`, `required_certs`, and `capabilities` are **comma-separated** strings.
- **Dates**: Dates are provided in a parseable format (recommended `YYYY-MM-DD`). When parsing fails, the system treats dates as unknown and avoids crashing.
- **Single assignment per resource**: A pilot/drone has at most **one** `current_assignment` at a time (enough for a prototype and the provided dataset).

## Technical Choices & Trade-offs
### UI: Streamlit
- **Why**: Very fast to build a hosted prototype with tables, forms, and chat.
- **Trade-off**: Less flexible than a custom web frontend for advanced workflows (multi-step wizards, complex validation, inline table editing).

### “Agent” design: Rule-based intent routing (no external LLM dependency)
- **Why**: Deterministic behavior, easy debugging, runs in constrained environments, avoids keys/latency/cost.
- **Trade-off**: Natural language support is limited to simple intent matching and ID extraction; not a full conversational planner.

### Conflict detection: DataFrame-driven checks
- **Why**: Transparent logic; easy to extend.
- **Trade-off**: Not yet a full constraint solver/optimizer; it flags issues and suggests candidates rather than automatically scheduling everything.

### Google Sheets sync: gspread + service account
- **Why**: Simple and widely used approach for 2‑way sync.
- **Trade-offs**:
  - Updates are per-cell/row operations (can be slower at large scale).
  - No transaction semantics; partial updates are possible if a network error occurs mid-operation.

## “Urgent Reassignments” — Interpretation
**Interpretation**: When missions are marked `priority = Urgent`, the agent should:
- Surface urgent missions quickly.
- Recommend the best available pilots for each urgent mission.
- Explain *why* each recommendation is strong (skills, certs, location, availability).
- If no perfect match exists, suggest the next best options and explicitly call out what constraints fail (e.g., missing Night Ops cert, different location).

**Implementation**:
- The agent scans for missions where `priority == "Urgent"`.
- It ranks candidates via a scoring model that rewards:
  - Required skills match
  - Required certs match
  - Same location
  - Availability before mission start
- It returns the **top N** suggestions with reasons, leaving the final “commit” step to the operator via the app’s Data Management actions (so changes are intentional and auditable).

## What I’d Do Differently With More Time
- **Stronger “assignment manager” workflow**:
  - UI to select mission → pick pilot + drone → run validations → commit assignment updates back to Sheets.
  - Multi-resource double-booking (pilots + drones) and assignment history.
- **Inline editing**:
  - Update any pilot/drone/mission field (not only status) without delete/re-add.
- **Better NLP**:
  - Add an LLM (optional) for richer conversation, multi-step clarification, and better intent/entity extraction.
  - Keep rule-based validations as the final “source of truth” layer.
- **Reliability & scale**:
  - Batch updates to Sheets.
  - Add retries/backoff and structured error reporting.
  - Add automated tests for the conflict rules and date parsing edge cases.
- **Security / access**:
  - AuthN/AuthZ (role-based access for ops coordinator vs viewer).
  - Audit log of changes (who changed what, when).

## Notes on Edge Cases
The system is designed to *flag* these cases (and avoid crashing on bad data):
- Overlapping mission dates → **Double Booking**
- Missing required skills/certs → **Skill/Cert Mismatch**
- Assigned while unavailable → **Unavailable Assignment**
- Pilot vs mission location mismatch → **Location Mismatch**
- Drone maintenance due while assigned → **Maintenance Required**

