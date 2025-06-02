"""IRIDM Disaster Management Streamlit Application\n=================================================\nThis Streamlit application is a proof‑of‑concept Disaster‑Management (DM) assistant\nfor **Indian Railways Institute of Disaster Management (IRIDM), Bengaluru**.\nIt focuses on Fire emergencies but is architected so that Natural / Man‑made\ndisasters and additional emergency types can be plugged‑in later.\n\n🚀 **Quick start**\n------------------\n1. ```bash\n   # in a clean venv\n   pip install streamlit geopy pandas pydeck==0.8.0 pillow\n   streamlit run iridm_dm_app.py\n   ```\n2. Place the campus site‑layout image in the same folder and name it\n   `iridm_site_layout.png` (or change `SITE_LAYOUT_PATH`).\n3. Optional: drop a CSV named `fire_stations.csv` with columns\n   `name,latitude,longitude,phone` to override the built‑in sample list.\n\nNOTE: Coordinates used here are **illustrative**. Please replace them with\naccurate GPS data for IRIDM campus features and nearby fire stations.\n"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st
from geopy.distance import geodesic
import pydeck as pdk

###############################################################################
# -----------------------  CONFIG & CONSTANTS  ------------------------------ #
###############################################################################

# Campus centroid (approx.) – replace with surveyed coordinates
IRIDM_LAT, IRIDM_LON = 12.9076, 77.4329  # Kanminike, Mysuru Road, Bengaluru

# Relative path to the schematic layout image shipped with the app
SITE_LAYOUT_PATH = Path(__file__).with_name("iridm_site_layout.png.png")

# Default fire‑station sample list (replace with authoritative data)
DEFAULT_FIRE_STATIONS = [
    {
        "name": "Kengeri Fire Station",
        "latitude": 12.9133,
        "longitude": 77.4488,
        "phone": "+918022851049",
    },
    {
        "name": "Ram Nagar Fire Station",
        "latitude": 12.9225,
        "longitude": 77.5051,
        "phone": "+918022917567",
    },
]

# Campus POIs (add more as required)
CAMPUS_LOCATIONS = [
    {
        "name": "Admin Block",
        "latitude": 12.9079,
        "longitude": 77.4332,
        "evac_path": [  # poly‑line of waypoints  (lat, lon)
            (12.9080, 77.4330),
            (12.9082, 77.4324),
            (12.9076, 77.4321),
        ],
        "extinguishers": [
            (12.90795, 77.43305),
            (12.90805, 77.43285),
        ],
    },
    {
        "name": "Hostel",
        "latitude": 12.9074,
        "longitude": 77.4326,
        "evac_path": [
            (12.9075, 77.4325),
            (12.9078, 77.4320),
        ],
        "extinguishers": [
            (12.90745, 77.43255),
        ],
    },
]

AVG_FIRE_TRUCK_SPEED_KMPH = 40  # crude assumption for ETA calculations

# File that persists incident logs between sessions
LOG_FILE = Path(__file__).with_name("incident_log.csv")

###############################################################################
# -------------------  INITIALISATION & HELPERS  ---------------------------- #
###############################################################################

def load_fire_station_df() -> pd.DataFrame:
    csv_path = Path("fire_stations.csv")
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame(DEFAULT_FIRE_STATIONS)


def haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Wrapper around geodesic distance returning km with 2‑dec precision."""
    return round(geodesic(p1, p2).kilometers, 2)


def nearest_fire_station(lat: float, lon: float, stations_df: pd.DataFrame):
    stations_df = stations_df.copy()
    stations_df["distance_km"] = stations_df.apply(
        lambda row: haversine_km((lat, lon), (row.latitude, row.longitude)), axis=1
    )
    stations_df.sort_values("distance_km", inplace=True)
    return stations_df.iloc[0]


def log_event(status: str, location: str, notes: str = "") -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    entry = {
        "timestamp": ts,
        "status": status,
        "location": location,
        "notes": notes,
    }
    if "log" not in st.session_state:
        st.session_state.log: List[dict] = []
    st.session_state.log.append(entry)
    # Persist to CSV
    pd.DataFrame(st.session_state.log).to_csv(LOG_FILE, index=False)


def load_existing_log() -> None:
    if LOG_FILE.exists() and "log" not in st.session_state:
        st.session_state.log = pd.read_csv(LOG_FILE).to_dict("records")


def draw_map(selected_loc: dict | None, highlight_evac: bool = False):
    """Render a pydeck map with campus, fire stations, and optional overlays."""
    stations_df = load_fire_station_df()

    layers = []

    # Fire stations layer
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=stations_df,
            get_position="[longitude, latitude]",
            get_radius=150,
            get_fill_color=[255, 0, 0, 160],
            pickable=True,
        )
    )

    # Campus locations layer
    loc_df = pd.DataFrame(CAMPUS_LOCATIONS)
    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=loc_df,
            get_position="[longitude, latitude]",
            get_radius=100,
            get_fill_color=[0, 128, 255, 160],
            pickable=True,
        )
    )

    # Extinguishers & Evac path for selected location
    if selected_loc:
        # Extinguishers as small green dots
        ext_data = pd.DataFrame(
            [
                {"lat": lat, "lon": lon}
                for lat, lon in selected_loc.get("extinguishers", [])
            ]
        )
        if not ext_data.empty:
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=ext_data,
                    get_position="[lon, lat]",
                    get_radius=50,
                    get_fill_color=[0, 255, 0, 200],
                )
            )

        if highlight_evac:
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    data=[{
                        "path": [
                            [lon, lat] for lat, lon in selected_loc.get("evac_path", [])
                        ],
                    }],
                    get_width=4,
                    get_color=[255, 165, 0],  # orange line
                )
            )

    view_state = pdk.ViewState(
        latitude=IRIDM_LAT,
        longitude=IRIDM_LON,
        zoom=16,
        pitch=45,
    )

    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))

###############################################################################
# ------------------------------  UI  --------------------------------------- #
###############################################################################

def main():
    st.set_page_config(
        page_title="IRIDM DM Assistant",
        layout="wide",
        page_icon="🚒",
    )

    load_existing_log()

    st.title("IRIDM Disaster‑Management Assistant :fire:")

    # ---- Top layout: Map & Site schematic side‑by‑side ----
    col_map, col_img = st.columns((2, 1))

    with col_img:
        st.header("Campus layout (schematic)")
        if SITE_LAYOUT_PATH.exists():
            st.image(SITE_LAYOUT_PATH, use_column_width=True)
        else:
            st.warning("Site layout image not found – place 'iridm_site_layout..png' next to the app.")

    with col_map:
        st.header("Live campus & nearby resources map")
        # Input sidebar collects selections; we draw map later after selections are made.
        pass

    # ---- Sidebar wizard ----
    st.sidebar.header("Incident Report Wizard")
    
    #altering now : 
    disaster_prep = st.sidebar.selectbox(
        "Diaster Preparedness", ["Training ", "Drills","DM Emergency Response Team","Evacuation Plans"], index=None, placeholder="Choose…"
    )
    
    disaster_mitig = st.sidebar.selectbox(
        "Diaster Mitigation", ["Training ", "Drills","DM Emergency Response Team","Evacuation Plans"], index=None, placeholder="Choose…"
    )
   
    disaster_type = st.sidebar.selectbox(
        "Risk Assessment", ["Natural", "Man‑made","Technical Faliure"], index=None, placeholder="Choose…"
    )

    if disaster_type:
        if disaster_type == "Natural":
            subtype = st.sidebar.selectbox(
                "Specify Nature of Incident",
                ["Flood", "Other"],
                index=None,
                placeholder="Choose…",
            )
        elif (disaster_type == "Man-made"):
            subtype = st.sidebar.selectbox(
                "Specify Type of Incident",
                ["Fire", "Train Accident", "Infrastructure Collapse", "Machinery BreakDown", "Medical Emergency","Other"],
                index=None,
                placeholder="Choose…",
            )
        else:
            subtype= st.sidebar.selectbox(
                "Specify the type of Techincal FAilure",["IT system BreakDowm","Power Failure","Transportation Accident involving trainee and staff"],
                index = None,
                placeholder="Choose.."
            )

        if subtype == "Fire":
            st.sidebar.subheader("Fire Incident Details")

            location_names = [loc["name"] for loc in CAMPUS_LOCATIONS]
            selected_loc_name = st.sidebar.selectbox("Where is the fire?", location_names, index=None)
            gps_option = st.sidebar.checkbox("Use my GPS location instead", value=False)

            selected_loc = next(
                (loc for loc in CAMPUS_LOCATIONS if loc["name"] == selected_loc_name), None
            )

            if selected_loc_name is None and not gps_option:
                st.sidebar.info("Select a campus location or use GPS to proceed.")
            else:
                # Compute distances/ETA to nearest fire station
                if gps_option:
                    # Use browser geolocation via st_javascript (needs external component) – placeholder
                    st.warning("GPS capture not implemented in this prototype. Using location centre.")
                    user_lat, user_lon = IRIDM_LAT, IRIDM_LON
                else:
                    user_lat, user_lon = selected_loc["latitude"], selected_loc["longitude"]

                stations_df = load_fire_station_df()
                nearest = nearest_fire_station(user_lat, user_lon, stations_df)

                distance_km = nearest["distance_km"]
                eta_min = int((distance_km / AVG_FIRE_TRUCK_SPEED_KMPH) * 60)

                st.sidebar.markdown("---")
                st.sidebar.markdown(
                    f"### Nearest Fire Station\n**{nearest['name']}**  \n"
                    f"📞 [Call](`tel:{nearest['phone']}`)  \n"
                    f"🛣️ {distance_km} km &nbsp;&nbsp; ⏱️ ≈ {eta_min} min"
                )

                # Action buttons
                if st.sidebar.button("📞 Dial Fire Station & Log Call"):
                    log_event(status="CALL_PLACED", location=selected_loc_name or "GPS")
                    st.sidebar.success("Call logged – stay safe! 🚒")

                if st.sidebar.button("✅ Firefighters Arrived – Mark Resolved"):
                    log_event(status="RESOLVED", location=selected_loc_name or "GPS")
                    st.sidebar.success("Incident marked as resolved. Report saved.")

                # Upload photos of incident
                st.sidebar.file_uploader(
                    "Upload photo/video evidence (optional)",
                    accept_multiple_files=False,
                    type=["jpg", "jpeg", "png", "mp4"],
                )
                
                

                # Upload / link evacuation plan for this location
                with st.sidebar.expander("Evacuation Plan for this location"):
                    st.markdown("Replace / add an updated evacuation schematic for this block.")
                    st.file_uploader(
                        "Upload schematic (PDF / image)",
                        type=["pdf", "jpg", "jpeg", "png"],
                        key=f"evac_{selected_loc_name}",
                    )

                # Draw map with highlight
                with col_map:
                    draw_map(selected_loc, highlight_evac=True)

        else:
            # Incidents that are not Fire have no custom flow yet
            st.sidebar.info("This prototype currently supports the **Fire** workflow only.")
            with col_map:
                draw_map(selected_loc=None)
    else:
        with col_map:
            draw_map(selected_loc=None)

    # ---- Incident log table ----
    st.subheader("📜 Incident Log (session + persisted)")
    log_df = pd.DataFrame(st.session_state.get("log", []))
    if log_df.empty:
        st.info("No incidents logged this session.")
    else:
        st.dataframe(log_df.sort_values("timestamp", ascending=False), use_container_width=True)


if __name__ == "__main__":
    main()
