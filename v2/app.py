# 1. IMPORTS
import os
import datetime
import warnings
import requests
import joblib
import numpy as np
import pandas as pd
import streamlit as st

# Mute Scikit-Learn version mismatch warnings in deployment logs
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

# 2. PATH SETUP
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 3. PAGE CONFIGURATION
st.set_page_config(
    page_title="AgriSense Kwara - Climate & Advisory Broadcast System",
    page_icon="🌾",
    layout="wide"
)

# 4. EBULKSMS API CONFIGURATION
try:
    EBULKSMS_USERNAME = st.secrets["EBULKSMS_USERNAME"]
    EBULKSMS_API_KEY = st.secrets["EBULKSMS_API_KEY"]
except Exception:
    # Safe fallback pulling directly from secrets dictionary without throwing KeyError
    EBULKSMS_USERNAME = st.secrets.get("EBULKSMS_USERNAME", "")
    EBULKSMS_API_KEY = st.secrets.get("EBULKSMS_API_KEY", "")

st.title("🌾 AgriSense Kwara (v2 Engine)")
st.subheader("Google Earth Engine & Open-Meteo Dynamic Advisory & SMS Dispatch System")
st.markdown("---")

# Geographic Coordinates for Kwara State LGAs [Latitude, Longitude]
LGA_COORDINATES = {
    "Ilorin_West": {"lat": 8.4900, "lon": 4.5421},
    "Ilorin_East": {"lat": 8.5333, "lon": 4.6333},
    "Ilorin_South": {"lat": 8.4333, "lon": 4.5500},
    "Asa": {"lat": 8.4167, "lon": 4.3333},
    "Kaiama": {"lat": 9.6053, "lon": 3.9410},
    "Ifelodun": {"lat": 8.3167, "lon": 4.7167}
}

# Helper: Phone Number Standardization (234 Format)
def format_nigerian_phone(raw_phone):
    phone_clean = str(raw_phone).replace("+", "").replace(" ", "").strip()
    if phone_clean.startswith("0"):
        return "234" + phone_clean[1:]
    elif phone_clean.startswith("234"):
        return phone_clean
    else:
        return "234" + phone_clean

# Helper: Growing Degree Days (GDD)
def calculate_gdd(temp):
    base_temp, cap_temp = 10.0, 30.0
    effective_temp = min(max(temp, base_temp), cap_temp)
    return max(0, effective_temp - base_temp)

# Helper: Irrigation Advisory Engine
def calculate_irrigation_advisory(dap, consecutive_dry_days, forecast_3day_rain, soil_type="Loam/Clay"):
    dry_limit_factor = 0.6 if str(soil_type).lower() == "sandy" else 1.0

    if 0 <= dap <= 15:
        stage, max_dry, daily_need = "Establishment (Days 0-15)", max(1, int(2 * dry_limit_factor)), 1.2
    elif 16 <= dap <= 45:
        stage, max_dry, daily_need = "Vegetative Growth (Days 16-45)", max(2, int(5 * dry_limit_factor)), 4.3
    elif 46 <= dap <= 65:
        stage, max_dry, daily_need = "Flowering & Silking (Days 46-65) ⚠️", max(1, int(3 * dry_limit_factor)), 6.5
    elif 66 <= dap <= 100:
        stage, max_dry, daily_need = "Grain Filling (Days 66-100)", max(2, int(4 * dry_limit_factor)), 6.3
    else:
        return {
            "stage": "Maturation / Drying (Days 101+)",
            "status": "STOP_IRRIGATION",
            "action": "🟢 STOP IRRIGATION",
            "advisory": "Crop mature. Stop watering for field drying before harvest."
        }

    if consecutive_dry_days >= max_dry:
        if forecast_3day_rain >= 15.0:
            status = "WAIT_FOR_RAIN"
            action = "🟡 HOLD OFF IRRIGATING"
            advisory = f"Soil dry ({consecutive_dry_days}d), but ~{forecast_3day_rain:.1f}mm rain in 72h. Save water."
        else:
            if "Flowering" in stage:
                status = "EMERGENCY_IRRIGATE"
                action = "🚨 CRITICAL: IRRIGATE NOW"
                advisory = f"CRITICAL! {consecutive_dry_days} dry days. Delay risks 35-100% pollination failure!"
            else:
                status = "IRRIGATE_NOW"
                action = "🔵 IRRIGATE NOW"
                advisory = f"Dry limit reached. Apply ~{daily_need * 3:.1f}mm water."
    else:
        status = "MOISTURE_SAFE"
        action = "🟢 MOISTURE OPTIMAL"
        advisory = f"Moisture adequate for {stage}. No extra watering needed."

    return {"stage": stage, "status": status, "action": action, "advisory": advisory}

# Fetch Live Weather from Open-Meteo REST API
@st.cache_data(ttl=1800)
def fetch_live_weather(lat, lon):
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
            daily = data.get('daily', {})
            
            precip = daily.get('precipitation_sum', [])
            t_max_list = daily.get('temperature_2m_max', [])
            t_min_list = daily.get('temperature_2m_min', [])

            # Clean lists replacing None with safe defaults
            raw_precip = [0.0 if p is None else float(p) for p in precip]
            t_max = [28.0 if t is None else float(t) for t in t_max_list]
            t_min = [22.0 if t is None else float(t) for t in t_min_list]

            # Use last available past day index safely
            today_index = min(7, len(raw_precip) - 1) if len(raw_precip) > 0 else 0

            today_rain = raw_precip[today_index] if today_index < len(raw_precip) else 0.0
            temp_max = t_max[today_index] if today_index < len(t_max) else 28.0
            temp_min = t_min[today_index] if today_index < len(t_min) else 22.0

            past_7day_rain = sum(raw_precip[:today_index])
            forecast_3day_rain = sum(raw_precip[today_index+1:today_index+4])

            dry_days = 0
            for r in reversed(raw_precip[:today_index]):
                if r < 1.0: 
                    dry_days += 1
                else: 
                    break

            dates = daily.get('time', [])[:today_index+1]
            rain_hist = raw_precip[:today_index+1]

            return {
                "today_rain": round(today_rain, 1),
                "temp_avg": round((temp_max + temp_min) / 2, 1),
                "past_7day_rain": round(past_7day_rain, 1),
                "forecast_3day_rain": round(forecast_3day_rain, 1),
                "consecutive_dry_days": dry_days,
                "dates": dates,
                "rain_history": rain_hist
            }
        else:
            st.error(f"Open-Meteo API Error Code: {response.status_code}")
    except Exception as e:
        st.error(f"Weather Fetch Exception: {e}")
    return None

# Load Upgraded Model v2 dynamically
@st.cache_resource
def load_agrisense_model():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for model_file in ["agrisense_kwara_model_v2.pkl", "agrisense_kwara_model.pkl"]:
        model_path = os.path.join(current_dir, model_file)
        if os.path.exists(model_path):
            try:
                m = joblib.load(model_path)
                return m, model_file
            except Exception as err:
                st.error(f"Failed to unpickle {model_file}: {err}")
                continue
    return None, None

model, model_file_name = load_agrisense_model()

# UI Navigation Tabs
tab1, tab2 = st.tabs(["📊 Single Farm Interactive Dashboard", "🚀 Multi-Farmer Batch SMS Dispatcher"])

# --- TAB 1: SINGLE FARM DASHBOARD ---
with tab1:
    if model is None:
        st.error(f"⚠️ Model file `agrisense_kwara_model_v2.pkl` not found in directory: `{BASE_DIR}`.")
    
    col_sel1, col_sel2, col_sel3 = st.columns(3)
    with col_sel1:
        selected_lga = st.selectbox("Select Kwara State LGA:", list(LGA_COORDINATES.keys()), key="single_lga")
    with col_sel2:
        planting_date = st.date_input("Planting Date:", datetime.date.today(), key="single_pdate")
    with col_sel3:
        soil_type = st.selectbox("Farm Soil Type:", ["Loam/Clay", "Sandy"], key="single_soil")

    today_date = datetime.date.today()
    dap = max(0, (today_date - planting_date).days)
    day_of_year = today_date.timetuple().tm_yday

    coords = LGA_COORDINATES[selected_lga]
    live_data = fetch_live_weather(coords["lat"], coords["lon"])

    if live_data:
        st.markdown(f"#### Live Climate Metrics ({selected_lga} LGA)")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Today Rain", f"{live_data['today_rain']} mm")
        c2.metric("Past 7-Day Rain", f"{live_data['past_7day_rain']} mm")
        c3.metric("3-Day Forecast Rain", f"{live_data['forecast_3day_rain']} mm")
        c4.metric("Dry Days Streak", f"{live_data['consecutive_dry_days']} Days")
        c5.metric("Avg Temp", f"{live_data['temp_avg']} °C")

        # Calculate Irrigation Advisory
        irrigation_res = calculate_irrigation_advisory(dap, live_data['consecutive_dry_days'], live_data['forecast_3day_rain'], soil_type)

        # Calculate Model Prediction if available
        planting_advisory = "N/A"
        if model is not None:
            gdd = calculate_gdd(live_data['temp_avg'])
            X_live = pd.DataFrame([[
                live_data['today_rain'],
                live_data['temp_avg'],
                gdd,
                live_data['past_7day_rain'],
                live_data['consecutive_dry_days'],
                live_data['forecast_3day_rain'],
                day_of_year
            ]], columns=['rainfall_mm', 'temp_celsius', 'gdd', 'rain_7day_sum', 'consecutive_dry_days', 'forecast_3day_rain', 'day_of_year'])

            prob_safe = model.predict_proba(X_live)[0][1] * 100

            st.markdown("---")
            st.markdown("### 🤖 Upgraded Model Decision Output")

            if prob_safe >= 80:
                st.success(f"🟢 **SAFE TO PLANT ({prob_safe:.1f}% Confidence)**")
                planting_advisory = "SAFE TO PLANT: Optimal moisture & 3-day forecast conditions predicted."
            elif 50 <= prob_safe < 80:
                st.warning(f"🟡 **MODERATE PLANTING RISK ({prob_safe:.1f}% Confidence)**")
                planting_advisory = "MODERATE RISK: Ensure light pre-irrigation if dry conditions persist."
            else:
                st.error(f"🔴 **DO NOT PLANT ({prob_safe:.1f}% Confidence)**")
                planting_advisory = "DO NOT PLANT: High drought/off-season risk detected."

        st.info(f"**Growth Stage:** {irrigation_res['stage']} | **Irrigation Status:** {irrigation_res['action']}\n\n{irrigation_res['advisory']}")

        st.markdown("---")

        # Charting Trend
        st.write(f"### 📊 7-Day Rainfall Trend for {selected_lga}")
        df_trend = pd.DataFrame({
            "Date": live_data["dates"],
            "Rainfall (mm)": live_data["rain_history"]
        })
        df_trend["Rainfall (mm)"] = df_trend["Rainfall (mm)"].fillna(0.0)
        st.bar_chart(df_trend.set_index("Date"))

        st.markdown("---")
        st.markdown("### 📱 Test Single SMS Broadcast")

        default_single_msg = (
            f"AgriSense({selected_lga}): {planting_advisory} "
            f"Irrigation: {irrigation_res['action']}. {irrigation_res['advisory']}"
        )
        
        single_msg = st.text_area("SMS Content:", default_single_msg, height=100)
        
        msg_len = len(single_msg)
        segments = (msg_len // 160) + 1
        if msg_len <= 160:
            st.caption(f"📏 **Length:** {msg_len}/160 chars (1 SMS segment)")
        else:
            st.warning(f"⚠️ **Length:** {msg_len} chars ({segments} SMS segments). Keep under 160 characters to optimize pilot dispatch costs.")

        test_phone = st.text_input("Enter Phone Number:", "08143086509")
        if st.button("🚀 Send Single Test SMS"):
            formatted_phone = format_nigerian_phone(test_phone)
            unique_id = f"single_{selected_lga}_{dap}_{int(datetime.datetime.now().timestamp())}"

            payload = {
                "SMS": {
                    "auth": {"username": EBULKSMS_USERNAME, "apikey": EBULKSMS_API_KEY},
                    "message": {"sender": "AgriSense", "messagetext": single_msg, "flash": "0", "dndsender": "1"},
                    "recipients": {"gsm": [{"msidn": formatted_phone, "msgid": unique_id}]}
                }
            }
            res = requests.post("https://api.ebulksms.com/sendsms.json", json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
            st.write("EbulkSMS API Response:", res.json())

# --- TAB 2: MULTI-FARMER BATCH SMS DISPATCHER ---
with tab2:
    st.markdown("### 📋 Upload Recipient Roster (50 Farmers Target)")
    uploaded_file = st.file_uploader("Upload Farmers File (.xlsx or .csv)", type=["xlsx", "csv"])

    if uploaded_file:
        df_farmers = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
        st.markdown("#### Farmer Roster Preview")
        st.dataframe(df_farmers.head(10))

        if st.button("🚀 Execute Daily LGA Batch Broadcast"):
            if model is None:
                st.error("Cannot run prediction: Model `agrisense_kwara_model_v2.pkl` is missing.")
            else:
                dispatch_logs = []
                today_date = datetime.date.today()
                day_of_year = today_date.timetuple().tm_yday

                with st.spinner("Processing weather forecasts and generating advisories..."):
                    for lga_name, group in df_farmers.groupby("LGA"):
                        clean_lga = str(lga_name).strip()
                        if clean_lga not in LGA_COORDINATES:
                            st.warning(f"LGA '{clean_lga}' coordinates not configured. Skipping {len(group)} farmer(s).")
                            continue

                        coords = LGA_COORDINATES[clean_lga]
                        weather = fetch_live_weather(coords["lat"], coords["lon"])
                        if not weather:
                            st.error(f"Failed to fetch weather data for {clean_lga}. Skipping group.")
                            continue

                        gdd = calculate_gdd(weather['temp_avg'])
                        X_live = pd.DataFrame([[
                            weather['today_rain'],
                            weather['temp_avg'],
                            gdd,
                            weather['past_7day_rain'],
                            weather['consecutive_dry_days'],
                            weather['forecast_3day_rain'],
                            day_of_year
                        ]], columns=['rainfall_mm', 'temp_celsius', 'gdd', 'rain_7day_sum', 'consecutive_dry_days', 'forecast_3day_rain', 'day_of_year'])

                        prob_safe = model.predict_proba(X_live)[0][1] * 100
                        planting_status = "SAFE TO PLANT" if prob_safe >= 80 else "DO NOT PLANT"

                        for idx, row in group.iterrows():
                            farmer_name = str(row.get('Name', 'Farmer')).strip()
                            raw_phone = str(row.get('Phone', '')).strip()
                            soil = str(row.get('Soil_Type', 'Loam/Clay')).strip()

                            formatted_phone = format_nigerian_phone(raw_phone)

                            try:
                                p_date = pd.to_datetime(row['Planting_Date']).date()
                                dap = max(0, (today_date - p_date).days)
                            except Exception:
                                dap = 0

                            irrigation = calculate_irrigation_advisory(dap, weather['consecutive_dry_days'], weather['forecast_3day_rain'], soil)

                            # Structured concise message to guarantee single SMS segment (<160 chars)
                            personalized_msg = (
                                f"AgriSense({clean_lga}): Hi {farmer_name}, "
                                f"Plant: {planting_status} ({prob_safe:.0f}%). "
                                f"Irrigate: {irrigation['action']}. {irrigation['advisory']}"
                            )[:160]

                            # Ensure unique message ID per row index
                            unique_msgid = f"batch_{clean_lga}_{dap}_{idx}"

                            payload = {
                                "SMS": {
                                    "auth": {"username": EBULKSMS_USERNAME, "apikey": EBULKSMS_API_KEY},
                                    "message": {"sender": "AgriSense", "messagetext": personalized_msg, "flash": "0", "dndsender": "1"},
                                    "recipients": {"gsm": [{"msidn": formatted_phone, "msgid": unique_msgid}]}
                                }
                            }

                            try:
                                res = requests.post("https://api.ebulksms.com/sendsms.json", json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
                                res_json = res.json()
                                status = res_json.get("response", {}).get("status", "FAILED")
                            except Exception as err:
                                status = f"ERROR: {err}"

                            dispatch_logs.append({
                                "Farmer Name": farmer_name,
                                "Phone": formatted_phone,
                                "LGA": clean_lga,
                                "Crop Age (DAP)": dap,
                                "Planting Advisory": planting_status,
                                "Dispatch Status": status,
                                "SMS Length": len(personalized_msg)
                            })

                st.success("🎉 Batch Broadcast Execution Completed!")
                st.markdown("### 📊 Live Dispatch Execution Report")
                st.dataframe(pd.DataFrame(dispatch_logs))
