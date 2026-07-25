import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
import datetime

# --- EBULKSMS API CONFIGURATION ---
try:
    EBULKSMS_USERNAME = st.secrets["EBULKSMS_USERNAME"]
    EBULKSMS_API_KEY = st.secrets["EBULKSMS_API_KEY"]
except Exception:
    # Fallback for local testing:
    EBULKSMS_USERNAME = "fausiyatmahmood@gmail.com"
    EBULKSMS_API_KEY = "b4619b7c11b37261ed1858cccbf223362b8c0a9a20fa1e36425b3fc759764474"

# Page Configuration
st.set_page_config(
    page_title="AgriSense Kwara - Climate & Advisory Broadcast System",
    page_icon="🌾",
    layout="wide"
)

st.title("🌾 AgriSense Kwara (v2 Engine)")
st.subheader("Google Earth Engine & Open-Meteo Dynamic Advisory & SMS Dispatch System")
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
            "advisory": "Crop mature. Stop all watering to allow proper field drying before harvest."
        }

    if consecutive_dry_days >= max_dry:
        if forecast_3day_rain >= 15.0:
            status = "WAIT_FOR_RAIN"
            action = "🟡 HOLD OFF IRRIGATING"
            advisory = f"Soil is dry ({consecutive_dry_days} days), but ~{forecast_3day_rain:.1f}mm rain expected in 72h. Save water."
        else:
            if "Flowering" in stage:
                status = "EMERGENCY_IRRIGATE"
                action = "🚨 CRITICAL: IRRIGATE IMMEDIATELY"
                advisory = f"CRITICAL PHASE! {consecutive_dry_days} dry days detected. Delay risks 35-100% pollination failure!"
            else:
                status = "IRRIGATE_NOW"
                action = "🔵 IRRIGATE NOW"
                advisory = f"Dry spell limit reached for {stage}. Apply ~{daily_need * 3:.1f}mm water."
    else:
        status = "MOISTURE_SAFE"
        action = "🟢 MOISTURE OPTIMAL"
        advisory = f"Soil moisture adequate for {stage} stage. No extra watering required."

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
            daily = data['daily']
            today_index = 7

            today_rain = daily['precipitation_sum'][today_index]
            temp_max = daily['temperature_2m_max'][today_index]
            temp_min = daily['temperature_2m_min'][today_index]

            past_7day_rain = sum(daily['precipitation_sum'][:today_index])
            forecast_3day_rain = sum(daily['precipitation_sum'][today_index+1:today_index+4])

            dry_days = 0
            for r in reversed(daily['precipitation_sum'][:today_index]):
                if r < 1.0: dry_days += 1
                else: break

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

# Load Upgraded Model v2
@st.cache_resource
def load_agrisense_model():
    # Load Model v2 if available, else fall back to v1
    for model_file in ["agrisense_kwara_model_v2.pkl", "agrisense_kwara_model.pkl"]:
        try:
            m = joblib.load(model_file)
            return m, model_file
        except Exception:
            continue
    return None, None

model, model_file_name = load_agrisense_model()

if model is None:
    st.error("⚠️ Model file not found. Ensure 'agrisense_kwara_model_v2.pkl' is uploaded to your app root folder.")

# UI Navigation Tabs
tab1, tab2 = st.tabs(["📊 Single Farm Interactive Dashboard", "🚀 Multi-Farmer Batch SMS Dispatcher"])

# --- TAB 1: SINGLE FARM DASHBOARD ---
with tab1:
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

    if live_data and model:
        st.markdown(f"#### Live Climate Metrics ({selected_lga} LGA)")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Today Rain", f"{live_data['today_rain']} mm")
        c2.metric("Past 7-Day Rain", f"{live_data['past_7day_rain']} mm")
        c3.metric("3-Day Forecast Rain", f"{live_data['forecast_3day_rain']} mm")
        c4.metric("Dry Days Streak", f"{live_data['consecutive_dry_days']} Days")
        c5.metric("Avg Temp", f"{live_data['temp_avg']} °C")

        # 7-Feature Model Inference
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
            planting_advisory = "Optimal moisture and 3-day forecast conditions predicted for maize seed germination."
        elif 50 <= prob_safe < 80:
            st.warning(f"🟡 **MODERATE PLANTING RISK ({prob_safe:.1f}% Confidence)**")
            planting_advisory = "Planting is possible, but ensure light pre-irrigation if dry conditions persist."
        else:
            st.error(f"🔴 **DO NOT PLANT ({prob_safe:.1f}% Confidence)**")
            planting_advisory = "High drought or off-season risk detected. Hold off planting to avoid seed loss."

        irrigation_res = calculate_irrigation_advisory(dap, live_data['consecutive_dry_days'], live_data['forecast_3day_rain'], soil_type)

        st.info(f"**Growth Stage:** {irrigation_res['stage']} | **Irrigation Status:** {irrigation_res['action']}\n\n{irrigation_res['advisory']}")

        st.markdown("---")

        # --- 3. CHARTING TREND ---
        st.write(f"### 📊 7-Day Rainfall Trend for {selected_lga}")
        df_trend = pd.DataFrame({
            "Date": live_data["dates"],
            "Rainfall (mm)": live_data["rain_history"]
        })
        st.bar_chart(df_trend.set_index("Date"))

        st.markdown("---")
        st.markdown("### 📱 Test Single SMS Broadcast")

        single_msg = (
            f"🌾 [AgriSense {selected_lga}]\n"
            f"Planting: {planting_advisory}\n"
            f"Irrigation: {irrigation_res['action']}\n"
            f"Advice: {irrigation_res['advisory']}"
        )
        st.text_area("SMS Preview:", single_msg, height=120)

        test_phone = st.text_input("Enter Phone Number:", "08143086509")
        if st.button("🚀 Send Single Test SMS"):
            phone_clean = test_phone.replace("+", "").strip()

            # --- UPDATED PHONE NUMBER FORMATTING LOGIC FOR SINGLE SMS ---
            if phone_clean.startswith("0"):
                formatted_phone = "234" + phone_clean[1:]
            elif phone_clean.startswith("234"):
                formatted_phone = phone_clean
            else:
                formatted_phone = "234" + phone_clean
            # --- END UPDATED LOGIC ---

            payload = {
                "SMS": {
                    "auth": {"username": EBULKSMS_USERNAME, "apikey": EBULKSMS_API_KEY},
                    "message": {"sender": "AgriSense", "messagetext": single_msg, "flash": "0", "dndsender": "1"},
                    "recipients": {"gsm": [{"msidn": formatted_phone, "msgid": f"single_{selected_lga}_{dap}"}]}
                }
            }
            res = requests.post("https://api.ebulksms.com/sendsms.json", json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
            st.write("EbulkSMS API Response:", res.json())

# --- TAB 2: MULTI-FARMER BATCH SMS DISPATCHER ---
with tab2:
    st.markdown("### 📋 Upload Recipient Roster (20 Farmers Pilot)")
    uploaded_file = st.file_uploader("Upload Farmers File (.xlsx or .csv)", type=["xlsx", "csv"])

    if uploaded_file and model:
        df_farmers = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
        st.markdown("#### Farmer Roster Preview")
        st.dataframe(df_farmers.head(10))

        if st.button("🚀 Execute Daily LGA Batch Broadcast"):
            dispatch_logs = []
            today_date = datetime.date.today()
            day_of_year = today_date.timetuple().tm_yday

            # Grouping dispatches by LGA
            for lga_name, group in df_farmers.groupby("LGA"):
                clean_lga = str(lga_name).strip()
                if clean_lga not in LGA_COORDINATES:
                    st.warning(f"LGA '{clean_lga}' coordinates not configured. Skipping {len(group)} farmer(s).")
                    continue

                # Fetch LGA level weather once per group
                coords = LGA_COORDINATES[clean_lga]
                weather = fetch_live_weather(coords["lat"], coords["lon"])
                if not weather:
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

                # Send personalized SMS per farmer
                for _, row in group.iterrows():
                    farmer_name = str(row.get('Name', 'Farmer')).strip()
                    raw_phone = str(row.get('Phone', '')).replace("+", "").strip()
                    soil = str(row.get('Soil_Type', 'Loam/Clay')).strip()

                    if raw_phone.startswith("0"):
                        formatted_phone = "234" + raw_phone[1:]
                    elif raw_phone.startswith("234"):
                        formatted_phone = raw_phone
                    else:
                        formatted_phone = "234" + raw_phone

                    try:
                        p_date = pd.to_datetime(row['Planting_Date']).date()
                        dap = max(0, (today_date - p_date).days)
                    except Exception:
                        dap = 0

                    irrigation = calculate_irrigation_advisory(dap, weather['consecutive_dry_days'], weather['forecast_3day_rain'], soil)

                    personalized_msg = (
                        f"🌾 AgriSense ({clean_lga})\n"
                        f"Hello {farmer_name},\n"
                        f"Planting: {planting_status} ({prob_safe:.0f}% Conf)\n"
                        f"Irrigation: {irrigation['action']}\n"
                        f"{irrigation['advisory']}"
                    )

                    payload = {
                        "SMS": {
                            "auth": {"username": EBULKSMS_USERNAME, "apikey": EBULKSMS_API_KEY},
                            "message": {"sender": "AgriSense", "messagetext": personalized_msg, "flash": "0", "dndsender": "1"},
                            "recipients": {"gsm": [{"msidn": formatted_phone, "msgid": f"batch_{clean_lga}_{dap}"}]}
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
                        "Dispatch Status": status
                    })

            st.success("🎉 Batch Broadcast Execution Completed!")
            st.markdown("### 📊 Live Dispatch Execution Report")
            st.dataframe(pd.DataFrame(dispatch_logs))
