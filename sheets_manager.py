import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime


class SheetsManager:
    """Manages all Google Sheets operations with 2-way sync"""

    # Google Sheet IDs
    PILOT_SHEET_ID = "1WkJ2rXsFOz9_e2RPfpU97Je22SJ5Qj8lUvIr-8JVcgs"
    DRONE_SHEET_ID = "1nMlecMSQCCVA7ZbzJ0oiNLeEzvl2FY3-QMfccMNtb9g"
    MISSION_SHEET_ID = "1iRKQ_lat97zygd7g43bnHWKLh2UiPyja5NEmZG0EfKM"

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self):
        self.client = self._get_client()
        self.pilots_df = None
        self.drones_df = None
        self.missions_df = None
        self.reload_data()

    # ---------------- AUTH ----------------

    def _get_client(self):
        """Authenticate using Streamlit Secrets"""
        try:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=self.SCOPES
            )
            return gspread.authorize(creds)
        except Exception as e:
            raise RuntimeError(
                "Failed to initialize Google Sheets connection. "
                "Check Streamlit Secrets configuration."
            ) from e

    # ---------------- READ ----------------

    def reload_data(self):
        self.pilots_df = self._read_sheet(self.PILOT_SHEET_ID, "pilot_roster.csv")
        self.drones_df = self._read_sheet(self.DRONE_SHEET_ID, "drone_fleet.csv")
        self.missions_df = self._read_sheet(self.MISSION_SHEET_ID, "missions.csv")

    def _read_sheet(self, sheet_id, tab_name):
        try:
            sheet = self.client.open_by_key(sheet_id).worksheet(tab_name)
            return pd.DataFrame(sheet.get_all_records())
        except Exception:
            spreadsheet = self.client.open_by_key(sheet_id)
            sheets = spreadsheet.worksheets()

            if len(sheets) == 1:
                return pd.DataFrame(sheets[0].get_all_records())

            raise RuntimeError(
                f"Worksheet '{tab_name}' not found. "
                f"Available sheets: {[s.title for s in sheets]}"
            )

    # ---------------- UPDATE STATUS ----------------

    def update_pilot_status(self, pilot_id, new_status,
                            current_assignment=None, available_from=None):
        try:
            sheet = self.client.open_by_key(self.PILOT_SHEET_ID).worksheet("pilot_roster.csv")
            values = sheet.get_all_values()
            headers = values[0]

            pid_col = headers.index("pilot_id")
            status_col = headers.index("status")
            assign_col = headers.index("current_assignment")
            avail_col = headers.index("available_from")

            for idx, row in enumerate(values[1:], start=2):
                if row[pid_col] == pilot_id:
                    sheet.update_cell(idx, status_col + 1, new_status)
                    if current_assignment is not None:
                        sheet.update_cell(idx, assign_col + 1, current_assignment)
                    if available_from is not None:
                        sheet.update_cell(idx, avail_col + 1, available_from)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print("Pilot update failed:", e)
            return False

    def update_drone_status(self, drone_id, new_status, current_assignment=None):
        try:
            sheet = self.client.open_by_key(self.DRONE_SHEET_ID).worksheet("drone_fleet.csv")
            values = sheet.get_all_values()
            headers = values[0]

            did_col = headers.index("drone_id")
            status_col = headers.index("status")
            assign_col = headers.index("current_assignment")

            for idx, row in enumerate(values[1:], start=2):
                if row[did_col] == drone_id:
                    sheet.update_cell(idx, status_col + 1, new_status)
                    if current_assignment is not None:
                        sheet.update_cell(idx, assign_col + 1, current_assignment)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print("Drone update failed:", e)
            return False

    # ---------------- QUERY ----------------

    def get_available_pilots(self, skill=None, location=None, certification=None):
        df = self.pilots_df[self.pilots_df["status"] == "Available"].copy()

        if skill:
            df = df[df["skills"].str.contains(skill, case=False, na=False)]
        if location:
            df = df[df["location"] == location]
        if certification:
            df = df[df["certifications"].str.contains(certification, case=False, na=False)]

        return df

    def get_available_drones(self, capability=None, location=None):
        df = self.drones_df[self.drones_df["status"] == "Available"].copy()

        if capability:
            df = df[df["capabilities"].str.contains(capability, case=False, na=False)]
        if location:
            df = df[df["location"] == location]

        return df

    # ---------------- ASSIGN / UNASSIGN ----------------

    def assign_pilot_to_mission(self, pilot_id, mission_id, available_from):
        return self.update_pilot_status(
            pilot_id,
            "Assigned",
            current_assignment=mission_id,
            available_from=available_from
        )

    def unassign_pilot(self, pilot_id):
        return self.update_pilot_status(
            pilot_id,
            "Available",
            current_assignment="–",
            available_from=datetime.now().strftime("%Y-%m-%d")
        )

    # ---------------- CREATE ----------------

    def add_pilot(self, pilot_data):
        return self._append_row(self.PILOT_SHEET_ID, "pilot_roster.csv", pilot_data)

    def add_drone(self, drone_data):
        return self._append_row(self.DRONE_SHEET_ID, "drone_fleet.csv", drone_data)

    def add_mission(self, mission_data):
        return self._append_row(self.MISSION_SHEET_ID, "missions.csv", mission_data)

    def _append_row(self, sheet_id, tab_name, data):
        try:
            sheet = self.client.open_by_key(sheet_id).worksheet(tab_name)
            headers = sheet.row_values(1)
            row = [str(data.get(col, "")) for col in headers]
            sheet.append_row(row)
            self.reload_data()
            return True
        except Exception as e:
            print("Append failed:", e)
            return False

    # ---------------- DELETE ----------------

    def delete_pilot(self, pilot_id):
        return self._delete_row(self.PILOT_SHEET_ID, "pilot_roster.csv", "pilot_id", pilot_id)

    def delete_drone(self, drone_id):
        return self._delete_row(self.DRONE_SHEET_ID, "drone_fleet.csv", "drone_id", drone_id)

    def delete_mission(self, project_id):
        return self._delete_row(self.MISSION_SHEET_ID, "missions.csv", "project_id", project_id)

    def _delete_row(self, sheet_id, tab_name, key_col, key_val):
        try:
            sheet = self.client.open_by_key(sheet_id).worksheet(tab_name)
            values = sheet.get_all_values()
            headers = values[0]
            key_index = headers.index(key_col)

            for idx, row in enumerate(values[1:], start=2):
                if row[key_index] == key_val:
                    sheet.delete_rows(idx)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print("Delete failed:", e)
            return False
