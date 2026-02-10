import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import re


class DroneOpsAgent:
    """Intelligent agent for drone operations management with conflict detection"""
    
    def __init__(
        self,
        pilots_df_or_manager,
        drones_df: Optional[pd.DataFrame] = None,
        missions_df: Optional[pd.DataFrame] = None,
    ):
        """
        Initialize the agent.

        Supports two calling patterns:
        - DroneOpsAgent(SheetsManager)  -> used by the Streamlit app
        - DroneOpsAgent(pilots_df, drones_df, missions_df)  -> direct DataFrame usage
        """
        # Detect if we've been given a SheetsManager-like object
        if hasattr(pilots_df_or_manager, "pilots_df") and hasattr(
            pilots_df_or_manager, "drones_df"
        ) and hasattr(pilots_df_or_manager, "missions_df"):
            self.sheets_manager = pilots_df_or_manager
            self.pilots_df = self.sheets_manager.pilots_df.copy()
            self.drones_df = self.sheets_manager.drones_df.copy()
            self.missions_df = self.sheets_manager.missions_df.copy()
        else:
            self.sheets_manager = None
            self.pilots_df = pilots_df_or_manager.copy()
            if drones_df is None or missions_df is None:
                raise ValueError(
                    "When not passing a SheetsManager, you must provide drones_df and missions_df"
                )
            self.drones_df = drones_df.copy()
            self.missions_df = missions_df.copy()

        self._preprocess_data()
    
    def _preprocess_data(self):
        """Preprocess and clean data"""
        # Convert dates safely
        self.missions_df['start_date'] = pd.to_datetime(self.missions_df['start_date'], errors='coerce')
        self.missions_df['end_date'] = pd.to_datetime(self.missions_df['end_date'], errors='coerce')
        self.drones_df['maintenance_due'] = pd.to_datetime(self.drones_df['maintenance_due'], errors='coerce')
        self.pilots_df['available_from'] = pd.to_datetime(self.pilots_df['available_from'], errors='coerce')
        
        # Parse skills and certifications
        self.pilots_df['skills_list'] = self.pilots_df['skills'].fillna('').str.split(',').apply(
            lambda x: [s.strip().lower() for s in x if s.strip()]
        )
        self.pilots_df['certs_list'] = self.pilots_df['certifications'].fillna('').str.split(',').apply(
            lambda x: [s.strip().lower() for s in x if s.strip()]
        )
        
        self.missions_df['required_skills_list'] = self.missions_df['required_skills'].fillna('').str.split(',').apply(
            lambda x: [s.strip().lower() for s in x if s.strip()]
        )
        self.missions_df['required_certs_list'] = self.missions_df['required_certs'].fillna('').str.split(',').apply(
            lambda x: [s.strip().lower() for s in x if s.strip()]
        )
        
        self.drones_df['capabilities_list'] = self.drones_df['capabilities'].fillna('').str.split(',').apply(
            lambda x: [s.strip().lower() for s in x if s.strip()]
        )
        
        # Replace '–' with None for assignments
        self.pilots_df['current_assignment'] = self.pilots_df['current_assignment'].replace(['–', '', 'None'], None)
        self.drones_df['current_assignment'] = self.drones_df['current_assignment'].replace(['–', '', 'None'], None)
    
    def _is_date_valid(self, date_value):
        """Check if date is valid (not NaT)"""
        return pd.notna(date_value)
    
    def detect_all_conflicts(self) -> List[Dict]:
        """Detect all types of conflicts"""
        conflicts = []
        today = datetime.now().date()
        
        # 1. Double Booking Detection
        for _, pilot in self.pilots_df.iterrows():
            if pd.notna(pilot['current_assignment']):
                assigned_mission = self.missions_df[
                    self.missions_df['project_id'] == pilot['current_assignment']
                ]
                
                if not assigned_mission.empty:
                    mission = assigned_mission.iloc[0]
                    
                    # Skip if dates are invalid
                    if not self._is_date_valid(mission['start_date']) or not self._is_date_valid(mission['end_date']):
                        continue
                    
                    mission_start = mission['start_date'].date()
                    mission_end = mission['end_date'].date()
                    
                    # Find overlapping missions
                    for _, other_mission in self.missions_df.iterrows():
                        if other_mission['project_id'] == mission['project_id']:
                            continue
                        
                        # Skip if dates are invalid
                        if not self._is_date_valid(other_mission['start_date']) or not self._is_date_valid(other_mission['end_date']):
                            continue
                        
                        other_start = other_mission['start_date'].date()
                        other_end = other_mission['end_date'].date()
                        
                        # Check for overlap
                        if (other_start <= mission_end and other_end >= mission_start):
                            conflicts.append({
                                'type': 'Double Booking',
                                'severity': 'High',
                                'description': f"Pilot {pilot['name']} assigned to {pilot['current_assignment']} overlaps with {other_mission['project_id']}",
                                'affected_entity': pilot['pilot_id'],
                                'details': {
                                    'pilot': pilot['name'],
                                    'current_mission': pilot['current_assignment'],
                                    'conflicting_mission': other_mission['project_id']
                                }
                            })
        
        # 2. Skill/Certification Mismatch
        for _, mission in self.missions_df.iterrows():
            # Skip if dates are invalid
            if not self._is_date_valid(mission['start_date']) or not self._is_date_valid(mission['end_date']):
                continue
            
            start = mission['start_date'].date()
            end = mission['end_date'].date()
            
            # Check if mission is active or upcoming
            if start <= today <= end or start > today:
                assigned_pilots = self.pilots_df[
                    self.pilots_df['current_assignment'] == mission['project_id']
                ]
                
                for _, pilot in assigned_pilots.iterrows():
                    missing_skills = [
                        skill for skill in mission['required_skills_list']
                        if skill not in pilot['skills_list']
                    ]
                    missing_certs = [
                        cert for cert in mission['required_certs_list']
                        if cert not in pilot['certs_list']
                    ]
                    
                    if missing_skills or missing_certs:
                        conflicts.append({
                            'type': 'Skill/Cert Mismatch',
                            'severity': 'High',
                            'description': f"Pilot {pilot['name']} lacks required skills/certs for {mission['project_id']}",
                            'affected_entity': pilot['pilot_id'],
                            'details': {
                                'pilot': pilot['name'],
                                'mission': mission['project_id'],
                                'missing_skills': missing_skills,
                                'missing_certs': missing_certs
                            }
                        })
        
        # 3. Location Mismatch
        for _, pilot in self.pilots_df.iterrows():
            if pd.notna(pilot['current_assignment']):
                assigned_mission = self.missions_df[
                    self.missions_df['project_id'] == pilot['current_assignment']
                ]
                
                if not assigned_mission.empty:
                    mission = assigned_mission.iloc[0]
                    if pilot['location'] != mission['location']:
                        conflicts.append({
                            'type': 'Location Mismatch',
                            'severity': 'Medium',
                            'description': f"Pilot {pilot['name']} in {pilot['location']} assigned to mission in {mission['location']}",
                            'affected_entity': pilot['pilot_id'],
                            'details': {
                                'pilot': pilot['name'],
                                'pilot_location': pilot['location'],
                                'mission_location': mission['location'],
                                'mission': pilot['current_assignment']
                            }
                        })
        
        # 4. Maintenance Issues
        for _, drone in self.drones_df.iterrows():
            if pd.notna(drone['current_assignment']) and self._is_date_valid(drone['maintenance_due']):
                maint_date = drone['maintenance_due'].date()
                
                if maint_date <= today:
                    conflicts.append({
                        'type': 'Maintenance Required',
                        'severity': 'High',
                        'description': f"Drone {drone['drone_id']} needs maintenance but is assigned to {drone['current_assignment']}",
                        'affected_entity': drone['drone_id'],
                        'details': {
                            'drone': drone['drone_id'],
                            'model': drone['model'],
                            'assignment': drone['current_assignment'],
                            'maintenance_due': drone['maintenance_due'].strftime('%Y-%m-%d')
                        }
                    })
        
        # 5. Unavailable Pilot Assignments
        for _, pilot in self.pilots_df.iterrows():
            if pilot['status'] != 'Available' and pd.notna(pilot['current_assignment']):
                conflicts.append({
                    'type': 'Unavailable Assignment',
                    'severity': 'High',
                    'description': f"Pilot {pilot['name']} status is '{pilot['status']}' but assigned to {pilot['current_assignment']}",
                    'affected_entity': pilot['pilot_id'],
                    'details': {
                        'pilot': pilot['name'],
                        'status': pilot['status'],
                        'assignment': pilot['current_assignment']
                    }
                })
        
        return conflicts
    
    def find_best_pilots(self, mission_id: str, top_n: int = 3) -> List[Dict]:
        """Find best available pilots for a mission"""
        mission = self.missions_df[self.missions_df['project_id'] == mission_id]
        
        if mission.empty:
            return []
        
        mission = mission.iloc[0]
        available_pilots = self.pilots_df[self.pilots_df['status'] == 'Available'].copy()
        
        if available_pilots.empty:
            return []
        
        # Score pilots
        scores = []
        for _, pilot in available_pilots.iterrows():
            score = 0
            reasons = []
            
            # Skill match
            skill_match = len(set(mission['required_skills_list']) & set(pilot['skills_list']))
            score += skill_match * 10
            if skill_match == len(mission['required_skills_list']):
                reasons.append("✅ All required skills")
            else:
                reasons.append(f"⚠️ {skill_match}/{len(mission['required_skills_list'])} skills")
            
            # Certification match
            cert_match = len(set(mission['required_certs_list']) & set(pilot['certs_list']))
            score += cert_match * 15
            if cert_match == len(mission['required_certs_list']):
                reasons.append("✅ All required certifications")
            else:
                reasons.append(f"⚠️ {cert_match}/{len(mission['required_certs_list'])} certifications")
            
            # Location match
            if pilot['location'] == mission['location']:
                score += 20
                reasons.append(f"✅ Same location ({pilot['location']})")
            else:
                reasons.append(f"⚠️ Different location (pilot in {pilot['location']}, mission in {mission['location']})")
            
            # Availability date
            if self._is_date_valid(pilot['available_from']) and self._is_date_valid(mission['start_date']):
                if pilot['available_from'].date() <= mission['start_date'].date():
                    score += 5
                    reasons.append("✅ Available before mission start")
                else:
                    reasons.append("⚠️ Not available until after mission start")
            
            scores.append({
                'pilot_id': pilot['pilot_id'],
                'name': pilot['name'],
                'score': score,
                'location': pilot['location'],
                'skills': pilot['skills'],
                'certifications': pilot['certifications'],
                'reasons': reasons,
                'is_perfect_match': score >= 50
            })
        
        # Sort by score
        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores[:top_n]
    
    def get_availability_summary(self) -> Dict:
        """Get summary of availability"""
        today = datetime.now().date()
        
        # Count active and upcoming missions (skip invalid dates)
        active_missions = 0
        upcoming_missions = 0
        
        for _, mission in self.missions_df.iterrows():
            if self._is_date_valid(mission['start_date']) and self._is_date_valid(mission['end_date']):
                start = mission['start_date'].date()
                end = mission['end_date'].date()
                
                if start <= today <= end:
                    active_missions += 1
                elif start > today:
                    upcoming_missions += 1
        
        return {
            'pilots': {
                'total': len(self.pilots_df),
                'available': len(self.pilots_df[self.pilots_df['status'] == 'Available']),
                'assigned': len(self.pilots_df[self.pilots_df['current_assignment'].notna()]),
                'on_leave': len(self.pilots_df[self.pilots_df['status'] == 'On Leave'])
            },
            'drones': {
                'total': len(self.drones_df),
                'available': len(self.drones_df[self.drones_df['status'] == 'Available']),
                'deployed': len(self.drones_df[self.drones_df['status'] == 'Deployed']),
                'maintenance': len(self.drones_df[self.drones_df['status'] == 'Maintenance'])
            },
            'missions': {
                'total': len(self.missions_df),
                'active': active_missions,
                'upcoming': upcoming_missions,
                'urgent': len(self.missions_df[self.missions_df['priority'] == 'Urgent'])
            }
        }
    
    def assign_pilot(self, pilot_id: str, mission_id: str) -> Tuple[bool, str]:
        """Assign a pilot to a mission"""
        pilot_idx = self.pilots_df[self.pilots_df['pilot_id'] == pilot_id].index
        mission = self.missions_df[self.missions_df['project_id'] == mission_id]
        
        if pilot_idx.empty:
            return False, f"Pilot {pilot_id} not found"
        
        if mission.empty:
            return False, f"Mission {mission_id} not found"
        
        pilot_idx = pilot_idx[0]
        mission = mission.iloc[0]
        
        # Verify skills and certs
        pilot = self.pilots_df.loc[pilot_idx]
        missing_skills = [s for s in mission['required_skills_list'] if s not in pilot['skills_list']]
        missing_certs = [c for c in mission['required_certs_list'] if c not in pilot['certs_list']]
        
        if missing_skills or missing_certs:
            warnings = []
            if missing_skills:
                warnings.append(f"Missing skills: {', '.join(missing_skills)}")
            if missing_certs:
                warnings.append(f"Missing certifications: {', '.join(missing_certs)}")
            return False, "; ".join(warnings)
        
        # Assign
        self.pilots_df.loc[pilot_idx, 'status'] = 'Assigned'
        self.pilots_df.loc[pilot_idx, 'current_assignment'] = mission_id
        
        if self._is_date_valid(mission['end_date']):
            self.pilots_df.loc[pilot_idx, 'available_from'] = mission['end_date']
        
        return True, f"Successfully assigned {pilot['name']} to {mission_id}"
    
    def unassign_pilot(self, pilot_id: str) -> Tuple[bool, str]:
        """Unassign a pilot from their current mission"""
        pilot_idx = self.pilots_df[self.pilots_df['pilot_id'] == pilot_id].index
        
        if pilot_idx.empty:
            return False, f"Pilot {pilot_id} not found"
        
        pilot_idx = pilot_idx[0]
        pilot = self.pilots_df.loc[pilot_idx]
        
        if pd.isna(pilot['current_assignment']):
            return False, f"Pilot {pilot['name']} is not currently assigned"
        
        old_assignment = pilot['current_assignment']
        self.pilots_df.loc[pilot_idx, 'status'] = 'Available'
        self.pilots_df.loc[pilot_idx, 'current_assignment'] = None
        self.pilots_df.loc[pilot_idx, 'available_from'] = datetime.now()
        
        return True, f"Successfully unassigned {pilot['name']} from {old_assignment}"
    
    def get_mission_status(self, mission_id: str) -> Optional[Dict]:
        """Get detailed status of a mission"""
        mission = self.missions_df[self.missions_df['project_id'] == mission_id]
        
        if mission.empty:
            return None
        
        mission = mission.iloc[0]
        assigned_pilots = self.pilots_df[self.pilots_df['current_assignment'] == mission_id]
        
        today = datetime.now().date()
        
        status = "Unknown"
        if self._is_date_valid(mission['start_date']) and self._is_date_valid(mission['end_date']):
            start = mission['start_date'].date()
            end = mission['end_date'].date()
            
            if start <= today <= end:
                status = "Active"
            elif start > today:
                status = "Upcoming"
            else:
                status = "Completed"
        
        return {
            'project_id': mission['project_id'],
            'client': mission['client'],
            'location': mission['location'],
            'start_date': mission['start_date'].strftime('%Y-%m-%d') if self._is_date_valid(mission['start_date']) else 'Invalid',
            'end_date': mission['end_date'].strftime('%Y-%m-%d') if self._is_date_valid(mission['end_date']) else 'Invalid',
            'priority': mission['priority'],
            'status': status,
            'required_skills': mission['required_skills'],
            'required_certs': mission['required_certs'],
            'assigned_pilots': assigned_pilots[['pilot_id', 'name', 'skills', 'certifications']].to_dict('records')
        }

    # ------------- Conversational Interface -------------

    def process_query(self, query: str) -> str:
        """
        Lightweight intent router for conversational queries used by the Streamlit UI.
        Returns a markdown-formatted response.
        """
        q = query.lower()

        # Explicit intents first
        if any(k in q for k in ["conflict", "issue", "problem", "mismatch", "double book"]):
            return self._respond_conflicts()

        if any(k in q for k in ["urgent", "priority", "emergency"]):
            return self._respond_urgent_missions()

        if any(k in q for k in ["available", "availability", "who is available", "free to fly"]):
            return self._respond_availability()

        if any(k in q for k in ["mission", "project", "client"]):
            # Mission status / overview
            return self._respond_mission_overview(q)

        if any(k in q for k in ["assign", "allocate", "schedule"]):
            return self._respond_assignment_intent(q)

        if any(k in q for k in ["pilot", "roster"]):
            return self._respond_pilot_roster()

        if any(k in q for k in ["drone", "fleet", "equipment"]):
            return self._respond_drone_fleet()

        # Fallback help
        return self._respond_help()

    def _respond_help(self) -> str:
        return (
            "👋 **I'm your Drone Operations Coordinator AI.**\n\n"
            "I can help with:\n\n"
            "- **Availability**: \"Who is available in Bangalore for mapping?\"\n"
            "- **Conflicts**: \"Show me all current conflicts\" or \"Any double bookings?\"\n"
            "- **Urgent missions**: \"Which missions are urgent?\" or \"Suggest urgent reassignments\"\n"
            "- **Assignments**: \"Can P001 take PRJ002?\" or \"Best pilots for PRJ001\"\n"
            "- **Fleet status**: \"Show drone fleet\" or \"Available drones in Mumbai\"\n\n"
            "You can also switch to the **Dashboard**, **Data View**, and **Conflicts** tabs for a structured view."
        )

    def _respond_availability(self) -> str:
        summary = self.get_availability_summary()

        text = "📊 **Current Availability Overview**\n\n"

        # Pilots
        p = summary["pilots"]
        text += (
            f"👨‍✈️ **Pilots**\n"
            f"- Total: {p['total']}\n"
            f"- Available: {p['available']}\n"
            f"- Assigned: {p['assigned']}\n"
            f"- On Leave: {p['on_leave']}\n\n"
        )

        # Drones
        d = summary["drones"]
        text += (
            f"🚁 **Drones**\n"
            f"- Total: {d['total']}\n"
            f"- Available: {d['available']}\n"
            f"- Deployed: {d['deployed']}\n"
            f"- Maintenance: {d['maintenance']}\n\n"
        )

        # Missions
        m = summary["missions"]
        text += (
            f"📋 **Missions**\n"
            f"- Total: {m['total']}\n"
            f"- Active: {m['active']}\n"
            f"- Upcoming: {m['upcoming']}\n"
            f"- Urgent: {m['urgent']}\n"
        )

        return text

    def _respond_conflicts(self) -> str:
        conflicts = self.detect_all_conflicts()
        if not conflicts:
            return "✅ **No conflicts detected.** All pilots, drones, and missions look consistent."

        text = f"⚠️ **Detected {len(conflicts)} potential conflicts:**\n\n"

        for c in conflicts:
            text += f"- **{c['type']}** ({c.get('severity', 'Unknown')}): {c.get('description', '')}\n"
        text += "\n💡 Use the **Conflicts** tab for a structured, filterable view and suggestions."
        return text

    def _respond_urgent_missions(self) -> str:
        urgent = self.missions_df[self.missions_df["priority"] == "Urgent"]
        if urgent.empty:
            return "✅ **No missions marked as Urgent right now.**"

        text = f"🚨 **Urgent Missions & Suggested Reassignments ({len(urgent)})**\n\n"

        for _, mission in urgent.iterrows():
            text += (
                f"**{mission['project_id']} – {mission['client']}**  \n"
                f"- Location: {mission['location']}  \n"
                f"- Window: {mission['start_date'].date()} → {mission['end_date'].date()}  \n"
                f"- Required: {mission['required_skills']} | Certs: {mission['required_certs']}\n"
            )

            candidates = self.find_best_pilots(mission["project_id"], top_n=3)
            if not candidates:
                text += "  - ❌ No strong pilot matches available. Consider relaxing skill/location constraints.\n\n"
                continue

            text += "  - ✅ **Top Pilot Options:**\n"
            for c in candidates:
                reasons = "; ".join(c["reasons"])
                text += (
                    f"    - **{c['name']} ({c['pilot_id']})** – score {c['score']}  \n"
                    f"      {reasons}\n"
                )
            text += "\n"

        text += (
            "These are *recommendations only* – use the **Data Management** tab to commit any reassignments "
            "so they sync back to Google Sheets."
        )
        return text

    def _respond_mission_overview(self, q: str) -> str:
        # Try to extract an explicit mission ID like PRJ001
        match = re.search(r"prj\\d+", q)
        if match:
            mission_id = match.group().upper()
            info = self.get_mission_status(mission_id)
            if not info:
                return f"❌ Mission **{mission_id}** not found."

            text = f"📋 **Mission {info['project_id']} – {info['client']}**\n\n"
            text += (
                f"- Location: {info['location']}\n"
                f"- Window: {info['start_date']} → {info['end_date']}\n"
                f"- Priority: {info['priority']}\n"
                f"- Status: {info['status']}\n"
                f"- Required: {info['required_skills']} | Certs: {info['required_certs']}\n\n"
            )

            if info["assigned_pilots"]:
                text += "**Assigned pilots:**\n"
                for p in info["assigned_pilots"]:
                    text += (
                        f"- {p['name']} ({p['pilot_id']}) – {p['skills']} | {p['certifications']}\n"
                    )
            else:
                text += "❌ No pilots currently assigned.\n"

            return text

        # If no specific ID, return a short overview
        m = self.get_availability_summary()["missions"]
        return (
            "📋 **Mission Portfolio Overview**\n\n"
            f"- Total missions: {m['total']}\n"
            f"- Active: {m['active']}\n"
            f"- Upcoming: {m['upcoming']}\n"
            f"- Urgent: {m['urgent']}\n\n"
            "Ask about a specific mission ID, e.g. `PRJ001`, for more detail."
        )

    def _respond_assignment_intent(self, q: str) -> str:
        pilot_match = re.search(r"p\\d+", q)
        mission_match = re.search(r"prj\\d+", q)

        if not (pilot_match and mission_match):
            return (
                "ℹ️ To evaluate an assignment, mention both pilot and mission IDs, "
                "for example: `Can P001 take PRJ002?`"
            )

        pilot_id = pilot_match.group().upper()
        mission_id = mission_match.group().upper()

        # Check feasibility without committing any write back
        mission = self.missions_df[self.missions_df["project_id"] == mission_id]
        pilot = self.pilots_df[self.pilots_df["pilot_id"] == pilot_id]

        if mission.empty:
            return f"❌ Mission **{mission_id}** not found."
        if pilot.empty:
            return f"❌ Pilot **{pilot_id}** not found."

        mission = mission.iloc[0]
        pilot = pilot.iloc[0]

        missing_skills = [
            s for s in mission["required_skills_list"] if s not in pilot["skills_list"]
        ]
        missing_certs = [
            c for c in mission["required_certs_list"] if c not in pilot["certs_list"]
        ]

        issues = []
        if missing_skills:
            issues.append(f"- Missing skills: {', '.join(missing_skills)}")
        if missing_certs:
            issues.append(f"- Missing certifications: {', '.join(missing_certs)}")
        if pilot["location"] != mission["location"]:
            issues.append(
                f"- Location mismatch: pilot in {pilot['location']}, mission in {mission['location']}"
            )
        if pilot["status"] != "Available":
            msg = f"- Pilot status is {pilot['status']}"
            if pd.notna(pilot["current_assignment"]):
                msg += f" (currently on {pilot['current_assignment']})"
            issues.append(msg)

        if not issues:
            return (
                f"✅ **{pilot['name']} ({pilot_id}) is a good fit for {mission_id}.**\n\n"
                "All core checks (skills, certifications, location, status) look good. "
                "You can commit this via the **Data Management → Pilots** tab so it syncs back to Google Sheets."
            )

        text = (
            f"❌ **{pilot['name']} ({pilot_id}) is *not* an ideal fit for {mission_id}.**\n\n"
            "Issues detected:\n" + "\n".join(issues)
        )
        best = self.find_best_pilots(mission_id, top_n=3)
        if best:
            text += "\n\n💡 **Alternative pilot suggestions:**\n"
            for c in best:
                text += f"- {c['name']} ({c['pilot_id']}) – score {c['score']}\n"
        return text

    def _respond_pilot_roster(self) -> str:
        available = self.pilots_df[self.pilots_df["status"] == "Available"]
        if available.empty:
            return "👨‍✈️ **Pilot Roster**\n\nNo pilots are currently marked as Available."

        text = "👨‍✈️ **Pilot Roster – Available Pilots**\n\n"
        for _, p in available.iterrows():
            text += (
                f"- **{p['name']} ({p['pilot_id']})** – {p['skills']} | {p['certifications']}  \n"
                f"  Location: {p['location']} | Status: {p['status']}\n"
            )
        return text

    def _respond_drone_fleet(self) -> str:
        available = self.drones_df[self.drones_df["status"] == "Available"]
        maintenance = self.drones_df[self.drones_df["status"] == "Maintenance"]

        text = "🚁 **Drone Fleet Overview**\n\n"
        text += f"- Total drones: {len(self.drones_df)}\n"
        text += f"- Available: {len(available)}\n"
        text += f"- In maintenance: {len(maintenance)}\n\n"

        if not available.empty:
            text += "**Available drones:**\n"
            for _, d in available.iterrows():
                text += (
                    f"- {d['drone_id']} – {d['model']} ({d['capabilities']}) in {d['location']}\n"
                )

        if not maintenance.empty:
            text += "\n🔧 **Maintenance queue:**\n"
            for _, d in maintenance.iterrows():
                due = (
                    d["maintenance_due"].strftime("%Y-%m-%d")
                    if self._is_date_valid(d["maintenance_due"])
                    else "Unknown"
                )
                text += f"- {d['drone_id']} – {d['model']} (due {due})\n"

        return text