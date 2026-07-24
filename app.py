import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
import json
import os
import datetime

# --- TERMII API KEY CONFIGURATION ---
try:
    TERMII_API_KEY = st.secrets["TERMII_API_KEY"]
except Exception:
    TERMII_API_KEY = "tlv_Hn4rlapWW6cTRqdHB5sWSKiwSNepn-VSBab_mQ08blk"

# Page Configuration
st.set_page_config(
    page_title="AgriSense Kwara - Live Weather & Planting Advisory",
    page_icon="🌾",
    layout="wide"
)

# Header
st.title("🌾 AgriSense Kwara")
st.subheader("Real-Time Climate Monitoring & Maize Planting Advisory Engine")
st.markdown("---")

# 1. Geographic Coordinates for Kwara State LGAs [Latitude, Longitude]
LGA_COORDINATES = {
    "Ilorin_West": {"lat": 8.4900, "lon": 4.5421},
    "Ilorin_East": {"lat": 8.5333, "lon": 4.6333},
    "Ilorin_South": {"lat": 8.4333, "lon": 4.5500},
    "Asa": {"lat": 8.4167, "lon": 4.3333},
    "Kaiama": {"lat": 9.6053, "lon": 3.9410},
    "Ifelodun": {"lat": 8.3167, "lon": 4.7167}
}

# --- Helper function for Growing Degree Days (GDD) ---
def calculate_gdd(temp):
    base_temp = 10.0
    cap_temp = 30.0
    effective_temp = min(max(temp, base_temp), cap_temp)
    return max(0, effective_temp - base_temp)

# --- Helper function for Irrigation Advisory ---
def calculate_irrigation_advisory(dap, consecutive_dry_days, forecast_3day_rain, soil_type="Loam/Clay"):
    """
    Computes real-time irrigation guidance based on Growth Stage (DAP),
    soil moisture retention, and short-term rainfall forecasts.
    """
    dry_limit_factor = 0.6 if soil_type.lower() == "sandy" else 1.0
    
    if 0 <= dap <= 15:
        stage = "Establishment (Days 0-15)"
        max_dry_allowed = max(1, int(2 * dry_limit_factor))
        daily_need = 1.2
    elif 16 <= dap <= 45:
        stage = "Vegetative Growth (Days 16-45)"
        max_dry_allowed = max(2, int(5 * dry_limit_factor))
        daily_need = 4.3
    elif 46 <= dap <= 65:
        stage = "Flowering & Silking (Days 46-65) ⚠️"
        max_dry_allowed = max(1, int(3 * dry_limit_factor))
        daily_need = 6.5
    elif 66 <= dap <= 100:
        stage = "Grain Filling (Days 66-100)"
        max_dry_allowed = max(2, int(4 * dry_limit_factor))
        daily_need = 6.3
    else:
        return {
            "stage": "Maturation / Drying (Days 101+)",
            "status": "STOP_IRRIGATION",
            "action": "🟢 STOP IRRIGATION",
            "advisory": "Crop has reached physiological maturity. Stop all watering to allow proper field drying before harvest."
        }

    # Decision Engine Logic
    if consecutive_dry_days >= max_dry_allowed:
        if forecast_3day_rain >= 15.0:
            status = "WAIT_FOR_RAIN"
            action = "🟡 HOLD OFF IRRIGATING"
            advisory = (f"Soil is dry ({consecutive_dry_days} days), but substantial rain ({forecast_3day_rain:.1f}mm) "
                        f"is forecasted within 72 hours. Save water and wait for natural rainfall.")
        else:
            if "Flowering" in stage:
                status = "EMERGENCY_IRRIGATE"
                action = "🚨 CRITICAL: IRRIGATE IMMEDIATELY"
                advisory = (f"CRITICAL PHASE! Crop is in flowering/silking. {consecutive_dry_days} dry days detected "
                            f"with low rain forecast. Delaying irrigation risks 35-100% pollination failure!")
            else:
                status = "IRRIGATE_NOW"
                action = "🔵 IRRIGATE NOW"
                advisory = (f"Dry spell limit reached for {stage}. Apply ~{daily_need * 3:.1f}mm of water "
                            f"to replenish root moisture.")
    else:
        status = "MOISTURE_SAFE"
        action = "🟢 MOISTURE OPTIMAL"
        advisory = f"Current soil moisture is adequate for the {stage} stage. No extra watering required today."

    return {
        "stage": stage,
        "status": status,
        "action": action,
        "advisory": advisory
    }

# 2. Function to fetch Live Real-Time Weather from Open-Meteo API
@st.cache_data(ttl=1800)  # Refresh cache every 30 minutes
def fetch_live_weather(lat, lon):
    # Notice: forecast_days=3 so we get future 3-day precipitation for the irrigation model
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=precipitation_sum,temperature_2m_max,temperature_2m_min&"
        f"past_days=7&forecast_days=3&timezone=Africa%2FLagos"
    )
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            daily = data['daily']

            # Today's live index is position 7 (0 to 6 are past 7 days)
            today_index = 7
            today_rain = daily['precipitation_sum'][today_index]
            temp_max = daily['temperature_2m_max'][today_index]
            temp_min = daily['temperature_2m_min'][today_index]

            # Calculate 7-day past accumulated rainfall
            past_7day_rain = sum(daily['precipitation_sum'][:today_index])

            # Calculate 3-day future forecasted rainfall
            forecast_3day_rain = sum(daily['precipitation_sum'][today_index+1:today_index+4])

            # Count consecutive dry days in the past week
            dry_days = 0
            for r in reversed(daily['precipitation_sum'][:today_index]):
                if r < 1.0:
                    dry_days += 1
                else:
                    break

            return {
                "today_rain": today_rain,
                "temp_avg": round((temp_max + temp_min) / 2, 1),
                "past_7day_rain": round(past_7day_rain, 1),
                "forecast_3day_rain": round(forecast_3day_rain, 1),
                "consecutive_dry_days": dry_days,
                "dates": daily['time'][:today_index+1],
                "rain_history": daily['precipitation_sum'][:today_index+1]
            }
    except Exception as e:
        st.error(f"Error fetching live weather: {e}")
    return None

# Sidebar Controls
st.sidebar.header("📍 Select Location")
selected_lga = st.sidebar.selectbox(
    "Select Kwara State LGA:",
    list(LGA_COORDINATES.keys())
)

coords = LGA_COORDINATES[selected_lga]

st.sidebar.markdown("---")
st.sidebar.header("🌽 Farm Management Profile")
planting_date = st.sidebar.date_input("Select Planting Date:", datetime.date.today())
soil_type = st.sidebar.selectbox("Select Farm Soil Type:", ["Loam/Clay", "Sandy"])

# Calculate Days After Planting (DAP) dynamically
today = datetime.date.today()
dap = (today - planting_date).days
if dap < 0:
    dap = 0
st.sidebar.info(f"Crop Age: **{dap} Days After Planting (DAP)**")

# Fetch Real-Time Weather Data for the chosen LGA
with st.spinner(f"Fetching live weather station data for {selected_lga}..."):
    live_data = fetch_live_weather(coords["lat"], coords["lon"])

# Load Trained ML Model
try:
    model = joblib.load('agrisense_kwara_model.pkl')
    model_loaded = True
except Exception as e:
    st.error(f"Error loading ML model: {e}. Ensure 'agrisense_kwara_model.pkl' exists.")
    model_loaded = False

# --- MAIN DASHBOARD DISPLAY ---
if live_data and model_loaded:
    st.write(f"### Live Climate Conditions: **{selected_lga} LGA**")

    # Display Real-Time Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Today's Rainfall", f"{live_data['today_rain']} mm")
    col2.metric("7-Day Accumulation", f"{live_data['past_7day_rain']} mm")
    col3.metric("Dry Spell Streak", f"{live_data['consecutive_dry_days']} Days")
    col4.metric("Average Temp", f"{live_data['temp_avg']} °C")

    st.markdown("---")

    # --- 1. ML PLANTING DECISION ENGINE ---
    st.write("### 🤖 Automated Planting Decision Engine Output")

    current_gdd = calculate_gdd(live_data['temp_avg'])
    X_live = pd.DataFrame([[live_data['today_rain'],
                            live_data['temp_avg'],
                            current_gdd,
                            live_data['past_7day_rain'],
                            live_data['consecutive_dry_days']]],
                          columns=['rainfall_mm', 'temp_celsius', 'gdd', 'rain_7day_sum', 'consecutive_dry_days'])

    prediction = model.predict(X_live)[0]

    if prediction == 1:
        status_code = "GREEN"
        st.success("🟢 **DECISION: SAFE TO PLANT**")
        st.info(f"Optimal conditions predicted in {selected_lga} for maize planting. Safe window for germination.")
        planting_advisory = "Soil moisture is safe! You can begin planting your maize seeds now."
    else:
        status_code = "RED"
        st.error("🔴 **DECISION: DO NOT PLANT**")
        st.write("Unfavorable drought risks predicted in coming days. Hold off planting to avoid germination failure.")
        planting_advisory = "Drought risk high. Do NOT plant seeds yet to avoid germination failure."

    st.markdown("---")

    # --- 2. IRRIGATION RISK & SCHEDULING ENGINE ---
    st.write("### 💧 Irrigation Risk & Scheduling Engine")

    forecast_rain = live_data.get('forecast_3day_rain', 0.0)
    dry_streak = live_data['consecutive_dry_days']

    irrigation_result = calculate_irrigation_advisory(
        dap=dap,
        consecutive_dry_days=dry_streak,
        forecast_3day_rain=forecast_rain,
        soil_type=soil_type
    )

    st.write(f"**Growth Stage:** {irrigation_result['stage']} | **3-Day Rain Forecast:** {forecast_rain} mm")

    if "CRITICAL" in irrigation_result['action']:
        st.error(f"### {irrigation_result['action']}")
    elif "HOLD" in irrigation_result['action']:
        st.warning(f"### {irrigation_result['action']}")
    else:
        st.success(f"### {irrigation_result['action']}")

    st.info(irrigation_result['advisory'])

    # --- 3. CHARTING TREND ---
    st.markdown("---")
    st.write(f"### 📊 7-Day Rainfall Trend for {selected_lga}")
    df_trend = pd.DataFrame({
        "Date": live_data["dates"],
        "Rainfall (mm)": live_data["rain_history"]
    })
    st.bar_chart(df_trend.set_index("Date"))

    # --- 4. TERMII SMS BROADCAST BLOCK ---
    st.markdown("---")
    st.write("### 📲 Dispatch Real-Time Alert to Registered Farmers")

    sms_message = (
        f"🌾 [AgriSense {selected_lga}]\n"
        f"Planting: {status_code} ({planting_advisory})\n"
        f"Irrigation: {irrigation_result['action']}\n"
        f"Details: {irrigation_result['advisory']}"
    )

    st.text_area("Live Broadcast Preview:", sms_message, height=140)

    farmer_phone = st.text_input("Test Farmer Phone Number (International format):", "2348143086509")

    if st.button("🚀 Send SMS Alert via Termii"):
        payload = {
            "to": farmer_phone,
            "from": "N-Alert",
            "sms": sms_message,
            "type": "plain",
            "channel": "generic",
            "api_key": TERMII_API_KEY
        }
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post("https://api.ng.termii.com/api/sms/send", json=payload, headers=headers)
            res_data = response.json()

            if response.status_code == 200 and res_data.get("message") == "Successfully Sent":
                st.success(f"✅ Advisory successfully sent to {farmer_phone} in {selected_lga}!")
            else:
                st.error(f"Failed to send SMS. Response: {res_data}")
        except Exception as e:
            st.error(f"Error connecting to Termii: {e}")

else:
    st.error("Could not load real-time weather data or ML model. Ensure 'agrisense_kwara_model.pkl' is uploaded.")
