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
st.subheader("Real Time Climate & Maize Planting Advisory System")
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
        "irrig_status": "Ipo Fun Omi Bori Egbin",
        "trend_header": "📊 Sise Akosile Ojo Osese Koidi fun",
        "sms_header": "📱 Daju Sise Ransan Ase Nikan",
        "sms_content": "Akokono Ase SMS:",
        "enter_phone": "Tẹ Nọmba Fonu Re:",
        "send_sms_btn": "🚀 Ransan Ase SMS Ni Yanyan"
    }
}

# Dynamic Irrigation & Fertilizer Advisory Translations
ADVISORY_TRANSLATIONS = {
    "STOP_IRRIGATION": {
        "action_yo": "🟢 DA OMI DURO",
        "advisory_yo": "Egbin ti gbo. Da omi duro lati gbe oko ki o to kore.",
        "fert_yo": "Ko si fe fun takete ni ipele yi (Egbin ti gbo)."
    },
    "WAIT_FOR_RAIN": {
        "action_yo": "🟡 DI MURA FUN OJO",
        "advisory_yo": "Erupe gbe, sugbon ojo nbo ni akoko wakati méjíléláàdọ́rin. Fi omi pamora.",
        "fert_yo": "⚠️ DI MURA FUN TAKETE: Ojo nla nbo ni wakati méjíléláàdọ́rin. Takete re le ba je lo ti o ba fi si loni!"
    },
    "EMERGENCY_IRRIGATE": {
        "action_yo": "🚨 EWU: WON OMI KIAKIA!",
        "advisory_yo": "EWU NLA! Erupe gbe. Ti o ba pe lati won omi, egbin le ba je!",
        "fert_yo": "⚠️ ERUPE GBE JU: Won omi si oko ki o to fi takete/Urea si lati ma ba egbin je."
    },
    "IRRIGATE_NOW": {
        "action_yo": "🔵 WON OMI NISIN",
        "advisory_yo": "Nkan gbigbe ti po ju. Won omi daadaa fun oko re.",
        "fert_yo": "Erupe gbe die. Won omi die ki o to fi takete si."
    },
    "MOISTURE_SAFE": {
        "action_yo": "🟢 OMI WA DAADAA",
        "advisory_yo": "Omi ti to fun ipele idagbasoke egbin re. Ko gbudo won omi sii.",
        "fert_yo": "🟢 AKEJU OMI DA: Aaye wa lati fi takete si egbe egbin re ti o ba koo si asiko."
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

# Helper: Monthly Subscription Expiry Checker (Supports Excel Timestamps)
def is_subscription_active(expiry_date_str):
    try:
        # Extract just the YYYY-MM-DD part if a full timestamp is passed
        clean_date_str = str(expiry_date_str).strip().split(" ")[0]
        expiry_date = datetime.datetime.strptime(clean_date_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        return today <= expiry_date
    except Exception:
        return False
        
# Helper: Growing Degree Days (GDD)
def calculate_gdd(temp):
    base_temp, cap_temp = 10.0, 30.0
    effective_temp = min(max(temp, base_temp), cap_temp)
    return max(0, effective_temp - base_temp)

# Helper: Convert Water Depth (mm), Farm Size & Units to Generator Pumping Hours
def calculate_pump_hours(water_depth_mm, land_size=1.0, unit="Hectares"):
    if water_depth_mm <= 0 or land_size <= 0:
        return 0.0
    
    # Convert Acres to Hectares if needed
    land_size_ha = land_size * 0.404686 if str(unit).lower() == "acres" else land_size
    
    total_liters = water_depth_mm * 10000 * land_size_ha
    pump_capacity_lh = 25000  # Standard 2-inch petrol pump (~25,000 L/hr)
    return round(total_liters / pump_capacity_lh, 1)

# Helper: Verify Paystack Transaction Reference via Paystack REST API
def verify_paystack_transaction(reference_code):
    paystack_secret = st.secrets.get("PAYSTACK_SECRET_KEY", "")
    if not paystack_secret or not reference_code:
        return False, None
        
    headers = {"Authorization": f"Bearer {paystack_secret}"}
    url = f"https://api.paystack.co/transaction/verify/{reference_code}"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json().get("data", {})
            if data.get("status") == "success":
                customer_phone = data.get("metadata", {}).get("phone") or data.get("customer", {}).get("phone")
                return True, customer_phone
    except Exception as e:
        st.error(f"Payment verification error: {e}")
    return False, None

# Upgraded Combined Irrigation & Fertilizer Advisory Engine
def calculate_crop_advisory(dap, consecutive_dry_days, forecast_3day_rain, soil_type="Loam/Clay", land_size=1.0, land_unit="Hectares"):
    dry_limit_factor = 0.6 if str(soil_type).lower() == "sandy" else 1.0

    # 1. Determine Crop Stage & Daily Water Needs FIRST
    if 0 <= dap <= 15:
        stage, max_dry, daily_need = "Establishment / Early Growth (Days 0-15)", max(1, int(2 * dry_limit_factor)), 1.2
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
            "advisory": "Crop mature. Stop watering for field drying before harvest.",
            "fert_en": "No fertilizer application required at maturation phase.",
            "fert_yo": "Ko si fe fun takete ni ipele yi (Egbin ti gbo)."
        }

    # 2. Calculate Derived Values safely after max_dry & daily_need are set
    needed_mm = daily_need * 3
    hrs = calculate_pump_hours(needed_mm, land_size=land_size, unit=land_unit)
    today = datetime.date.today()
    next_watering_date = today + datetime.timedelta(days=max_dry)
    formatted_next_date = next_watering_date.strftime("%b %d, %Y")

    # 3. Evaluate Moisture & Irrigation Status
    if consecutive_dry_days >= max_dry:
        if forecast_3day_rain >= 15.0:
            status = "WAIT_FOR_RAIN"
            action = "🟡 HOLD OFF IRRIGATING"
            advisory = f"Soil dry ({consecutive_dry_days}d), but ~{forecast_3day_rain:.1f}mm rain in 72h. Save fuel & water."
        else:
            if "Flowering" in stage:
                status = "EMERGENCY_IRRIGATE"
                action = f"🚨 CRITICAL: IRRIGATE NOW (~{hrs} hrs pump)"
                advisory = f"CRITICAL! {consecutive_dry_days} dry days in Flowering stage. Apply ~{needed_mm:.1f}mm (~{hrs} hrs 2-inch pump) to prevent pollination failure!\n\n📅 **Next Irrigation Date:** {formatted_next_date} (if dry spell continues)."
            else:
                status = "IRRIGATE_NOW"
                action = f"🔵 IRRIGATE NOW (~{hrs} hrs pump)"
                advisory = f"Dry limit reached. Apply ~{needed_mm:.1f}mm water (run 2-inch pump for ~{hrs} hours).\n\n📅 **Next Irrigation Date:** {formatted_next_date} (if dry spell continues)."
    else:
        status = "MOISTURE_SAFE"
        action = "🟢 MOISTURE OPTIMAL"
        advisory = f"Moisture adequate for {stage}. No extra watering needed."

    # 4. Evaluate Fertilizer Timings & Yoruba Translations
    if 7 <= dap <= 14:
        if forecast_3day_rain >= 15.0:
            fert_en = "⚠️ HOLD OFF NPK: Heavy rain forecast. Fertilizer will wash away!"
            fert_yo = "⚠️ DURO FUN NPK: Ojo nla nbo. Takete re le ba je lo ti o ba fi si loni!"
        else:
            fert_en = "🧪 BASAL FERTILIZER WINDOW: Apply NPK 15-15-15 (1 bag/ha) near root zone."
            fert_yo = "🧪 AKOKO TAKETE NPK: Won NPK 15-15-15 si egbe egbin re ni eba ogbo."
    elif 21 <= dap <= 30:
        if forecast_3day_rain >= 15.0:
            fert_en = "⚠️ HOLD OFF UREA: Heavy rain in 72h forecast. Fertilizer will wash away!"
            fert_yo = "⚠️ DURO FUN UREA: Ojo nbo ni wakati méjíléláàdọ́rin. Fi takete Urea pamo bayii."
        elif consecutive_dry_days >= 4:
            fert_en = "⚠️ DRY SOIL: Pre-irrigate field before applying Urea to prevent root burn."
            fert_yo = "⚠️ ERUPE GBE: Won omi si oko ki o to fi Urea si lati ma ba egbin je."
        else:
            fert_en = "🧪 1ST TOP-DRESSING WINDOW: Apply Urea for fast vegetative growth."
            fert_yo = "🧪 AKOKO UREA AKOKO: Won takete Urea fun idagbasoke egbin re."
    elif 45 <= dap <= 55:
        if forecast_3day_rain >= 15.0:
            fert_en = "⚠️ HOLD OFF 2ND UREA: Rain expected in 72h. Hold off application."
            fert_yo = "⚠️ DURO FUN UREA ELEKEJI: Ojo nbo ni wakati méjíléláàdọ́rin. Mura da duro."
        else:
            fert_en = "🧪 2ND TOP-DRESSING WINDOW: Apply Urea before flowering stage."
            fert_yo = "🧪 AKOKO UREA ELEKEJI: Won Urea keji ki egbin to bere si ru ewe/ododo."
    else:
        fert_en = "🟢 No scheduled fertilizer application for this exact growth day."
        fert_yo = "🟢 Ko si takete ti a sun si sile fun ojo idagbasoke egbin yi."

    return {
        "stage": stage,
        "status": status,
        "action": action,
        "advisory": advisory,
        "fert_en": fert_en,
        "fert_yo": fert_yo,
        "pump_hrs": hrs,
        "next_date": formatted_next_date
    }

# Fetch Live Weather from Open-Meteo REST API
@st.cache_data(ttl=3600, show_spinner=False)
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
    lang = st.radio("🌐 Choose Language / Yan Ede:", ["English", "Yoruba"], horizontal=True, key="dashboard_lang")
    txt = UI_TEXT[lang]

    if model is None:
        st.error(f"⚠️ Model file `agrisense_kwara_model_v2.pkl` not found in directory: `{BASE_DIR}`.")

    st.markdown("---")
    
    # 🔑 FARMER ACCOUNT PORTAL (WITH SESSION STATE PERSISTENCE)
    st.markdown("### 🔑 Farmer Account Portal / Ipade Wo Tesiwaju")

    # Initialize Session State Variables
    if "is_paid_user" not in st.session_state:
        st.session_state.is_paid_user = False
    if "user_phone" not in st.session_state:
        st.session_state.user_phone = ""

    # Check for Paystack URL Redirect Reference
    query_params = st.query_params
    if "reference" in query_params:
        pay_ref = query_params["reference"]
        is_valid_pay, paid_phone = verify_paystack_transaction(pay_ref)
        if is_valid_pay:
            st.balloons()
            st.success("🎉 Payment Verified! Welcome to AgriSense Premium.")
            st.session_state.is_paid_user = True
            if paid_phone:
                st.session_state.user_phone = str(paid_phone)
            st.query_params.clear()

    # Input Box for Farmer Login
    user_input_phone = st.text_input(
        "Enter Phone Number / Tẹ Nọmba Fonu Re:", 
        value=st.session_state.user_phone, 
        placeholder="e.g. 08012345678", 
        key="user_login_phone"
    )
    
    formatted_login = format_nigerian_phone(user_input_phone)
    ALLOWED_ADMIN_NUMBERS = ["08143086509", "2348143086509"]

    # Access Gate Verification Checks
    if formatted_login in ALLOWED_ADMIN_NUMBERS or formatted_login[-10:] in [p[-10:] for p in ALLOWED_ADMIN_NUMBERS]:
        st.session_state.is_paid_user = True
    elif user_input_phone != "" and 'df_farmers' in locals() and df_farmers is not None and not df_farmers.empty:
        matched_user = df_farmers[df_farmers['Phone'].astype(str).str.contains(formatted_login[-10:])]
        if not matched_user.empty:
            p_status = str(matched_user.iloc[0].get('Payment_Status', 'UNPAID')).strip().upper()
            user_expiry = str(matched_user.iloc[0].get('Subscription_Expiry', '2026-10-02')).strip()
            date_is_valid = is_subscription_active(user_expiry)
            if (p_status == "PAID") and date_is_valid:
                st.session_state.is_paid_user = True

    is_paid_user = st.session_state.is_paid_user

    if is_paid_user:
        st.success("🟢 Account Status: Active Subscriber / Akaunti Re Wa Ni Alafia")
    else:
        st.warning("🔴 Account Status: Expired or Unpaid / Akaunti Re Ti Fe San Owo")
        st.info("💡 Pay seasonal/monthly subscription to unlock ML planting forecasts & irrigation alerts.")
    st.markdown("---")

    col_sel1, col_sel2, col_sel3, col_sel4, col_sel5 = st.columns([2, 2, 2, 2, 2])
    with col_sel1:
        selected_lga = st.selectbox(txt["lga_label"], list(LGA_COORDINATES.keys()), key="single_lga")
    with col_sel2:
        planting_date = st.date_input(txt["pdate_label"], datetime.date.today(), key="single_pdate")
    with col_sel3:
        soil_type = st.selectbox(txt["soil_label"], ["Loam/Clay", "Sandy"], key="single_soil")
    with col_sel4:
        land_size = st.number_input("Farm Size:", min_value=0.1, max_value=None, value=1.0, step=0.5, key="single_land")
    with col_sel5:
        land_unit = st.selectbox("Unit:", ["Acres", "Hectares"], key="single_unit")

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

        crop_res = calculate_crop_advisory(
            dap, 
            live_data['consecutive_dry_days'], 
            live_data['forecast_3day_rain'], 
            soil_type, 
            land_size=land_size, 
            land_unit=land_unit
        )
        status_key = crop_res.get("status", "MOISTURE_SAFE")
        yo_irrig = ADVISORY_TRANSLATIONS.get(status_key, ADVISORY_TRANSLATIONS["MOISTURE_SAFE"])

        action_text = yo_irrig["action_yo"] if lang == "Yoruba" else crop_res["action"]
        advisory_text = yo_irrig["advisory_yo"] if lang == "Yoruba" else crop_res["advisory"]
        fert_text = crop_res["fert_yo"] if lang == "Yoruba" else crop_res["fert_en"]

        planting_advisory = "N/A"
        prob_safe = 50.0
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
            if prob_safe >= 80:
                planting_advisory = "O DARA LATI GBIN" if lang == "Yoruba" else "SAFE TO PLANT"
            elif 50 <= prob_safe < 80:
                planting_advisory = "EWU DIE WA" if lang == "Yoruba" else "MODERATE RISK"
            else:
                planting_advisory = "E MURA DA GBIGBIN DURO" if lang == "Yoruba" else "DO NOT PLANT"

        st.markdown("---")

        if is_paid_user:
            st.markdown("### 🎯 Select Advisory Focus / Yan Imoran Ti O Fẹ")
            
            advisory_choice = st.radio(
                "Choose Advisory View / Yan Akeju Re:",
                ["🌾 Planting Decision", "💧 Irrigation & Water Plan", "🧪 Fertilizer & Input Protection"],
                horizontal=True,
                key="advisory_module_choice"
            )

            st.markdown("---")

            if advisory_choice == "🌾 Planting Decision":
                st.markdown(f"### {txt['model_header']}")
                if prob_safe >= 80:
                    st.success(f"{txt['safe_plant']} ({prob_safe:.1f}% Confidence)")
                elif 50 <= prob_safe < 80:
                    st.warning(f"{txt['mod_risk']} ({prob_safe:.1f}% Confidence)")
                else:
                    st.error(f"{txt['no_plant']} ({prob_safe:.1f}% Confidence)")
                
                st.info(f"**{txt['growth_stage']}:** {crop_res['stage']}")

            elif advisory_choice == "💧 Irrigation & Water Plan":
                st.markdown("### 💧 Dry-Season & Irrigation Advisory")
                st.info(f"**{txt['growth_stage']}:** {crop_res['stage']} | **{txt['irrig_status']}:** {action_text}\n\n{advisory_text}")
                st.caption(f"💡 *Dry Season Tip: Pumping required for {land_size} {land_unit} field = ~{crop_res['pump_hrs']} hrs of 2-inch petrol pump.*")

            elif advisory_choice == "🧪 Fertilizer & Input Protection":
                st.markdown("### 🧪 Fertilizer Timing & Crop Protection")
                st.info(f"**{txt['growth_stage']}:** {crop_res['stage']}\n\n**Advisory / Imoran:** {fert_text}")
                st.caption("💡 *Input Safety Tip: Applying fertilizer before heavy downpours washes nutrients away and wastes money.*")

        else:
            st.warning("🔒 **PREMIUM ADVISORIES LOCKED / IMORAN AKANSE TITI**")
            st.markdown(
                """
                > **Upgrade to AgriSense Premium (₦1,000 / Month):**
                > * 🌾 Unlock Machine Learning Planting Decision Scores.
                > * 💧 Get Exact Daily Pumping/Watering Schedules (Saves fuel in Dry Season).
                > * 🧪 Prevent Fertilizer Leaching & Seed Loss.
                """
            )
            
            pay_col1, pay_col2 = st.columns(2)
            with pay_col1:
                st.markdown("#### 💳 Option 1: Pay Online")
                st.link_button(
                    "Pay ₦1,000 via Paystack", 
                    "https://paystack.shop/pay/cl6o6aipdr",
                    use_container_width=True
                )
            
            with pay_col2:
                st.markdown("#### 💵 Option 2: Pay Field Coordinator")
                st.info(
                    "Pay cash directly to your local **AgriSense Coordinator / Cooperative Leader** in your LGA.\n\n"
                    "📞 **Support / Activation Hotlines:** `08143086509`"
                )

        st.markdown("---")

        st.write(f"### {txt['trend_header']} {selected_lga}")
        df_trend = pd.DataFrame({
            "Date": live_data["dates"],
            "Rainfall (mm)": live_data["rain_history"]
        })
        df_trend["Rainfall (mm)"] = df_trend["Rainfall (mm)"].fillna(0.0)
        st.bar_chart(df_trend.set_index("Date"))

        st.markdown("---")

        st.markdown(f"### {txt['sms_header']}")

        if lang == "Yoruba":
            default_single_msg = (
                f"AgriSense({selected_lga}): Gbigbin: {planting_advisory} ({prob_safe:.0f}%). "
                f"Omi: {action_text}. Takete: {fert_text[:40]}..."
            )[:160]
        else:
            default_single_msg = (
                f"AgriSense({selected_lga}): Plant: {planting_advisory} ({prob_safe:.0f}%). "
                f"Irrig: {action_text}. Fert: {crop_res['fert_en'][:40]}..."
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

# --- TAB 2: MULTI-FARMER BATCH SMS DISPATCHER (ADMIN & AGENT ONLY) ---
with tab2:
    st.markdown("### 🔒 Authorized Personnel Area (Admin / Field Officer)")
    
    ADMIN_PIN = st.secrets.get("ADMIN_PIN", "2026")
    admin_input = st.text_input("🔑 Enter Admin / Agent Passcode:", type="password", key="admin_gate_pin")

    if admin_input == ADMIN_PIN:
        st.success("🔓 Access Granted: Welcome Admin / Field Officer")
        st.markdown("---")
        
        st.markdown("### 📋 Upload Recipient Roster (50 Farmers Target)")
        st.info(
            "💡 **Batch Roster Columns Required:** `Name`, `Phone`, `LGA`, `Planting_Date`, `Soil_Type`.\n\n"
            "Optional Columns: `Language` (`Yoruba`/`English`), `Payment_Status` (`PAID`/`UNPAID`), `Subscription_Expiry` (`YYYY-MM-DD`), `Land_Size` (default: 1.0), `Land_Unit` (`Acres`/`Hectares`)."
        )
        
        uploaded_file = st.file_uploader("Upload Farmers File (.xlsx or .csv)", type=["xlsx", "csv"], key="admin_file_uploader")

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

                    with st.spinner("Processing climate data & preparing personalized bulk dispatches..."):
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

                            for idx, row in group.iterrows():
                                farmer_name = str(row.get('Name', 'Farmer')).strip()
                                raw_phone = str(row.get('Phone', '')).strip()
                                soil = str(row.get('Soil_Type', 'Loam/Clay')).strip()
                                farmer_lang = str(row.get('Language', 'Yoruba')).strip().title()
                                p_status = str(row.get('Payment_Status', 'PAID')).strip().upper()
                                user_expiry = str(row.get('Subscription_Expiry', '2026-10-02')).strip()
                                farmer_land = float(row.get('Land_Size', 1.0))
                                farmer_unit = str(row.get('Land_Unit', 'Hectares')).strip().title()

                                formatted_phone = format_nigerian_phone(raw_phone)

                                try:
                                    p_date = pd.to_datetime(row['Planting_Date']).date()
                                    dap = max(0, (today_date - p_date).days)
                                except Exception:
                                    dap = 0

                                crop_res = calculate_crop_advisory(
                                    dap, 
                                    weather['consecutive_dry_days'], 
                                    weather['forecast_3day_rain'], 
                                    soil, 
                                    land_size=farmer_land,
                                    land_unit=farmer_unit
                                )
                                status_key = crop_res.get("status", "MOISTURE_SAFE")
                                yo_irrig = ADVISORY_TRANSLATIONS.get(status_key, ADVISORY_TRANSLATIONS["MOISTURE_SAFE"])

                                active_account = (p_status == "PAID") and is_subscription_active(user_expiry)

                                if active_account:
                                    if farmer_lang == "Yoruba":
                                        personalized_msg = (
                                            f"AgriSense({clean_lga}): Bawo {farmer_name}, "
                                            f"Gbigbin: {planting_status_yo} ({prob_safe:.0f}%). "
                                            f"Omi: {yo_irrig['action_yo']}. Takete: {crop_res['fert_yo'][:30]}..."
                                        )[:160]
                                    else:
                                        personalized_msg = (
                                            f"AgriSense({clean_lga}): Hi {farmer_name}, "
                                            f"Plant: {planting_status_en} ({prob_safe:.0f}%). "
                                            f"Irrig: {crop_res['action']}. Fert: {crop_res['fert_en'][:30]}..."
                                        )[:160]
                                else:
                                    if farmer_lang == "Yoruba":
                                        personalized_msg = (
                                            f"AgriSense: Bawo {farmer_name}, akaunti re ti fe san owo. "
                                            f"San N1000 lati tesiwaju gbigba imoran oko re."
                                        )[:160]
                                    else:
                                        personalized_msg = (
                                            f"AgriSense: Hi {farmer_name}, your subscription has expired. "
                                            f"Pay N1000 to continue receiving seasonal advisories."
                                        )[:160]

                                unique_msgid = f"batch_{clean_lga}_{dap}_{idx}_{int(datetime.datetime.now().timestamp())}"

                                single_payload = {
                                    "SMS": {
                                        "auth": {"username": EBULKSMS_USERNAME, "apikey": EBULKSMS_API_KEY},
                                        "message": {"sender": "AgriSense", "messagetext": personalized_msg, "flash": "0", "dndsender": "1"},
                                        "recipients": {"gsm": [{"msidn": formatted_phone, "msgid": unique_msgid}]}
                                    }
                                }

                                try:
                                    res = requests.post("https://api.ebulksms.com/sendsms.json", json=single_payload, headers={'Content-Type': 'application/json'}, timeout=10)
                                    res_json = res.json()
                                    api_status = res_json.get("response", {}).get("status", "SUCCESS")
                                except Exception as err:
                                    api_status = f"ERROR: {err}"

                                dispatch_logs.append({
                                    "Farmer Name": farmer_name,
                                    "Phone": formatted_phone,
                                    "LGA": clean_lga,
                                    "Language": farmer_lang,
                                    "Payment Status": p_status,
                                    "Subscription Expiry": user_expiry,
                                    "Land Size": f"{farmer_land} {farmer_unit}",
                                    "Account Status": "ACTIVE" if active_account else "EXPIRED",
                                    "Crop Age (DAP)": dap,
                                    "Message Body": personalized_msg,
                                    "Dispatch Status": api_status
                                })

                    st.success("🎉 Batch Broadcast Execution Completed!")
                    st.markdown("### 📊 Live Dispatch Execution Report")
                    st.dataframe(pd.DataFrame(dispatch_logs))

    elif admin_input != "":
        st.error("🔴 Invalid Admin Passcode. Access restricted to authorized AgriSense field agents.")
    else:
        st.info("👆 Please enter your authorized Admin PIN above to unlock the Multi-Farmer Batch Dispatcher.")
