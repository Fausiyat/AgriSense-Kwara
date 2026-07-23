import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
import json
import os

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

# 2. Function to fetch Live Real-Time Weather from Open-Meteo API
@st.cache_data(ttl=1800)  # Refresh cache every 30 minutes
def fetch_live_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=precipitation_sum,temperature_2m_max,temperature_2m_min&"
        f"past_days=7&forecast_days=1&timezone=Africa%2FLagos"
    )
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            daily = data['daily']
            
            today_rain = daily['precipitation_sum'][-1]
            temp_max = daily['temperature_2m_max'][-1]
            temp_min = daily['temperature_2m_min'][-1]
            
            past_7day_rain = sum(daily['precipitation_sum'][:-1])
            
            dry_days = 0
            for r in reversed(daily['precipitation_sum'][:-1]):
                if r < 1.0:
                    dry_days += 1
                else:
                    break
                    
            return {
                "today_rain": today_rain,
                "temp_avg": round((temp_max + temp_min) / 2, 1),
                "past_7day_rain": round(past_7day_rain, 1),
                "consecutive_dry_days": dry_days,
                "dates": daily['time'],
                "rain_history": daily['precipitation_sum']
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

# Fetch Real-Time Weather Data
with st.spinner(f"Fetching live weather station data for {selected_lga}..."):
    live_data = fetch_live_weather(coords["lat"], coords["lon"])

if live_data:
    st.write(f"### Live Climate Conditions: **{selected_lga} LGA**")
    
    # 1. Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Today's Rainfall", f"{live_data['today_rain']} mm")
    col2.metric("7-Day Accumulation", f"{live_data['past_7day_rain']} mm")
    col3.metric("Dry Spell Streak", f"{live_data['consecutive_dry_days']} Days")
    col4.metric("Average Temp", f"{live_data['temp_avg']} °C")
    
    st.markdown("---")
    
    # 2. Decision Engine Logic
    st.write("### 🤖 Automated Decision Engine Output")
    
    total_moisture = live_data['past_7day_rain'] + live_data['today_rain']
    dry_streak = live_data['consecutive_dry_days']
    
    if total_moisture >= 30.0 and dry_streak <= 2:
        status_code = "GREEN"
        st.success("🟢 **DECISION: SAFE TO PLANT**")
        st.info(f"Optimal moisture detected in {selected_lga} ({total_moisture:.1f}mm past 7 days + today). Safe window for germination.")
    elif total_moisture >= 15.0 and dry_streak <= 4:
        status_code = "YELLOW"
        st.warning("🟡 **DECISION: CAUTION / HOLD**")
        st.write("Moderate soil moisture. Wait 24–48 hours for additional rainfall confirmation before planting.")
    else:
        status_code = "RED"
        st.error("🔴 **DECISION: DO NOT PLANT**")
        st.write("Drought risk detected. Soil moisture is below the required threshold for maize seeds.")
        
    # 3. Termii SMS Broadcast Block
    st.markdown("---")
    st.write("### 📲 Dispatch Real-Time Alert to Registered Farmers")

    sms_message = (
        f"🌾 [AgriSense {selected_lga}]\n"
        f"Status: {status_code}\n"
        f"Today's Rain: {live_data['today_rain']}mm. "
        f"7-Day Total: {live_data['past_7day_rain']}mm.\n"
        f"Advisory: "
    )

    if status_code == "GREEN":
        sms_message += "Soil moisture is safe! You can begin planting your maize seeds now."
    elif status_code == "YELLOW":
        sms_message += "Moderate moisture. Hold off planting for 24-48 hours until next rain update."
    else:
        sms_message += "Drought risk high. Do NOT plant seeds yet to avoid germination failure."

    st.text_area("Live Broadcast Preview:", sms_message, height=120)

    farmer_phone = st.text_input("Test Farmer Phone Number (International format):", "2348143086509")

    if st.button("🚀 Send SMS Alert via Termii"):
        payload = {
            "to": farmer_phone,
            "from": "N-Alert",  # Swap to "AgriSense" once approved
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

    # 4. Charting Trend
    st.markdown("---")
    st.write(f"### 📊 7-Day Rainfall Trend for {selected_lga}")
    df_trend = pd.DataFrame({
        "Date": live_data["dates"],
        "Rainfall (mm)": live_data["rain_history"]
    })
    st.bar_chart(df_trend.set_index("Date"))

else:
    st.error("Could not load real-time weather data. Check your internet connection.")
