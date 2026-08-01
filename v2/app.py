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

# 4. API CONFIGURATION
try:
    EBULKSMS_USERNAME = st.secrets["EBULKSMS_USERNAME"]
    EBULKSMS_API_KEY = st.secrets["EBULKSMS_API_KEY"]
    OPEN_METEO_API_KEY = st.secrets.get("OPEN_METEO_API_KEY", "")
except Exception:
    EBULKSMS_USERNAME = st.secrets.get("EBULKSMS_USERNAME", "")
    EBULKSMS_API_KEY = st.secrets.get("EBULKSMS_API_KEY", "")
    OPEN_METEO_API_KEY = st.secrets.get("OPEN_METEO_API_KEY", "")

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

# ==========================================
# TRANSLATION DICTIONARIES (English & Yoruba)
# ==========================================

# UI Translations for Dashboard Elements
UI_TEXT = {
    "English": {
        "lga_label": "Select Kwara State LGA:",
        "pdate_label": "Planting Date:",
        "soil_label": "Farm Soil Type:",
        "live_metrics_header": "Live Climate Metrics",
        "today_rain": "Today Rain",
        "past_rain": "Past 7-Day Rain",
        "forecast_rain": "3-Day Forecast Rain",
        "dry_streak": "Dry Days Streak",
        "avg_temp": "Avg Temp",
        "model_header": "🤖 Upgraded Model Decision Output",
        "safe_plant": "🟢 SAFE TO PLANT",
        "mod_risk": "🟡 MODERATE PLANTING RISK",
        "no_plant": "🔴 DO NOT PLANT",
        "growth_stage": "Growth Stage",
        "irrig_status": "Irrigation Status",
        "trend_header": "📊 7-Day Rainfall Trend for",
        "sms_header": "📱 Test Single SMS Broadcast",
        "sms_content": "SMS Content:",
        "enter_phone": "Enter Phone Number:",
        "send_sms_btn": "🚀 Send Single Test SMS"
    },
    "Yoruba": {
        "lga_label": "Yan Ijoba Ibile Re ni Kwara:",
        "pdate_label": "Ojo Ti O Gbin Egbin Re:",
        "soil_label": "Iru Erupe Oko Re:",
        "live_metrics_header": "Agbaye Ateworogbo Afefe loni ni LGA",
        "today_rain": "Ojo Loni",
        "past_rain": "Ojo Osese Ko koidi",
        "forecast_rain": "Ojo Ti Nbo Ni Ojo Meta",
        "dry_streak": "Ojo Ti Ojo Ko Ro",
        "avg_temp": "Agbara Ooru",
        "model_header": "🤖 Imoran Agbara Eto AgriSense",
        "safe_plant": "🟢 O DARA LATI GBIN",
        "mod_risk": "🟡 EWU DIE WA FUN GBIGBIN",
        "no_plant": "🔴 E MURA DA GBIGBIN DURO",
        "growth_stage": "Ipele Idagbasoke Egbin",
        "irrig_status": "Ipo Fun Omi BoriEgbin",
        "trend_header": "📊 Sise Akosile Ojo Osese Koidi fun",
        "sms_header": "📱 Daju Sise Ransan Ase Nikan",
        "sms_content": "Akokono Ase SMS:",
        "enter_phone": "Tẹ Nọmba Fonu Re:",
        "send_sms_btn": "🚀 Ransan Ase SMS Ni Yanyan"
    }
}

# Dynamic Irrigation Advisory Translations
IRRIGATION_TRANSLATIONS = {
    "STOP_IRRIGATION": {
        "action_yo": "🟢 DA OMI DURO",
        "advisory_yo": "Egbin ti gbo. Da omi duro lati gbe oko ki o to kore."
    },
    "WAIT_FOR_RAIN": {
        "action_yo": "🟡 DUMURA FUN OJO",
        "advisory_yo": "Erupe gbe, sugbon ojo nbo ni akoko wakati 72. Fi omi pamora."
    },
    "EMERGENCY_IRRIGATE": {
        "action_yo": "🚨 EWU: WUN OMI NIOUN!",
        "advisory_yo": "EWU NLA! Erupe gbe. Ti o ba pe lati wun omi, egbin le ba je!"
    },
    "IRRIGATE_NOW": {
        "action_yo": "🔵 WUN OMI NIOUN",
        "advisory_yo": "Nkan gbigbe ti po ju. Wun omi daradara fun oko re."
    },
    "MOISTURE_SAFE": {
        "action_yo": "🟢 OMI WA DARADARA",
        "advisory_yo": "Omi ti to fun ipele idagbasoke egbin re. Ko buido wun omi sii."
    }
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

# Fetch Live Weather from Open-Meteo REST API (Standard Clean URL)
@st.cache_data(ttl=3600, show_spinner=False)  # Cache results for 1 hour
def fetch_live_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=precipitation_sum,temperature_2m_max,temperature_2m_min&"
        f"past_days=7&forecast_days=3&timezone=Africa%2FLagos"
    )

    today = datetime.date.today()
    fallback_dates = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, -1, -1)]
    fallback_data = {
        "today_rain": 2.5,
        "temp_avg": 26.5,
        "past_7day_rain": 18.0,
        "forecast_3day_rain": 12.0,
        "consecutive_dry_days": 1,
        "dates": fallback_dates,
        "rain_history": [1.0, 0.0, 4.2, 0.0, 2.1, 8.2, 0.0, 2.5]
    }

    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            daily = data.get('daily', {})
            
            precip = daily.get('precipitation_sum', [])
            t_max_list = daily.get('temperature_2m_max', [])
            t_min_list = daily.get('temperature_2m_min', [])

            raw_precip = [0.0 if p is None else float(p) for p in precip]
            t_max = [28.0 if t is None else float(t) for t in t_max_list]
            t_min = [22.0 if t is None else float(t) for t in t_min_list]

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

            return {
                "today_rain": round(today_rain, 1),
                "temp_avg": round((temp_max + temp_min) / 2, 1),
                "past_7day_rain": round(past_7day_rain, 1),
                "forecast_3day_rain": round(forecast_3day_rain, 1),
                "consecutive_dry_days": dry_days,
                "dates": daily.get('time', [])[:today_index+1],
                "rain_history": raw_precip[:today_index+1]
            }
        
        st.warning(f"⚠️ Weather API Status {response.status_code}. Loading local climate fallback parameters...")
        return fallback_data

    except Exception as e:
        st.warning(f"⚠️ Weather connection error: {e}. Loading local climate fallback parameters...")
        return fallback_data

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

# SINGLE UI NAVIGATION TAB DECLARATION
tab1, tab2 = st.tabs(["📊 Single Farm Interactive Dashboard", "🚀 Multi-Farmer Batch SMS Dispatcher"])

# --- TAB 1: SINGLE FARM DASHBOARD ---
with tab1:
    # Global / Tab Language Switcher
    lang = st.radio("🌐 Choose Language / Yan Ede:", ["English", "Yoruba"], horizontal=True, key="dashboard_lang")
    txt = UI_TEXT[lang] # Load dictionary based on selected language

    if model is None:
        st.error(f"⚠️ Model file `agrisense_kwara_model_v2.pkl` not found in directory: `{BASE_DIR}`.")
    
    col_sel1, col_sel2, col_sel3 = st.columns(3)
    with col_sel1:
        selected_lga = st.selectbox(txt["lga_label"], list(LGA_COORDINATES.keys()), key="single_lga")
    with col_sel2:
        planting_date = st.date_input(txt["pdate_label"], datetime.date.today(), key="single_pdate")
    with col_sel3:
        soil_type = st.selectbox(txt["soil_label"], ["Loam/Clay", "Sandy"], key="single_soil")

    today_date = datetime.date.today()
    dap = max(0, (today_date - planting_date).days)
    day_of_year = today_date.timetuple().tm_yday

    coords = LGA_COORDINATES[selected_lga]
    live_data = fetch_live_weather(coords["lat"], coords["lon"])

    if live_data:
        st.markdown(f"#### {txt['live_metrics_header']} ({selected_lga})")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(txt["today_rain"], f"{live_data['today_rain']} mm")
        c2.metric(txt["past_rain"], f"{live_data['past_7day_rain']} mm")
        c3.metric(txt["forecast_rain"], f"{live_data['forecast_3day_rain']} mm")
        c4.metric(txt["dry_streak"], f"{live_data['consecutive_dry_days']} Days")
        c5.metric(txt["avg_temp"], f"{live_data['temp_avg']} °C")

        # Calculate Irrigation Advisory
        irrigation_res = calculate_irrigation_advisory(dap, live_data['consecutive_dry_days'], live_data['forecast_3day_rain'], soil_type)
        
        # Get Yoruba translations for the current irrigation status key
        status_key = irrigation_res.get("status", "MOISTURE_SAFE")
        yo_irrig = IRRIGATION_TRANSLATIONS.get(status_key, IRRIGATION_TRANSLATIONS["MOISTURE_SAFE"])

        # Set localized advisory texts
        action_text = yo_irrig["action_yo"] if lang == "Yoruba" else irrigation_res["action"]
        advisory_text = yo_irrig["advisory_yo"] if lang == "Yoruba" else irrigation_res["advisory"]

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
            st.markdown(f"### {txt['model_header']}")

            if prob_safe >= 80:
                st.success(f"{txt['safe_plant']} ({prob_safe:.1f}% Confidence)")
                planting_advisory = "O DARA LATI GBIN" if lang == "Yoruba" else "SAFE TO PLANT: Optimal moisture & 3-day forecast conditions predicted."
            elif 50 <= prob_safe < 80:
                st.warning(f"{txt['mod_risk']} ({prob_safe:.1f}% Confidence)")
                planting_advisory = "EWU DIE WA" if lang == "Yoruba" else "MODERATE RISK: Ensure light pre-irrigation if dry conditions persist."
            else:
                st.error(f"{txt['no_plant']} ({prob_safe:.1f}% Confidence)")
                planting_advisory = "E MURA DA GBIGBIN DURO" if lang == "Yoruba" else "DO NOT PLANT: High drought/off-season risk detected."

        st.info(f"**{txt['growth_stage']}:** {irrigation_res['stage']} | **{txt['irrig_status']}:** {action_text}\n\n{advisory_text}")

        st.markdown("---")

        # Charting Trend
        st.write(f"### {txt['trend_header']} {selected_lga}")
        df_trend = pd.DataFrame({
            "Date": live_data["dates"],
            "Rainfall (mm)": live_data["rain_history"]
        })
        df_trend["Rainfall (mm)"] = df_trend["Rainfall (mm)"].fillna(0.0)
        st.bar_chart(df_trend.set_index("Date"))

        st.markdown("---")
        st.markdown(f"### {txt['sms_header']}")

        # Localized dynamic SMS message body
        if lang == "Yoruba":
            default_single_msg = (
                f"AgriSense({selected_lga}): Imoran Gbigbin: {planting_advisory} ({prob_safe:.0f}%). "
                f"Omi: {action_text}. {advisory_text}"
            )[:160]
        else:
            default_single_msg = (
                f"AgriSense({selected_lga}): {planting_advisory} "
                f"Irrigation: {action_text}. {advisory_text}"
            )[:160]
        
        single_msg = st.text_area(txt["sms_content"], default_single_msg, height=100)
        
        msg_len = len(single_msg)
        segments = (msg_len // 160) + 1
        if msg_len <= 160:
            st.caption(f"📏 **Length:** {msg_len}/160 chars (1 SMS segment)")
        else:
            st.warning(f"⚠️ **Length:** {msg_len} chars ({segments} SMS segments). Keep under 160 characters to optimize pilot dispatch costs.")

        test_phone = st.text_input(txt["enter_phone"], "08143086509")
        if st.button(txt["send_sms_btn"]):
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
    st.info("💡 **Language Support:** Add a `Language` column (`Yoruba` or `English`) in your file to send localized SMS to each farmer.")
    
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

                with st.spinner("Processing climate data & preparing bulk dispatch..."):
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
                        planting_status_en = "SAFE TO PLANT" if prob_safe >= 80 else "DO NOT PLANT"
                        planting_status_yo = "O DARA LATI GBIN" if prob_safe >= 80 else "E MURA DA GBIGBIN DURO"

                        gsm_recipients = []
                        lga_farmer_records = []

                        for idx, row in group.iterrows():
                            farmer_name = str(row.get('Name', 'Farmer')).strip()
                            raw_phone = str(row.get('Phone', '')).strip()
                            soil = str(row.get('Soil_Type', 'Loam/Clay')).strip()
                            farmer_lang = str(row.get('Language', 'Yoruba')).strip().title()

                            formatted_phone = format_nigerian_phone(raw_phone)

                            try:
                                p_date = pd.to_datetime(row['Planting_Date']).date()
                                dap = max(0, (today_date - p_date).days)
                            except Exception:
                                dap = 0

                            irrigation = calculate_irrigation_advisory(dap, weather['consecutive_dry_days'], weather['forecast_3day_rain'], soil)
                            status_key = irrigation.get("status", "MOISTURE_SAFE")
                            yo_irrig = IRRIGATION_TRANSLATIONS.get(status_key, IRRIGATION_TRANSLATIONS["MOISTURE_SAFE"])

                            # Dynamically pick SMS text based on farmer's preferred language
                            if farmer_lang == "Yoruba":
                                personalized_msg = (
                                    f"AgriSense({clean_lga}): Bawo {farmer_name}, "
                                    f"Gbigbin: {planting_status_yo} ({prob_safe:.0f}%). "
                                    f"Omi: {yo_irrig['action_yo']}."
                                )[:160]
                            else:
                                personalized_msg = (
                                    f"AgriSense({clean_lga}): Hi {farmer_name}, "
                                    f"Plant: {planting_status_en} ({prob_safe:.0f}%). "
                                    f"Irrigate: {irrigation['action']}."
                                )[:160]

                            unique_msgid = f"batch_{clean_lga}_{dap}_{idx}"

                            gsm_recipients.append({
                                "msidn": formatted_phone,
                                "msgid": unique_msgid
                            })

                            lga_farmer_records.append({
                                "Farmer Name": farmer_name,
                                "Phone": formatted_phone,
                                "LGA": clean_lga,
                                "Language": farmer_lang,
                                "Crop Age (DAP)": dap,
                                "Planting Advisory": planting_status_yo if farmer_lang == "Yoruba" else planting_status_en,
                                "SMS Length": len(personalized_msg),
                                "Message Body": personalized_msg
                            })

                        # Execute 1 Single Bulk API Call per LGA Group
                        if gsm_recipients:
                            sample_msg = lga_farmer_records[0]["Message Body"]
                            
                            bulk_payload = {
                                "SMS": {
                                    "auth": {"username": EBULKSMS_USERNAME, "apikey": EBULKSMS_API_KEY},
                                    "message": {"sender": "AgriSense", "messagetext": sample_msg, "flash": "0", "dndsender": "1"},
                                    "recipients": {"gsm": gsm_recipients}
                                }
                            }

                            try:
                                res = requests.post("https://api.ebulksms.com/sendsms.json", json=bulk_payload, headers={'Content-Type': 'application/json'}, timeout=10)
                                res_json = res.json()
                                api_status = res_json.get("response", {}).get("status", "SUCCESS")
                            except Exception as err:
                                api_status = f"ERROR: {err}"

                            for record in lga_farmer_records:
                                record["Dispatch Status"] = api_status
                                dispatch_logs.append(record)

                st.success("🎉 Batch Broadcast Execution Completed!")
                st.markdown("### 📊 Live Dispatch Execution Report")
                st.dataframe(pd.DataFrame(dispatch_logs))
