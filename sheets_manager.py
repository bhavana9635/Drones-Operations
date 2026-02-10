import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import os
import json

class SheetsManager:
    """Manages all Google Sheets operations with 2-way sync"""
    
    # Production Sheet IDs (you'll need to replace these with your actual sheet IDs)
    PILOT_SHEET_ID = "1WkJ2rXsFOz9_e2RPfpU97Je22SJ5Qj8lUvIr-8JVcgs"
    DRONE_SHEET_ID = "1nMlecMSQCCVA7ZbzJ0oiNLeEzvl2FY3-QMfccMNtb9g"
    MISSION_SHEET_ID = "1iRKQ_lat97zygd7g43bnHWKLh2UiPyja5NEmZG0EfKM"
    
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    
    def __init__(self):
        """Initialize Google Sheets connection"""
        self.client = self._get_client()
        self.pilots_df = None
        self.drones_df = None
        self.missions_df = None
        self.reload_data()
    
    def _get_client(self):
        """Authenticate and return gspread client"""
        # Try to load credentials from environment variable first (for deployment)
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        
        if creds_json:
            # Parse JSON from environment variable
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=self.SCOPES)
        elif os.path.exists("credentials.json"):
            # Load from file (for local development)
            creds = Credentials.from_service_account_file("credentials.json", scopes=self.SCOPES)
        else:
            raise Exception("No credentials found. Please set GOOGLE_CREDENTIALS_JSON environment variable or provide credentials.json file")
        
        return gspread.authorize(creds)
    
    def reload_data(self):
        """Reload all data from Google Sheets"""
        self.pilots_df = self._read_sheet(self.PILOT_SHEET_ID, "pilot_roster.csv")
        self.drones_df = self._read_sheet(self.DRONE_SHEET_ID, "drone_fleet.csv")
        self.missions_df = self._read_sheet(self.MISSION_SHEET_ID, "missions.csv")
    
    def _read_sheet(self, sheet_id, tab_name):
        """Read a specific sheet and return as DataFrame"""
        try:
            sheet = self.client.open_by_key(sheet_id).worksheet(tab_name)
            data = sheet.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            # Try to find the correct worksheet name
            try:
                spreadsheet = self.client.open_by_key(sheet_id)
                available_sheets = [ws.title for ws in spreadsheet.worksheets()]
                
                # If only one sheet, use it
                if len(available_sheets) == 1:
                    sheet = spreadsheet.worksheet(available_sheets[0])
                    data = sheet.get_all_records()
                    return pd.DataFrame(data)
                else:
                    raise Exception(f"Worksheet '{tab_name}' not found. Available: {available_sheets}")
            except Exception as inner_e:
                raise Exception(f"Error reading sheet {sheet_id}: {str(inner_e)}")
    
    def update_pilot_status(self, pilot_id, new_status, current_assignment=None, available_from=None):
        """
        Update pilot status in Google Sheet
        Returns: True if successful, False otherwise
        """
        try:
            sheet = self.client.open_by_key(self.PILOT_SHEET_ID).worksheet("pilot_roster.csv")
            
            # Get all values
            all_values = sheet.get_all_values()
            headers = all_values[0]
            
            # Find column indices
            pilot_id_col = headers.index('pilot_id') if 'pilot_id' in headers else 0
            status_col = headers.index('status') if 'status' in headers else 5
            assignment_col = headers.index('current_assignment') if 'current_assignment' in headers else 6
            available_col = headers.index('available_from') if 'available_from' in headers else 7
            
            # Find the pilot row
            for idx, row in enumerate(all_values[1:], start=2):  # Start from row 2 (skip header)
                if len(row) > pilot_id_col and row[pilot_id_col] == pilot_id:
                    # Update status
                    sheet.update_cell(idx, status_col + 1, new_status)
                    
                    # Update current assignment if provided
                    if current_assignment is not None:
                        sheet.update_cell(idx, assignment_col + 1, current_assignment if current_assignment else '–')
                    
                    # Update available_from if provided
                    if available_from is not None:
                        sheet.update_cell(idx, available_col + 1, available_from)
                    
                    # Reload data
                    self.reload_data()
                    return True
            
            return False  # Pilot not found
            
        except Exception as e:
            print(f"Error updating pilot status: {str(e)}")
            return False
    
    def update_drone_status(self, drone_id, new_status, current_assignment=None):
        """
        Update drone status in Google Sheet
        Returns: True if successful, False otherwise
        """
        try:
            sheet = self.client.open_by_key(self.DRONE_SHEET_ID).worksheet("drone_fleet.csv")
            
            # Get all values
            all_values = sheet.get_all_values()
            headers = all_values[0]
            
            # Find column indices
            drone_id_col = headers.index('drone_id') if 'drone_id' in headers else 0
            status_col = headers.index('status') if 'status' in headers else 3
            assignment_col = headers.index('current_assignment') if 'current_assignment' in headers else 5
            
            # Find the drone row
            for idx, row in enumerate(all_values[1:], start=2):  # Start from row 2 (skip header)
                if len(row) > drone_id_col and row[drone_id_col] == drone_id:
                    # Update status
                    sheet.update_cell(idx, status_col + 1, new_status)
                    
                    # Update current assignment if provided
                    if current_assignment is not None:
                        sheet.update_cell(idx, assignment_col + 1, current_assignment if current_assignment else '–')
                    
                    # Reload data
                    self.reload_data()
                    return True
            
            return False  # Drone not found
            
        except Exception as e:
            print(f"Error updating drone status: {str(e)}")
            return False
    
    def get_available_pilots(self, skill=None, location=None, certification=None):
        """Find available pilots matching criteria"""
        df = self.pilots_df[self.pilots_df['status'] == 'Available'].copy()
        
        if skill:
            df = df[df['skills'].str.contains(skill, case=False, na=False)]
        
        if location:
            df = df[df['location'] == location]
        
        if certification:
            df = df[df['certifications'].str.contains(certification, case=False, na=False)]
        
        return df
    
    def get_available_drones(self, capability=None, location=None):
        """Find available drones matching criteria"""
        df = self.drones_df[self.drones_df['status'] == 'Available'].copy()
        
        if capability:
            df = df[df['capabilities'].str.contains(capability, case=False, na=False)]
        
        if location:
            df = df[df['location'] == location]
        
        return df
    
    def assign_pilot_to_mission(self, pilot_id, mission_id, available_from_date):
        """Assign a pilot to a mission"""
        return self.update_pilot_status(
            pilot_id=pilot_id,
            new_status="Assigned",
            current_assignment=mission_id,
            available_from=available_from_date
        )
    
    def unassign_pilot(self, pilot_id):
        """Make a pilot available again"""
        from datetime import datetime
        return self.update_pilot_status(
            pilot_id=pilot_id,
            new_status="Available",
            current_assignment="–",
            available_from=datetime.now().strftime("%Y-%m-%d")
        )

    # --------- Create / Delete operations (records) ---------

    def add_pilot(self, pilot_data):
        """
        Append a new pilot to the pilot_roster sheet.
        `pilot_data` should be a dict keyed by column name
        (e.g. pilot_id, name, skills, certifications, location, status, current_assignment, available_from).
        """
        try:
            sheet = self.client.open_by_key(self.PILOT_SHEET_ID).worksheet("pilot_roster.csv")
            headers = sheet.row_values(1)

            # Build row in the same order as the sheet headers
            row = [str(pilot_data.get(col, "")) for col in headers]
            sheet.append_row(row)

            self.reload_data()
            return True
        except Exception as e:
            print(f"Error adding pilot: {str(e)}")
            return False

    def add_drone(self, drone_data):
        """
        Append a new drone to the drone_fleet sheet.
        `drone_data` should be a dict keyed by column name
        (e.g. drone_id, model, capabilities, status, location, current_assignment, maintenance_due).
        """
        try:
            sheet = self.client.open_by_key(self.DRONE_SHEET_ID).worksheet("drone_fleet.csv")
            headers = sheet.row_values(1)

            row = [str(drone_data.get(col, "")) for col in headers]
            sheet.append_row(row)

            self.reload_data()
            return True
        except Exception as e:
            print(f"Error adding drone: {str(e)}")
            return False

    def delete_pilot(self, pilot_id):
        """Delete a pilot row by pilot_id."""
        try:
            sheet = self.client.open_by_key(self.PILOT_SHEET_ID).worksheet("pilot_roster.csv")
            all_values = sheet.get_all_values()
            headers = all_values[0]
            pilot_id_col = headers.index("pilot_id") if "pilot_id" in headers else 0

            for idx, row in enumerate(all_values[1:], start=2):
                if len(row) > pilot_id_col and row[pilot_id_col] == pilot_id:
                    sheet.delete_rows(idx)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print(f"Error deleting pilot: {str(e)}")
            return False

    def delete_drone(self, drone_id):
        """Delete a drone row by drone_id."""
        try:
            sheet = self.client.open_by_key(self.DRONE_SHEET_ID).worksheet("drone_fleet.csv")
            all_values = sheet.get_all_values()
            headers = all_values[0]
            drone_id_col = headers.index("drone_id") if "drone_id" in headers else 0

            for idx, row in enumerate(all_values[1:], start=2):
                if len(row) > drone_id_col and row[drone_id_col] == drone_id:
                    sheet.delete_rows(idx)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print(f"Error deleting drone: {str(e)}")
            return False

    def add_mission(self, mission_data):
        """
        Append a new mission to the missions sheet.
        `mission_data` keys should match the missions header
        (e.g. project_id, client, location, required_skills, required_certs, start_date, end_date, priority).
        """
        try:
            sheet = self.client.open_by_key(self.MISSION_SHEET_ID).worksheet("missions.csv")
            headers = sheet.row_values(1)
            row = [str(mission_data.get(col, "")) for col in headers]
            sheet.append_row(row)
            self.reload_data()
            return True
        except Exception as e:
            print(f"Error adding mission: {str(e)}")
            return False

    def delete_mission(self, project_id):
        """Delete a mission row by project_id."""
        try:
            sheet = self.client.open_by_key(self.MISSION_SHEET_ID).worksheet("missions.csv")
            all_values = sheet.get_all_values()
            headers = all_values[0]
            proj_col = headers.index("project_id") if "project_id" in headers else 0

            for idx, row in enumerate(all_values[1:], start=2):
                if len(row) > proj_col and row[proj_col] == project_id:
                    sheet.delete_rows(idx)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print(f"Error deleting mission: {str(e)}")
            return False

    def update_mission(self, project_id, updates: dict):
        """
        Update one or more fields for a mission identified by project_id.
        `updates` is a dict of column_name -> new_value.
        """
        try:
            sheet = self.client.open_by_key(self.MISSION_SHEET_ID).worksheet("missions.csv")
            all_values = sheet.get_all_values()
            headers = all_values[0]
            proj_col = headers.index("project_id") if "project_id" in headers else 0

            for idx, row in enumerate(all_values[1:], start=2):
                if len(row) > proj_col and row[proj_col] == project_id:
                    for col_name, value in updates.items():
                        if col_name in headers:
                            col_idx = headers.index(col_name) + 1
                            sheet.update_cell(idx, col_idx, value)
                    self.reload_data()
                    return True
            return False
        except Exception as e:
            print(f"Error updating mission: {str(e)}")
            return False