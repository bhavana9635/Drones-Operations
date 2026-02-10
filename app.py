import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
from sheets_manager import SheetsManager
from agent_logic import DroneOpsAgent
import os

# Page configuration
st.set_page_config(
    page_title="Skylark Drones - Operations Coordinator AI",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E40AF;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #6B7280;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3B82F6;
    }
    .conflict-card {
        background-color: #FEE2E2;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #EF4444;
        margin-bottom: 1rem;
    }
    .success-card {
        background-color: #D1FAE5;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #10B981;
        margin-bottom: 1rem;
    }

    /* Chat message styling for clearer AI answers */
    [data-testid="stChatMessage"] {
        background-color: #F9FAFB;
        border-radius: 0.75rem;
        padding: 0.75rem 1rem;
        border: 1px solid #E5E7EB;
        max-width: 900px;
    }
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] strong {
        color: #111827 !important;  /* dark text for good contrast */
        font-size: 0.95rem;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'sheets_manager' not in st.session_state:
    try:
        st.session_state.sheets_manager = SheetsManager()
        st.session_state.agent = DroneOpsAgent(st.session_state.sheets_manager)
    except Exception as e:
        st.error(f"⚠️ Failed to initialize Google Sheets connection: {str(e)}")
        st.stop()

if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

# Header
st.markdown('<div class="main-header">🚁 Skylark Drones Operations Coordinator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Drone Fleet & Pilot Management System</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("📊 System Status")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        with st.spinner("Syncing with Google Sheets..."):
            st.session_state.sheets_manager.reload_data()
            st.session_state.agent = DroneOpsAgent(st.session_state.sheets_manager)
            st.session_state.data_loaded = True
            st.success("✅ Data refreshed!")
    
    st.divider()
    
    # Load data for sidebar metrics
    if st.session_state.sheets_manager:
        pilots_df = st.session_state.sheets_manager.pilots_df
        drones_df = st.session_state.sheets_manager.drones_df
        missions_df = st.session_state.sheets_manager.missions_df
        
        st.subheader("👨‍✈️ Pilots")
        st.metric("Total", len(pilots_df))
        st.metric("Available", len(pilots_df[pilots_df['status'] == 'Available']))
        st.metric("Assigned", len(pilots_df[pilots_df['status'] == 'Assigned']))
        st.metric("On Leave", len(pilots_df[pilots_df['status'] == 'On Leave']))
        
        st.divider()
        
        st.subheader("🚁 Drones")
        st.metric("Total", len(drones_df))
        st.metric("Available", len(drones_df[drones_df['status'] == 'Available']))
        st.metric("Deployed", len(drones_df[drones_df['status'] == 'Deployed']))
        st.metric("Maintenance", len(drones_df[drones_df['status'] == 'Maintenance']))
        
        st.divider()
        
        st.subheader("📋 Missions")
        today = datetime.now().date()
        active_missions = missions_df[
            (pd.to_datetime(missions_df['start_date']).dt.date <= today) &
            (pd.to_datetime(missions_df['end_date']).dt.date >= today)
        ]
        urgent_missions = missions_df[missions_df['priority'] == 'Urgent']
        
        st.metric("Total", len(missions_df))
        st.metric("Active", len(active_missions))
        st.metric("Urgent", len(urgent_missions))
        
        # Detect conflicts
        conflicts = st.session_state.agent.detect_all_conflicts()
        if conflicts:
            st.divider()
            st.subheader("⚠️ Conflicts")
            st.metric("Total Issues", len(conflicts))
            high_severity = len([c for c in conflicts if c.get('severity') == 'high'])
            if high_severity > 0:
                st.error(f"🔴 {high_severity} High Priority")

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["💬 AI Assistant", "📊 Dashboard", "📋 Data View", "⚠️ Conflicts"])

with tab1:
    st.header("Chat with AI Operations Coordinator")
    
    # Quick action buttons (send question + auto-run AI response)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔍 Check Availability", use_container_width=True):
            prompt = "Who is available for missions right now?"
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("🤔 Checking availability..."):
                response = st.session_state.agent.process_query(prompt)
                st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    with col2:
        if st.button("⚠️ Show Conflicts", use_container_width=True):
            prompt = "Show me all current conflicts and issues"
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("🔎 Scanning for conflicts..."):
                response = st.session_state.agent.process_query(prompt)
                st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    with col3:
        if st.button("🚨 Urgent Missions", use_container_width=True):
            prompt = "Are there any urgent missions that need attention?"
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("🚨 Analyzing urgent missions..."):
                response = st.session_state.agent.process_query(prompt)
                st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    with col4:
        if st.button("📍 Location Check", use_container_width=True):
            prompt = "Check for any location mismatches"
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("📍 Checking locations..."):
                response = st.session_state.agent.process_query(prompt)
                st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    st.divider()
    
    # Chat container
    chat_container = st.container()
    
    with chat_container:
        # Display chat messages in a clean, chat-style layout
        for message in st.session_state.messages:
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(message["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(message["content"])
    
    # Chat input
    user_input = st.chat_input("Ask me anything about pilots, drones, missions, or assignments...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Get AI response
        with st.spinner("🤔 Thinking..."):
            response = st.session_state.agent.process_query(user_input)
            st.session_state.messages.append({"role": "assistant", "content": response})
        
        st.rerun()

with tab2:
    st.header("📊 Operations Dashboard")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👨‍✈️ Pilot Overview")
        pilots_df = st.session_state.sheets_manager.pilots_df
        
        # Status distribution
        status_counts = pilots_df['status'].value_counts()
        st.bar_chart(status_counts)
        
        # Location distribution
        st.subheader("📍 Pilots by Location")
        location_counts = pilots_df['location'].value_counts()
        st.bar_chart(location_counts)
    
    with col2:
        st.subheader("🚁 Drone Fleet Status")
        drones_df = st.session_state.sheets_manager.drones_df
        
        # Status distribution
        drone_status = drones_df['status'].value_counts()
        st.bar_chart(drone_status)
        
        # Model distribution
        st.subheader("🔧 Fleet by Model")
        model_counts = drones_df['model'].value_counts()
        st.bar_chart(model_counts)
    
    st.divider()
    
    # Upcoming missions timeline
    st.subheader("📅 Upcoming Missions")
    missions_df = st.session_state.sheets_manager.missions_df
    upcoming = missions_df.copy()
    upcoming['start_date'] = pd.to_datetime(upcoming['start_date'], errors='coerce')
    upcoming = upcoming.sort_values('start_date')
    
    for idx, mission in upcoming.iterrows():
        priority_color = {
            'Urgent': '🔴',
            'High': '🟠',
            'Standard': '🟢'
        }.get(mission['priority'], '⚪')

        start_val = mission['start_date']
        if pd.notna(start_val):
            start_str = start_val.strftime('%Y-%m-%d')
        else:
            start_str = "Unknown"
        
        st.markdown(f"""
        **{priority_color} {mission['project_id']}** - {mission['client']}  
        📍 {mission['location']} | 📅 {start_str} to {mission['end_date']}  
        🎯 Required: {mission['required_skills']} | 📜 Certs: {mission['required_certs']}
        """)
        st.divider()

with tab3:
    st.header("📋 Data Management")
    
    view_tab1, view_tab2, view_tab3 = st.tabs(["Pilots", "Drones", "Missions"])
    
    with view_tab1:
        st.subheader("👨‍✈️ Pilot Roster")
        pilots_df = st.session_state.sheets_manager.pilots_df
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.multiselect("Filter by Status", pilots_df['status'].unique(), default=None)
        with col2:
            location_filter = st.multiselect("Filter by Location", pilots_df['location'].unique(), default=None)
        with col3:
            search = st.text_input("Search by name or skills")
        
        # Apply filters
        filtered_df = pilots_df.copy()
        if status_filter:
            filtered_df = filtered_df[filtered_df['status'].isin(status_filter)]
        if location_filter:
            filtered_df = filtered_df[filtered_df['location'].isin(location_filter)]
        if search:
            filtered_df = filtered_df[
                filtered_df['name'].str.contains(search, case=False, na=False) |
                filtered_df['skills'].str.contains(search, case=False, na=False)
            ]
        
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        # Quick update section
        st.subheader("⚡ Quick Status Update")
        col1, col2, col3 = st.columns(3)
        with col1:
            pilot_to_update = st.selectbox("Select Pilot", pilots_df['pilot_id'].tolist())
        with col2:
            new_status = st.selectbox("New Status", ['Available', 'Assigned', 'On Leave'])
        with col3:
            st.write("")
            st.write("")
            if st.button("Update Status", use_container_width=True):
                success = st.session_state.sheets_manager.update_pilot_status(
                    pilot_to_update, new_status
                )
                if success:
                    st.success(f"✅ Updated {pilot_to_update} to {new_status}")
                    st.rerun()
                else:
                    st.error("❌ Update failed")

        st.subheader("➕ Add New Pilot")
        col1, col2 = st.columns(2)
        with col1:
            new_pilot_id = st.text_input("Pilot ID (e.g., P010)", key="add_pilot_id")
            new_pilot_name = st.text_input("Name", key="add_pilot_name")
            new_pilot_location = st.text_input("Location", key="add_pilot_location")
            new_pilot_status = st.selectbox("Status", ["Available", "Assigned", "On Leave"], index=0)
        with col2:
            new_pilot_skills = st.text_input("Skills (comma-separated)", key="add_pilot_skills")
            new_pilot_certs = st.text_input("Certifications (comma-separated)", key="add_pilot_certs")
            new_pilot_assignment = st.text_input(
                "Current Assignment (optional)", value="–", key="add_pilot_assignment"
            )
            new_pilot_available_from = st.text_input(
                "Available From (YYYY-MM-DD)", value="", key="add_pilot_available_from"
            )

        if st.button("Add Pilot", use_container_width=True):
            if not new_pilot_id or not new_pilot_name:
                st.error("Please provide at least Pilot ID and Name.")
            else:
                success = st.session_state.sheets_manager.add_pilot(
                    {
                        "pilot_id": new_pilot_id,
                        "name": new_pilot_name,
                        "skills": new_pilot_skills,
                        "certifications": new_pilot_certs,
                        "location": new_pilot_location,
                        "status": new_pilot_status,
                        "current_assignment": new_pilot_assignment or "–",
                        "available_from": new_pilot_available_from,
                    }
                )
                if success:
                    st.success(f"✅ Added pilot {new_pilot_id}")
                    st.rerun()
                else:
                    st.error("❌ Failed to add pilot")

        st.subheader("🗑️ Delete Pilot")
        del_pilot_id = st.selectbox("Select Pilot to Delete", pilots_df["pilot_id"].tolist())
        if st.button("Delete Pilot", use_container_width=True):
            confirm = st.checkbox("Confirm delete this pilot (cannot be undone)", value=False, key="confirm_delete_pilot")
            if not confirm:
                st.error("Please tick the confirmation checkbox before deleting.")
            else:
                success = st.session_state.sheets_manager.delete_pilot(del_pilot_id)
                if success:
                    st.success(f"✅ Deleted pilot {del_pilot_id}")
                    st.rerun()
                else:
                    st.error("❌ Failed to delete pilot")
    
    with view_tab2:
        st.subheader("🚁 Drone Fleet")
        drones_df = st.session_state.sheets_manager.drones_df
        st.dataframe(drones_df, use_container_width=True, hide_index=True)
        
        # Quick update section
        st.subheader("⚡ Quick Status Update")
        col1, col2, col3 = st.columns(3)
        with col1:
            drone_to_update = st.selectbox("Select Drone", drones_df['drone_id'].tolist())
        with col2:
            new_drone_status = st.selectbox("New Status", ['Available', 'Deployed', 'Maintenance'])
        with col3:
            st.write("")
            st.write("")
            if st.button("Update Drone Status", use_container_width=True):
                success = st.session_state.sheets_manager.update_drone_status(
                    drone_to_update, new_drone_status
                )
                if success:
                    st.success(f"✅ Updated {drone_to_update} to {new_drone_status}")
                    st.rerun()
                else:
                    st.error("❌ Update failed")

        st.subheader("➕ Add New Drone")
        col1, col2 = st.columns(2)
        with col1:
            new_drone_id = st.text_input("Drone ID (e.g., D010)", key="add_drone_id")
            new_drone_model = st.text_input("Model", key="add_drone_model")
            new_drone_location = st.text_input("Location", key="add_drone_location")
            new_drone_status = st.selectbox("Drone Status", ["Available", "Deployed", "Maintenance"], index=0)
        with col2:
            new_drone_capabilities = st.text_input(
                "Capabilities (comma-separated)", key="add_drone_capabilities"
            )
            new_drone_assignment = st.text_input(
                "Current Assignment (optional)", value="–", key="add_drone_assignment"
            )
            new_drone_maint_due = st.text_input(
                "Maintenance Due (YYYY-MM-DD)", value="", key="add_drone_maint_due"
            )

        if st.button("Add Drone", use_container_width=True):
            if not new_drone_id or not new_drone_model:
                st.error("Please provide at least Drone ID and Model.")
            else:
                success = st.session_state.sheets_manager.add_drone(
                    {
                        "drone_id": new_drone_id,
                        "model": new_drone_model,
                        "capabilities": new_drone_capabilities,
                        "status": new_drone_status,
                        "location": new_drone_location,
                        "current_assignment": new_drone_assignment or "–",
                        "maintenance_due": new_drone_maint_due,
                    }
                )
                if success:
                    st.success(f"✅ Added drone {new_drone_id}")
                    st.rerun()
                else:
                    st.error("❌ Failed to add drone")

        st.subheader("🗑️ Delete Drone")
        del_drone_id = st.selectbox("Select Drone to Delete", drones_df["drone_id"].tolist())
        if st.button("Delete Drone", use_container_width=True):
            confirm_d = st.checkbox("Confirm delete this drone (cannot be undone)", value=False, key="confirm_delete_drone")
            if not confirm_d:
                st.error("Please tick the confirmation checkbox before deleting.")
            else:
                success = st.session_state.sheets_manager.delete_drone(del_drone_id)
                if success:
                    st.success(f"✅ Deleted drone {del_drone_id}")
                    st.rerun()
                else:
                    st.error("❌ Failed to delete drone")

    with view_tab3:
        st.subheader("📋 Missions")
        missions_df = st.session_state.sheets_manager.missions_df
        st.dataframe(missions_df, use_container_width=True, hide_index=True)

        st.subheader("➕ Add New Mission")
        col1, col2 = st.columns(2)
        with col1:
            new_proj_id = st.text_input("Project ID (e.g., PRJ010)", key="add_mission_id")
            new_client = st.text_input("Client Name", key="add_mission_client")
            new_location = st.text_input("Location", key="add_mission_location")
            new_priority = st.selectbox("Priority", ["Urgent", "High", "Standard"], index=2)
        with col2:
            new_req_skills = st.text_input(
                "Required Skills (comma-separated)", key="add_mission_skills"
            )
            new_req_certs = st.text_input(
                "Required Certs (comma-separated)", key="add_mission_certs"
            )
            new_start = st.text_input(
                "Start Date (YYYY-MM-DD)", value="", key="add_mission_start"
            )
            new_end = st.text_input(
                "End Date (YYYY-MM-DD)", value="", key="add_mission_end"
            )

        if st.button("Add Mission", use_container_width=True):
            if not new_proj_id or not new_client:
                st.error("Please provide at least Project ID and Client name.")
            else:
                success = st.session_state.sheets_manager.add_mission(
                    {
                        "project_id": new_proj_id,
                        "client": new_client,
                        "location": new_location,
                        "required_skills": new_req_skills,
                        "required_certs": new_req_certs,
                        "start_date": new_start,
                        "end_date": new_end,
                        "priority": new_priority,
                    }
                )
                if success:
                    st.success(f"✅ Added mission {new_proj_id}")
                    st.rerun()
                else:
                    st.error("❌ Failed to add mission")

        st.subheader("🗑️ Delete Mission")
        del_proj_id = st.selectbox("Select Mission to Delete", missions_df["project_id"].tolist())
        if st.button("Delete Mission", use_container_width=True):
            confirm_m = st.checkbox("Confirm delete this mission (cannot be undone)", value=False, key="confirm_delete_mission")
            if not confirm_m:
                st.error("Please tick the confirmation checkbox before deleting.")
            else:
                success = st.session_state.sheets_manager.delete_mission(del_proj_id)
                if success:
                    st.success(f"✅ Deleted mission {del_proj_id}")
                    st.rerun()
                else:
                    st.error("❌ Failed to delete mission")

with tab4:
    st.header("⚠️ Conflict Detection & Resolution")
    
    conflicts = st.session_state.agent.detect_all_conflicts()
    
    if not conflicts:
        st.success("✅ No conflicts detected! All systems operational.")
    else:
        st.error(f"🚨 {len(conflicts)} conflicts detected")
        
        # Group by severity
        high_severity = [c for c in conflicts if c.get('severity') == 'high']
        medium_severity = [c for c in conflicts if c.get('severity') == 'medium']
        low_severity = [c for c in conflicts if c.get('severity') == 'low']
        
        if high_severity:
            st.subheader("🔴 High Severity Issues")
            for conflict in high_severity:
                with st.expander(f"{conflict['type'].replace('_', ' ').title()}", expanded=True):
                    st.markdown(f'<div class="conflict-card">', unsafe_allow_html=True)
                    st.json(conflict)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    if conflict['type'] == 'skill_mismatch':
                        st.info(f"💡 **Suggestion**: Find alternative pilots with required skills: {', '.join(conflict.get('missing_skills', []))}")
                    elif conflict['type'] == 'double_booking':
                        st.info("💡 **Suggestion**: Reassign one of the conflicting missions to another available pilot")
        
        if medium_severity:
            st.subheader("🟡 Medium Severity Issues")
            for conflict in medium_severity:
                with st.expander(f"{conflict['type'].replace('_', ' ').title()}"):
                    st.json(conflict)
        
        if low_severity:
            st.subheader("🟢 Low Severity Issues")
            for conflict in low_severity:
                with st.expander(f"{conflict['type'].replace('_', ' ').title()}"):
                    st.json(conflict)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #6B7280; padding: 1rem;'>
    <strong>Skylark Drones Operations Coordinator AI</strong><br>
    Built with Streamlit | Powered by Google Sheets Integration
</div>
""", unsafe_allow_html=True)