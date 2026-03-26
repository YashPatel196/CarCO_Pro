import streamlit as st
import pandas as pd
import pickle
import numpy as np
from datetime import datetime
from fpdf import FPDF
import google.generativeai as genai
import altair as alt
import matplotlib.pyplot as plt
import os
import socket
import hashlib  # Added for password hashing
import time
import requests  # Added for VIN API calls
import io
import sqlite3
from streamlit_geolocation import streamlit_geolocation
import math
import pydeck as pdk
import time
from streamlit_autorefresh import st_autorefresh

DB_FILE = "carco_data.db"

# --- HAVERSINE DISTANCE FUNCTION ---
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculates distance in km between two GPS coordinates."""
    R = 6371.0 # Earth radius in kilometers
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def fetch_vin_data(vin):
    """Fetches vehicle specifications from the NHTSA API using the VIN."""
    if not vin or len(vin) != 17:
        st.error("Please enter a valid 17-character VIN.")
        return False # Changed to return False for consistency

    try:
        api_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{vin}?format=json"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('Results', [])
            
            # Create a dictionary of the results for easy access
            vehicle_info = {item['Variable']: item['Value'] for item in results if item['Value']}
            
            # Store essential data in session state
            st.session_state.autofill_data = {
                "make": vehicle_info.get("Make", ""),
                "model": vehicle_info.get("Model", ""),
                "year": vehicle_info.get("Model Year", ""),
                "type": vehicle_info.get("Body Class", ""),
                "fuel": vehicle_info.get("Fuel Type - Primary", "Gasoline")
            }
            st.session_state.vin_input = vin
            return True
        else:
            st.error("Could not connect to the vehicle database.")
    except Exception as e:
        st.error(f"Error fetching data: {e}")
    return False

def main():
    # ... session state logic ...

   
    if st.session_state.current_tab == "VIN LOOKUP & SCANNER":
        st.title("🔍 Vehicle Identification Number (VIN) Lookup")
             
# --- 1. Load Bundle & Config ---

st.set_page_config(page_title="CarCo", page_icon="🚗", layout="wide")

@st.cache_resource
def load_data():
    # Updated to point to the new balanced model version
    with open('ultimate_confidence_model_V2.pkl', 'rb') as f:
        return pickle.load(f)

try:
    bundle = load_data()
except FileNotFoundError:
    st.error("Error: 'ultimate_confidence_model_V2.pkl' not found. Please ensure the model file is in the same directory.")
    st.stop()

# --- 2. Loading Animation & Connection Check ---
if 'app_loaded' not in st.session_state:
    loading_placeholder = st.empty()
    

    animation_html = """
        <style>
            @keyframes drive { 0% { transform: translateX(-100vw); } 100% { transform: translateX(100vw); } }
            @keyframes puff { 
                0% { opacity: 0.8; transform: scale(0.5) translate(0, 0); }
                50% { opacity: 0.6; }
                100% { opacity: 0; transform: scale(2.5) translate(-40px, -20px); }
            }
            .loading-container {
                display: flex; flex-direction: column; justify-content: center; align-items: center;
                height: 80vh; 
                background-color: var(--background-color); /* Adaptive background */
                overflow: hidden;
            }
            .car-container { position: relative; font-size: 100px; animation: drive 3s linear infinite; }
            .flipped-car { display: inline-block; transform: scaleX(-1); }
            .smoke {
                position: absolute; bottom: 20px; left: -10px; width: 20px; height: 20px;
                background-color: #555; border-radius: 50%; opacity: 0;
            }
            .s1 { animation: puff 1.5s infinite 0.1s; }
            .s2 { animation: puff 1.5s infinite 0.5s; }
            .s3 { animation: puff 1.5s infinite 0.9s; }
            .loading-text {
                margin-top: 20px; color: #4CAF50; font-family: 'Helvetica', sans-serif;
                font-weight: bold; animation: blink 1.5s infinite;
            }
            @keyframes blink { 50% { opacity: 0.5; } }
        </style>
        <div class="loading-container">
            <div class="car-container">
                <div class="flipped-car">🚗</div>
                <div class="smoke s1"></div><div class="smoke s2"></div><div class="smoke s3"></div>
            </div>
            <h2 class="loading-text">Analyzing Vehicle Emissions...</h2>
        </div>
    """
    
    # Start Animation
    loading_placeholder.markdown(animation_html, unsafe_allow_html=True)
    
    # Check Internet Connection
    def is_connected():
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    if not is_connected():
        loading_placeholder.empty()
        st.error("**Connection Error:** No internet access detected.")
        if st.button("Retry Connection", type="primary"):
            st.rerun()
        st.stop()

    time.sleep(2.5) # Simulate loading
    loading_placeholder.empty()
    st.session_state['app_loaded'] = True

# --- 3.STYLING ---
st.markdown("""
    <style>
    /* 1. Makes the 'White Boxes' adapt to the theme (Turns Black in Dark Mode) */
    .report-card, .vin-card {
        background-color: var(--background-secondary-color) !important;
        color: var(--text-color) !important;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-top: 5px solid #4CAF50;
        margin-bottom: 20px;
    }

   
    .report-card h1, .report-card h2, .report-card h3, .report-card p,
    .vin-row, .vin-label, .vin-value {
        color: var(--text-color) !important;
    }

    /* 3.BUTTON STYLING (Unchanged) */
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3em;
        background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
        color: white !important; font-weight: bold; border: none;
    }

    /* 4. Formatting for the VIN Data Section */
    .vin-header {
        color: #4CAF50 !important;
        font-size: 0.85em; font-weight: bold; text-transform: uppercase;
        margin-bottom: 8px;
    }
    .vin-row {
        display: flex; justify-content: space-between; padding: 6px 0;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    }
    .vin-label { opacity: 0.7; }
    .vin-value { font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. AUTHENTICATION SYSTEM ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    """Creates the database and table if they don't exist."""
    conn = sqlite3.connect('carco_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    conn.commit()
    conn.close()
    

def add_user(username, password):
    init_db() # Ensure table exists
    hashed_pswd = make_hashes(password)
    conn = sqlite3.connect('carco_data.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pswd))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # This triggers ONLY if the username actually exists in the DB
        return False
    finally:
        conn.close()

def login_user(username, password):
    init_db()
    hashed_pswd = make_hashes(password)
    conn = sqlite3.connect('carco_data.db')
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    if result and result[0] == hashed_pswd:
        return True
    return False

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''
# In your Dashboard Tab logic:
if 'autofill_data' in st.session_state:
    data = st.session_state['autofill_data']

if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""<div style="background-color: var(--background-secondary-color); padding: 30px; border-radius: 15px; border-top: 5px solid #2E7D32; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center;">
                <h2 style="margin: 0;">CarCo Access</h2></div>""", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Login", "Register"])
        with tab1:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type='password', key="login_pass")
            if st.button("Login", key="login_btn"):
                if login_user(username, password):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.rerun()
                else:
                    st.error("Incorrect Username or Password")
        with tab2:
            new_user = st.text_input("Choose a Username", key="reg_user").strip() # Added .strip() to prevent spaces
            new_pass = st.text_input("Choose a Password", type='password', key="reg_pass")
            confirm_pass = st.text_input("Confirm Password", type='password', key="reg_conf")
            
            if st.button("Create Account", key="reg_btn"):
                if " " in new_user or " " in new_pass:
                    st.warning("Username and Password cannot contain spaces.")
                elif new_pass != confirm_pass: 
                    st.warning("Passwords do not match!")
                elif len(new_pass) < 4: 
                    st.warning("Password must be at least 4 characters.")
                else:
                    if add_user(new_user, new_pass): 
                        st.success("Account created!")
                    else: 
                        st.error("Username already exists.")
            st.stop()

# --- 5. VIN LOOKUP HELPER ---

def get_vehicle_specs_from_vin(vin):
    """Fetch and parse vehicle data from NHTSA vPIC."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevinextended/{vin}?format=json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            results = response.json().get('Results', [])
            # Map API variables to a cleaner dictionary
            data = {item.get('Variable'): item.get('Value') for item in results if item.get('Value')}
            return {
                "Make": data.get("Make"),
                "Model": data.get("Model"),
                "Year": data.get("Model Year"),
                "Engine": data.get("Displacement (L)"),
                "Cylinders": data.get("Engine Number of Cylinders"),
                "Fuel": data.get("Fuel Type - Primary"),
                "Transmission": data.get("Transmission Style"),
                "Class": data.get("Body Class")
            }
    except:
        return None
    return None

def get_car_image(make, model):
    """Fetch a representative car image from Unsplash."""
    try:
        client_id = st.secrets.get("UNSPLASH_KEY")
        if not client_id:
            # Fallback image if no API key is set
            return "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?auto=format&fit=crop&w=800&q=80" 
        
        query = f"{make} {model} car"
        url = f"https://api.unsplash.com/search/photos?page=1&query={query}&client_id={client_id}&per_page=1"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['results']:
                return data['results'][0]['urls']['regular']
    except Exception as e:
        pass
    # Return default placeholder if anything fails
    return "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?auto=format&fit=crop&w=800&q=80"

# --- 6. NAVIGATION LOGIC ---
with st.sidebar:
    st.write(f"👤 **{st.session_state['username']}**")
    # Added Navigation
    
    app_mode = st.radio("Navigate", [
        "Introduction", 
        "VIN Lookup", 
        "Intelligence Dashboard", 
        "Eco Leaderboard/Compare",
        "Live Trip Tracker"
    ])
    
    if st.button("Log Out", type="secondary"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''
        st.session_state['autofill_data'] = None
        st.rerun()
    st.divider()

# --- MODE 1: INTRODUCTION PAGE ---
if app_mode == "Introduction":
    st.title("Understanding Vehicle Emissions")
    st.markdown("""
    Vehicle CO2 emissions are the primary byproduct of burning fossil fuels like gasoline and diesel. When fuel reacts with oxygen to create energy, carbon dioxide is released through the tailpipe. As a potent greenhouse gas, CO2 traps heat in the atmosphere, making the transportation sector a leading contributor to global climate change. A vehicle's emission levels are directly tied to its fuel efficiency; larger vehicles like SUVs and trucks naturally require more energy and produce higher emissions than compact cars. While modern hybrid technologies and stricter standards are helping, transitioning to renewable energy and improving engine efficiency remain the most effective ways to lower the global "carbon cost" of driving.

    CarCo is an AI-powered intelligence platform designed to bridge the gap between technical automotive data and environmental action. Our application empowers consumers to instantly estimate the environmental impact of any vehicle based on core specifications. By inputting details such as engine size, cylinder count, and fuel type, users receive a detailed Intelligence Report that translates raw data into intuitive Eco Grades and actionable insights. Our mission is to promote "Eco-Transparency," allowing you to compare vehicles side-by-side and make data-driven decisions for a sustainable future.

    At the heart of CarCo lies a sophisticated machine learning ensemble trained on thousands of real-world vehicle data points. We are proud to report that our core prediction model achieves an R² Score of 0.8922. This high-precision metric indicates that our model explains approximately 89.2% of the variance in CO2 emissions based on a vehicle's technical attributes. In the field of data science, this represents a highly reliable calculation, ensuring that the environmental estimates you receive are not mere guesses, but rigorous statistical validations. Whether you are browsing the Eco Leaderboard to compare rivals or analyzing a specific VIN, CarCo provides the high-accuracy intelligence needed to navigate the road toward a greener planet.
    """)
    
    if st.button("Proceed to Intelligence Dashboard"):
        st.info("Please select 'Intelligence Dashboard' from the sidebar.")

    # --- FAQ SECTION ---
    st.divider()
    st.header("❓ Frequently Asked Questions")
    
    with st.expander("What is CarCo?"):
        st.write("CarCo is an intelligent diagnostic platform that uses machine learning to predict vehicle CO2 emissions. It helps users understand the environmental footprint of specific vehicle configurations and provides actionable AI-driven advice for improvement.")
        
    with st.expander("How is the CO2 emission and Eco Grade calculated?"):
        st.write("Our system uses a Gradient Boosting regression model trained on thousands of vehicle records. It analyzes the relationship between engine size, cylinders, fuel consumption, and vehicle class. The 'Eco Grade' is a normalized score (0-100) where 'A' represents the top-tier efficiency within our database.")
        
    with st.expander("How accurate is the VIN lookup?"):
        st.write("The VIN lookup connects directly to the NHTSA (National Highway Traffic Safety Administration) database. While highly accurate for North American vehicles, some international models or very new releases may require manual entry.")
        
    with st.expander("What does the 'Statistical Confidence' mean?"):
        st.write("This percentage represents the model's certainty. It is calculated based on the 'spread' between our lower-bound and upper-bound predictions. A higher percentage means your vehicle configuration closely matches the patterns in our training data.")
        
    with st.expander("Can I use this for Electric Vehicles (EVs)?"):
        st.write("Currently, CarCo focuses on Internal Combustion Engine (ICE) and Hybrid vehicles. Since EVs have zero tailpipe emissions, they would technically always receive an 'A+' grade in this specific tool.")

# --- MODE 1.5: VIN LOOKUP PAGE ---
elif app_mode == "VIN Lookup":
    st.title("🔍 VIN Lookup")

    # --- TAB: MANUAL ENTRY (Features as before) ---
    st.markdown("**Lookup by VIN**")
    vin_input = st.text_input("Enter 17-character VIN", placeholder="e.g., 5UXZW4C55MDQGW...", key="manual_vin_entry")
    
    if st.button("Fetch & Autofill Specs"):
        if len(vin_input) == 17:
            with st.spinner("Searching database..."):
                specs = get_vehicle_specs_from_vin(vin_input)
                if specs and specs.get("Make"):
                    st.session_state['autofill_data'] = {
                        "Make": specs.get("Make"),
                        "Model": specs.get("Model"),
                        "Year": specs.get("Year"),
                        "Engine": specs.get("Engine"),
                        "Cylinders": specs.get("Cylinders"),
                        "Fuel": specs.get("Fuel"),
                        "Transmission": specs.get("Transmission"),
                        "Class": specs.get("Class")
                    }
                    st.success(f"✅ Vehicle specs for {specs['Make']} {specs['Model']} synced!")
                    st.rerun()
                else:
                    st.error("Vehicle not found. Please check the VIN.")
        else:
            st.warning("Please enter a valid 17-character VIN.")

    # 3. Global Success View (Displaying fetched data)
    if st.session_state.get('autofill_data'):
        s = st.session_state['autofill_data']
        st.divider()
        
        # Display the visual confirmation
        res_col1, res_col2 = st.columns([1, 1.2])
        car_img_url = get_car_image(s.get('Make', ''), s.get('Model', ''))
        
        with res_col1:
            st.image(car_img_url, width="stretch", caption=f"{s.get('Make')} {s.get('Model')}")
        with res_col2:
            st.markdown(f"""
                <div class="vin-card">
                <div class="vin-header">VEHICLE SPECS LOADED</div>
                <div class="vin-row"><span class="vin-label">Year / Make</span><span class="vin-value">{s.get('Year', 'N/A')} {s.get('Make', 'N/A')}</span></div>
                <div class="vin-row"><span class="vin-label">Model</span><span class="vin-value">{s.get('Model', 'N/A')}</span></div>
                <div class="vin-row"><span class="vin-label">Engine</span><span class="vin-value">{s.get('Engine', 'N/A')}L</span></div>
                <div class="vin-row"><span class="vin-label">Cylinders</span><span class="vin-value">{s.get('Cylinders', 'N/A')}</span></div>
                <div class="vin-row"><span class="vin-label">Fuel Type</span><span class="vin-value">{s.get('Fuel', 'N/A')}</span></div>
                <div class="vin-row"><span class="vin-label">Transmission</span><span class="vin-value">{s.get('Transmission', 'N/A')}</span></div>
                <div class="vin-row" style="border:none;"><span class="vin-label">Body Class</span><span class="vin-value">{s.get('Class', 'N/A')}</span></div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🗑️ Clear Data", width="stretch"):
                st.session_state['autofill_data'] = None
                st.rerun()

        st.success("✅ Data is now automatically inserted into the **Intelligence Dashboard**. Head there to see the results!")

# --- MODE 2: MAIN DASHBOARD ---
elif app_mode == "Intelligence Dashboard":
    st.title("🚗 CarCO Intelligence")
    st.markdown("Advanced CO2 Emission Grading & Statistical Confidence Dashboard")
    
    with st.sidebar:
        
        st.header("Vehicle Specs")
        
        # Helper to retrieve autofilled data or defaults
        data = st.session_state['autofill_data'] if st.session_state['autofill_data'] else {}

        # 1. Engine CC Logic (Converts L to CC)
        try:
            raw_engine = float(data.get("Engine", 1.6))
            def_cc = int(raw_engine * 1000) if raw_engine < 20 else int(raw_engine)
        except:
            def_cc = 1600
        engine_cc = st.number_input("Engine Displacement (CC)", value=def_cc, step=100)
        engine = engine_cc / 1000.0
        st.caption(f"In Litres: **{engine:.1f} Litres**")

        # 2. Cylinders Logic
        try:
            def_cyl = int(data.get("Cylinders", 4))
        except:
            def_cyl = 4
        cylinders = st.number_input("Cylinders", value=def_cyl, step=1)
        
        fuel_cons = st.slider("Combined Fuel Consumption (L/100 km)", 3.0, 30.0, 9.5)
        
        # 3. Transmission Category Mapping
        trans_list = ["Automatic", "Manual", "Automated Manual", "CVT"]
        api_trans = str(data.get("Transmission", "")).lower()
        t_idx = 0
        if "manual" in api_trans and "automated" not in api_trans: t_idx = 1
        elif "automated" in api_trans: t_idx = 2
        elif "variable" in api_trans or "cvt" in api_trans: t_idx = 3
        trans_cat = st.selectbox("Transmission Type", trans_list, index=t_idx)

        if trans_cat == "Automatic": specific_trans = st.selectbox("Select Code", ["AS6", "AS8", "AS10", "A4", "A5", "A6", "A8", "A9", "A10"])
        elif trans_cat == "Manual": specific_trans = st.selectbox("Select Code", ["M5", "M6", "M7"])
        elif trans_cat == "Automated Manual": specific_trans = st.selectbox("Select Code", ["AM5", "AM6", "AM7", "AM8", "AM9"])
        else: specific_trans = st.selectbox("Select Code", ["AV", "AV6", "AV7", "AV8", "AV10"])
            
        layout = st.selectbox("Engine Layout", ["Inline/Standard", "V-Type", "W-Type", "Flat/Boxer"])
        
        # 4. Fuel Type Mapping
        fuel_list = ["Regular Gasoline", "Premium Gasoline", "Diesel", "Ethanol"]
        api_fuel = str(data.get("Fuel", "")).lower()
        f_idx = 0
        if "premium" in api_fuel: f_idx = 1
        elif "diesel" in api_fuel: f_idx = 2
        elif "ethanol" in api_fuel: f_idx = 3
        fuel = st.selectbox("Fuel Type", fuel_list, index=f_idx)

        # 5. Vehicle Class Mapping
        class_list = ["Compact", "SUV - Small", "Mid-Size", "Full-Size", "Pickup Truck"]
        api_class = str(data.get("Class", "")).lower()
        c_idx = 2 # Default Mid-Size
        if "compact" in api_class: c_idx = 0
        elif "suv" in api_class: c_idx = 1
        elif "full" in api_class: c_idx = 3
        elif "pickup" in api_class: c_idx = 4
        v_class = st.selectbox("Vehicle Class", class_list, index=c_idx)

    def get_gemini_suggestions(engine, fuel, v_class, trans, co2, grade):
        try:
            api_key = st.secrets.get("GEMINI_KEY")
            if not api_key: return "⚠️ Gemini API Key not found."
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = f"Car: {engine}L {fuel} {v_class}. CO2: {co2:.1f}g/km. Give 3 short tips for improving the carbon emission score."
            response = model.generate_content(prompt)
            return response.text
        except: return "⚠️ AI Insights currently unavailable."

    # --- Prediction Execution ---
    # 1. Save the button click to session state so the report doesn't disappear on subsequent clicks
    if st.button("Generate Detailed Intelligence Report"):
        st.session_state['generate_report'] = True

    # 2. Run the calculation and UI if the flag is True
    if st.session_state.get('generate_report', False):
        layout_map = {"Inline/Standard": 1.0, "V-Type": 1.02, "W-Type": 1.05, "Flat/Boxer": 1.01}
        penalty = layout_map[layout]

        # Data Prep - Must match train.py logic
        input_df = pd.DataFrame(0, index=[0], columns=bundle['columns'])
        log_fuel = np.log1p(fuel_cons)
        
        input_df['Engine Size(L)'] = engine
        input_df['Cylinders'] = cylinders
        input_df['Engine_Cyl_Ratio'] = engine / cylinders
        input_df['Fuel_per_Liter'] = log_fuel / (engine + 1)
        
        f_map = {"Regular Gasoline": "X", "Premium Gasoline": "Z", "Diesel": "D", "Ethanol": "E"}
        c_map = {"Compact": "COMPACT", "SUV - Small": "SUV - SMALL", "Mid-Size": "MID-SIZE", "Full-Size": "FULL-SIZE", "Pickup Truck": "PICKUP TRUCK - STANDARD"}
        
        if f"Fuel Type_{f_map[fuel]}" in input_df.columns: input_df[f"Fuel Type_{f_map[fuel]}"] = 1
        if f"Vehicle Class_{c_map[v_class]}" in input_df.columns: input_df[f"Vehicle Class_{c_map[v_class]}"] = 1
        if f"Transmission_{specific_trans}" in input_df.columns: input_df[f"Transmission_{specific_trans}"] = 1

        mid_p = bundle['mid'].predict(input_df)[0] * penalty
        low_p = bundle['lower'].predict(input_df)[0] * penalty
        high_p = bundle['upper'].predict(input_df)[0] * penalty

        st.session_state['mid_p'] = float(mid_p)

        score = max(1, min(100, int(100 - ((mid_p - 90) / 260 * 100))))
        if score >= 85: grade, g_color = "A", "#4CAF50"
        elif score >= 70: grade, g_color = "B", "#2196F3"
        elif score >= 55: grade, g_color = "C", "#FBC02D"
        elif score >= 40: grade, g_color = "D", "#FF9800"
        elif score >= 30: grade, g_color = "E", "#ff3002"
        else: grade, g_color = "F", "#A30000"

        # --- Enhanced Statistical Confidence Logic ---
        spread = high_p - low_p
        relative_spread = spread / mid_p
        sensitivity = 0.9
        calculated_conf = 100 * (np.exp(-sensitivity * relative_spread))
        conf_pct = int(max(5, min(99, calculated_conf)))

        if conf_pct > 85: conf_label = "High"
        elif conf_pct > 65: conf_label = "Reliable"
        elif conf_pct > 45: conf_label = "Fair"
        else: conf_label = "Uncertain"

        st.divider()
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f"""<div style="padding: 30px; border-radius: 15px; text-align: center; border: 1px solid #ddd;">
                    <p style="margin:0; font-weight: bold; color: #666;">ECO GRADE</p>
                    <h1 style="font-size: 80px; color: {g_color}; margin: 0;">{grade}</h1>
                    <p style="font-size: 1.2em;">Score: {score}/100</p></div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class="report-card"><h3>Intelligence Summary</h3>
                    <div style="display: flex; justify-content: space-between; margin-top: 15px;">
                        <div><p style="color:#666; margin:0;">CO2 Prediction</p><h2>{mid_p:.1f} g/km</h2></div>
                        <div style="text-align:right;">
                            <p style="color:#666; margin:0;">AI Confidence ({conf_label})</p>
                            <h2>{conf_pct}%</h2>
                        </div>
                    </div>
                    <p style="margin: 15px 0 5px 0; font-weight: bold;">Performance Rating</p>
                    <div style="width: 100%; background: #eee; border-radius: 10px; height: 12px;">
                        <div style="width: {score}%; background: {g_color}; height: 12px; border-radius: 10px;"></div>
                    </div>
                    <p style="color: #d32f2f; font-weight: bold; margin-top: 15px; margin-bottom: 0;">Error Margin: ±{(high_p - low_p)/2:.1f} g/km</p>
                    <p style="font-size: 0.85em; color: #666;">Statistical Range: {low_p:.1f} - {high_p:.1f} g/km</p></div>""", unsafe_allow_html=True)

        st.divider()
        g_col1, g_col2 = st.columns([2, 1])
        with g_col1:
            st.markdown("**Benchmark Comparison (g/km)**")
            comp_df = pd.DataFrame({"Type": ["Hybrid", "Compact", "You", "Avg SUV", "Sport"], "CO2": [105, 140, int(mid_p), 220, 320], "Color": ["Ref", "Ref", "You", "Ref", "Ref"]})
            chart = alt.Chart(comp_df).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
                x=alt.X('Type', sort=None), y='CO2',
                color=alt.Color('Color', legend=None, scale=alt.Scale(domain=['Ref', 'You'], range=['#cfd8dc', g_color]))
            ).properties(height=250)
            st.altair_chart(chart, width="stretch")

        with g_col2:
            st.markdown("**Efficiency Composition**")
            fig, ax = plt.subplots(figsize=(3, 3))
            ax.pie([score, 100 - score], startangle=90, colors=[g_color, '#eeeeee'], wedgeprops=dict(width=0.35))
            ax.text(0, 0, f"{score}", ha='center', va='center', fontsize=24, fontweight='bold', color=g_color)
            ax.axis('equal')
            fig.patch.set_alpha(0)
            st.pyplot(fig)

        st.divider()
        st.markdown("### Advanced AI Insights (Gemini)")
        with st.spinner("Gemini is analyzing..."):
            ai_advice = get_gemini_suggestions(engine, fuel, v_class, specific_trans, mid_p, grade)
        st.info(ai_advice)
        
# --- INTERACTIVE LEADERBOARD LOGIC ---
        st.divider()
        st.markdown("### 🏆 Join the Eco Leaderboard")
        
        def update_and_show_leaderboard(user, vehicle, co2):
            leaderboard_file = 'leaderboard.csv'
            new_entry = {
                'User': user,
                'Vehicle': vehicle,
                'CO2 Emission (g/km)': round(co2, 1),
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            # 1. Load or Initialize the base dataframe
            if os.path.exists(leaderboard_file):
                try:
                    df_existing = pd.read_csv(leaderboard_file)
                except pd.errors.EmptyDataError:
                    df_existing = pd.DataFrame(columns=['User', 'Vehicle', 'CO2 Emission (g/km)', 'Timestamp'])
            else:
                df_existing = pd.DataFrame(columns=['User', 'Vehicle', 'CO2 Emission (g/km)', 'Timestamp'])

            # 2. Process Logic
            mask = (df_existing['User'] == user) & (df_existing['Vehicle'] == vehicle)
            
            if mask.any():
                # Update existing
                df_existing.loc[mask, 'CO2 Emission (g/km)'] = round(co2, 1)
                df_existing.loc[mask, 'Timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                df_final = df_existing
                st.success(f"Updated record for your **{vehicle}**!")
            else:
                # Append new
                df_new_row = pd.DataFrame([new_entry])
                df_final = pd.concat([df_existing, df_new_row], ignore_index=True)
                st.success(f"Added your **{vehicle}** to the leaderboard!")

            # 3. Save (df_final is now guaranteed to be defined)
            df_final.to_csv(leaderboard_file, index=False)
            
            # Display logic
            
            def get_leaderboard_df():
                conn = sqlite3.connect(DB_FILE)
                df = pd.read_sql_query("SELECT username as User, vehicle as Vehicle, co2 as [CO2 Emission (g/km)], timestamp as Timestamp FROM leaderboard ORDER BY co2 ASC", conn)
                conn.close()
                return df
            st.success(f"Leaderboard updated! Your current vehicle: **{vehicle}**")
            
            # Sort for display (lowest emission first)
            df_display = df_final.sort_values(by="CO2 Emission (g/km)", ascending=True).reset_index(drop=True)
            df_display.index = df_display.index + 1
            df_display.insert(0, "Rank", df_display.index.map(lambda x: 
                f"{x} 🥇" if x == 1 else f"{x} 🥈" if x == 2 else f"{x} 🥉" if x == 3 else f"{x}"))
            

        s = st.session_state.get('autofill_data')
        
        # Scenario A: Vehicle Name is known from VIN
        if s and s.get('Make') and s.get('Model'):
            vehicle_name = f"{s.get('Year', '')} {s.get('Make', '')} {s.get('Model', '')}".strip()
            st.info(f"Detected Vehicle: **{vehicle_name}**")
            
            if st.button("Update My Leaderboard Position"):
                update_and_show_leaderboard(st.session_state['username'], vehicle_name, mid_p)
                
        # Scenario B: Manual Entry required
        else:
            with st.form("leaderboard_form"):
                st.info("Please enter your car model to update your leaderboard rank.")
                custom_vehicle = st.text_input("Vehicle Model:")
                submitted = st.form_submit_button("Update Leaderboard")
                
                if submitted:
                    if custom_vehicle.strip():
                        update_and_show_leaderboard(st.session_state['username'], custom_vehicle.strip(), mid_p)
                    else:
                        st.warning("Please enter a vehicle name.")

 # --- 1. PDF ---
    class CarCO_Report(FPDF):
        def header(self):
            self.set_fill_color(40, 44, 52) 
            self.rect(0, 0, 210, 20, 'F')
            self.set_text_color(255, 255, 255)
            self.set_font("Arial", "B", 12)
            self.cell(0, -10, "OFFICIAL EMISSIONS & PERFORMANCE CERTIFICATE", 0, 0, 'C')
            self.ln(20)

        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, f"Page {self.page_no()} | Generated by CarCO Intelligence AI", 0, 0, 'C')

# --- 2. THE SINGLE GENERATOR FUNCTION ---
    def create_pdf_report(v_specs, results, bar_img_bytes, pie_img_bytes):
        pdf = CarCO_Report()
        pdf.add_page()
        
        # Title Section
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 20)
        pdf.cell(0, 15, "Vehicle Analysis Report", ln=True, align='L')
        
        # Metadata
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(100, 100, 100)
        meta = f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} | User: {st.session_state.get('username', 'Guest')}"
        pdf.cell(0, 5, meta, ln=True, align='L')
        pdf.ln(5)
        
        # Section 1: Specifications
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, " 1. VEHICLE SPECIFICATIONS", ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(0, 0, 0)
        for label, value in v_specs.items():
            pdf.set_font("Arial", "B", 10)
            pdf.cell(40, 7, f"{label}:", 0)
            pdf.set_font("Arial", "", 10)
            pdf.cell(95, 7, f"{value}", 0, 1)

        pdf.ln(10)

        # --- Section 2: Results & Charts ---
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, " 2. EMISSIONS ANALYSIS", ln=True, fill=True)
        
        # Key Results Highlight
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(46, 204, 113)
        pdf.cell(0, 10, f"Grade: {results['grade']} | Score: {results['score']}/100", ln=True, align='C')
        
        # --- The Magic Part: Loading from memory ---
        curr_y = pdf.get_y()
        
        # FPDF can accept a 'BytesIO' object directly as if it were a file path
        pdf.image(bar_img_bytes, x=15, y=curr_y + 5, w=100)
        pdf.image(pie_img_bytes, x=125, y=curr_y + 10, w=65)
        
        return bytes(pdf.output(dest='S'))

    # --- 3. THE TRIGGER ---
    st.divider()

    try:
        v_specs_data = {
            "Vehicle Class": v_class,
            "Engine Size": f"{engine}L",
            "Layout": layout,
            "Transmission": specific_trans,
            "Fuel Type": fuel,
            "Consumption": f"{fuel_cons} L/100 km"
        }

        results_data = {
            "grade": grade,
            "score": score,
            "co2": f"{mid_p:.1f} g/km"
        }

        # 1. Create Bar Chart in memory
        buf_bar = io.BytesIO()
        fig_bar, ax_bar = plt.subplots(figsize=(5, 3))
        ax_bar.bar(["Hybrid", "Compact", "You", "SUV", "Sport"], [105, 140, int(mid_p), 220, 320])
        fig_bar.savefig(buf_bar, format="png", bbox_inches='tight')
        plt.close(fig_bar)
        
        # 2. Create Pie Chart in memory
        buf_pie = io.BytesIO()
        fig_pie, ax_pie = plt.subplots(figsize=(4, 4))
        ax_pie.pie([score, 100-score])
        fig_pie.savefig(buf_pie, format="png", bbox_inches='tight')
        plt.close(fig_pie)

        # 3. Generate PDF using the buffers instead of file paths
        final_pdf_bytes = create_pdf_report(v_specs_data, results_data, buf_bar, buf_pie)

        st.download_button("📥 Download Report", data=final_pdf_bytes, file_name="Report.pdf")
    except NameError:
        st.warning("Please run the analysis first to generate the report data.")

# --- MODE 3: LEADERBOARD PAGE ---
elif app_mode == "Eco Leaderboard/Compare":
    st.title("🏆 Global Eco-Driver Leaderboard")
    st.markdown("Ranking every vehicle by its carbon efficiency.")

    leaderboard_file = 'leaderboard.csv'
    if os.path.exists(leaderboard_file):
        df_lb = pd.read_csv(leaderboard_file)
        
        # --- NEW: SELECT TO COMPARE FEATURE ---
        st.markdown("### ⚔️ Compare ")
        st.info("Select exactly two vehicles from the list below to compare them head-to-head.")
        
        df_lb['Select_Label'] = df_lb['User'] + " (" + df_lb['Vehicle'] + ")"
        
        # Multiselect widget
        selected_cars = st.multiselect(
            "Choose two vehicles:",
            options=df_lb['Select_Label'].tolist(),
            max_selections=2
        )

        if len(selected_cars) == 2:
            st.divider()
            # Filter the dataframe for selected cars
            compare_df = df_lb[df_lb['Select_Label'].isin(selected_cars)]
            
            col1, col2 = st.columns(2)
            
            for i, (idx, row) in enumerate(compare_df.iterrows()):
                current_col = col1 if i == 0 else col2
                with current_col:
                    st.markdown(f"""
                        <div class="report-card" style="border-top: 5px solid #2E7D32; text-align: center;">
                            <p style="color: #666; font-weight: bold; margin-bottom: 0;">DRIVER: {row['User']}</p>
                            <h2 style="margin-top: 10px;">{row['Vehicle']}</h2>
                            <hr>
                            <p style="font-size: 0.9em; color: #555;">PREDICTED EMISSIONS</p>
                            <h1 style="color: #2E7D32;">{row['CO2 Emission (g/km)']} <span style="font-size: 15px;">g/km</span></h1>
                        </div>
                    """, unsafe_allow_html=True)
            
            winner = compare_df.loc[compare_df['CO2 Emission (g/km)'].idxmin()]
            
            st.success(f"**{winner['User']}** wins with the more eco-friendly **{winner['Vehicle']}**!")
            st.divider()

        df_lb = df_lb.sort_values(by="CO2 Emission (g/km)", ascending=True).reset_index(drop=True)
        
        # Add Rank numbering and medals
        df_lb.index = df_lb.index + 1
        df_lb.insert(0, "Rank", df_lb.index.map(lambda x: 
            f"{x} 🥇" if x == 1 else 
            f"{x} 🥈" if x == 2 else 
            f"{x} 🥉" if x == 3 else f"{x}"))

        st.dataframe(
            df_lb,
            column_config={
                "Rank": st.column_config.TextColumn("Rank"),
                "User": st.column_config.TextColumn("Driver"),
                "Vehicle": st.column_config.TextColumn("Vehicle Model"),
                "CO2 Emission (g/km)": st.column_config.NumberColumn("CO2 (g/km)", format="%.1f 💨"),
                "Timestamp": st.column_config.DateColumn("Date Analyzed")
            },
            hide_index=True,
            width="stretch"
        )

# --- MODE 4: LIVE TRIP TRACKER ---
elif app_mode == "Live Trip Tracker":
    st.title("📍 Live Trip Emissions Tracker")
    st.markdown("Track your real-time CO2 emissions using your device's GPS.")

    # 1. Initialize Session States for Tracking
    if 'tracking_active' not in st.session_state:
        st.session_state['tracking_active'] = False
        st.session_state['total_km'] = 0.0
        st.session_state['last_lat'] = None
        st.session_state['last_lon'] = None
        st.session_state['route_coords'] = []
        
    # 2. Enforce Vehicle Calculation
    if 'mid_p' not in st.session_state:
        # If they haven't run the dashboard, show an alert and stop the page
        st.error("🛑 Action Required: CO2 Emission data not found.")
        st.info("Please navigate to the **Intelligence Dashboard** from the sidebar and click **'Calculate Emissions'** for your car first. The Live Tracker needs your specific g/km score to work!")
        
        # This stops the rest of the code from running, effectively hiding the map and buttons
        st.stop() 
        
    # If they make it past the stop() command, they have a calculated vehicle!
    emission_factor = st.session_state['mid_p']
    st.success(f"✅ Vehicle Profile Loaded! Using your specific emission factor: **{emission_factor:.1f} g/km**")

    st.divider()

    # 3. Controls
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Start Trip", type="primary"):
            st.session_state['tracking_active'] = True
            st.session_state['total_km'] = 0.0
            st.session_state['last_lat'] = None
            st.session_state['last_lon'] = None
            st.session_state['route_coords'] = []
            st.rerun()
    with col2:
        if st.button("🛑 End & Save Trip", type="secondary"):
            # Only save if they were actually tracking something
            if st.session_state['tracking_active']:
                st.session_state['tracking_active'] = False
                
                # Calculate final numbers
                final_km = st.session_state['total_km']
                final_co2 = final_km * emission_factor
                
                try:
                    # Connect to your existing database
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    
                    # Create a dedicated table for trips if it doesn't exist yet
                    c.execute('''CREATE TABLE IF NOT EXISTS live_trips
                                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                  trip_date TEXT,
                                  distance_km REAL,
                                  co2_emitted_g REAL)''')
                    
                    # Grab the current timestamp
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Insert the new trip data
                    c.execute("INSERT INTO live_trips (trip_date, distance_km, co2_emitted_g) VALUES (?, ?, ?)", 
                              (timestamp, final_km, final_co2))
                    
                    conn.commit()
                    conn.close()
                    
                    # --- FUN ENVIRONMENTAL MESSAGING ---
                    phones_charged = int(final_co2 / 8.2) # ~8.2g CO2 per smartphone charge
                    trees_day = max(1, int(final_co2 / 60)) # ~60g CO2 absorbed by a mature tree per day
                    
                    st.success(f"✅ **Trip Saved!** You drove {final_km:.2f} km and emitted {final_co2:.1f}g of CO2.")
                    
                    # Dynamically pick a message based on how much they emitted
                    if final_co2 == 0:
                        st.info("🍃 You went absolutely nowhere! Zero emissions. The Earth thanks you.")
                    elif final_co2 < 500:
                        st.info(f"📱 **Fun Fact:** Your drive put the same amount of CO2 into the air as charging your smartphone **{phones_charged} times**!")
                    elif final_co2 < 2000:
                        st.warning(f"🌳 **Fun Fact:** It will take about **{trees_day} mature tree(s)** an entire day to absorb the CO2 from this trip.")
                    else:
                        st.error(f"🌍 **Fun Fact:** That's a heavy trip! You emitted the equivalent of manufacturing **{int(final_co2 / 33)} plastic grocery bags**. Consider carpooling next time!")
                    
                    
                    
                except Exception as e:
                    st.error(f"Database Error: {e}")
            else:
                st.warning("No active trip to end! Click 'Start Trip' first.")

    # 4. Active Tracking Logic
    if st.session_state['tracking_active']:
        st_autorefresh(interval=4000, limit=None, key="live_gps_tracker")
        
        st.markdown("### Tracking is Active 🟢")
        st.write("Drive safely! Your route is updating automatically.")
        
        # Grab location from browser
        location = streamlit_geolocation()
        
        if location and location.get('latitude') is not None:
            current_lat = location['latitude']
            current_lon = location['longitude']
            
            # Save coordinate to our route list (Format: [Lon, Lat])
            if not st.session_state['route_coords'] or st.session_state['route_coords'][-1] != [current_lon, current_lat]:
                st.session_state['route_coords'].append([current_lon, current_lat])

            # If we have a previous point, calculate distance
            if st.session_state['last_lat'] is not None and st.session_state['last_lon'] is not None:
                dist = calculate_distance(
                    st.session_state['last_lat'], st.session_state['last_lon'], 
                    current_lat, current_lon
                )
                
                # Filter out GPS jitter (e.g., jumps less than 10 meters)
                if dist > 0.01: 
                    st.session_state['total_km'] += dist
            
            # Update last known location
            st.session_state['last_lat'] = current_lat
            st.session_state['last_lon'] = current_lon

    # 5. Live Dashboard Display
    st.divider()
    current_co2 = st.session_state['total_km'] * emission_factor
    
    dash_col1, dash_col2 = st.columns(2)
    with dash_col1:
        st.markdown(f"""
            <div class="report-card" style="text-align: center;">
                <p style="color: #666; margin-bottom: 0;">DISTANCE DRIVEN</p>
                <h1 style="color: #2196F3;">{st.session_state['total_km']:.2f} <span style="font-size: 20px;">km</span></h1>
            </div>
        """, unsafe_allow_html=True)
    with dash_col2:
        st.markdown(f"""
            <div class="report-card" style="text-align: center; border-top: 5px solid #FF9800;">
                <p style="color: #666; margin-bottom: 0;">LIVE CO2 EMITTED</p>
                <h1 style="color: #FF9800;">{current_co2:.1f} <span style="font-size: 20px;">grams</span></h1>
            </div>
        """, unsafe_allow_html=True)

    # 6. Live Route Map (Pydeck)
    st.markdown("### 🗺️ Live Route")
    
    if len(st.session_state['route_coords']) > 0:
        # Get the most recent location to center the map
        current_lon, current_lat = st.session_state['route_coords'][-1]
        
        # Format the data exactly how Pydeck's PathLayer wants it
        path_data = pd.DataFrame({
            "path": [st.session_state['route_coords']]
        })

        # Set the starting camera angle and zoom
        view_state = pdk.ViewState(
            latitude=current_lat, 
            longitude=current_lon, 
            zoom=15, 
            pitch=45 # Tilts the map for a cool 3D effect
        )

        # Draw the blue route line
        path_layer = pdk.Layer(
            type="PathLayer",
            data=path_data,
            pickable=True,
            get_color=[33, 150, 243], # Blue color
            width_scale=20,
            width_min_pixels=4,
            get_path="path",
            get_width=5,
        )

        # Draw a red dot at the current location
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=pd.DataFrame({"lon": [current_lon], "lat": [current_lat]}),
            get_position=["lon", "lat"],
            get_color=[255, 0, 0, 200], # Red dot
            get_radius=30,
        )

        # Render the map in Streamlit
        st.pydeck_chart(pdk.Deck(
            map_style="road",
            layers=[path_layer, scatter_layer],
            initial_view_state=view_state,
            tooltip={"text": "Current Location"}
        ))
    else:
        st.info("Waiting for GPS coordinates... Click 'Start Trip' and allow location access.")

    
    # ---------------------------------------------------------
    # 7. TRIP HISTORY TABLE
    # ---------------------------------------------------------
    st.divider()
    st.markdown("### 🗄️ Recent Trip History")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        history_df = pd.read_sql_query(
            "SELECT trip_date, distance_km, co2_emitted_g FROM live_trips ORDER BY id DESC LIMIT 5", 
            conn
        )
        conn.close()
        
        if not history_df.empty:
            # Keep internal names simple and clean
            history_df.columns = ["date", "distance", "co2"]
            
            max_co2 = float(history_df["co2"].max())
            
            # Render the table with perfectly formatted headers
            st.dataframe(
                history_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "date": st.column_config.TextColumn(
                        "🗓️ DATE & TIME",  # <-- Changed to ALL CAPS
                        width="medium"
                    ),
                    "distance": st.column_config.NumberColumn(
                        "🚗 DISTANCE (KM)", # <-- Changed to ALL CAPS
                        help="Total distance tracked during the trip",
                        format="%.2f",
                        width="small"
                    ),
                    "co2": st.column_config.ProgressColumn(
                        "💨 CO2 EMITTED (GRAMS)", # <-- Changed to ALL CAPS
                        help="Visual representation of carbon emitted",
                        format="%.1f g",
                        min_value=0,
                        max_value=max(500.0, max_co2),
                    ),
                }
            )
            
            # Fetch total lifetime CO2 for a summary metric
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT SUM(co2_emitted_g) FROM live_trips")
            total_historical_co2 = c.fetchone()[0] or 0.0
            conn.close()
            
            st.caption(f"**Total Lifetime Tracking:** You have logged **{total_historical_co2:.1f} grams** of CO2 across all trips.")
            
        else:
            st.info("No trips saved yet! Go for a drive and click 'End & Save Trip' to see your history here.")
            
    except sqlite3.OperationalError:
        st.info("No trips saved yet! Go for a drive and click 'End & Save Trip' to see your history here.")
    except Exception as e:
        st.error(f"Could not load trip history: {e}")
