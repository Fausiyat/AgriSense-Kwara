# 🌾 AgriSense Kwara: Real-Time Climate Monitoring & Maize Advisory Engine

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Termii](https://img.shields.io/badge/Termii_API-00C853?style=for-the-badge)](https://termii.com/)

**AgriSense Kwara** is a climate-smart decision engine designed to help smallholder farmers and agricultural cooperatives in Kwara State, Nigeria, optimize maize planting windows and mitigate drought risk. 

By combining **agronomy fundamentals**, **satellite climate data**, and **rural-first communication protocols (SMS)**, AgriSense bridge the gap between high-tech machine learning models and farmers operating in low-bandwidth, off-grid environments.

---

## 📌 The Problem & Context

In Kwara State—a pivotal agricultural hub in Nigeria—unpredictable rainfall patterns and mid-season dry spells lead to early planting failures. Up to **40% of maize seeds planted in rural Nigeria fail to germinate** due to premature planting triggered by brief, false early rains.

While modern web dashboards exist, **over 70% of Nigeria’s farming population resides in rural areas** with limited access to smartphones or mobile internet.

---

## 💡 The AgriSense Solution

AgriSense uses a dual-layer approach:
1. **B2B Web Portal (Streamlit):** Designed for farm extension officers, seed companies, and grain aggregators to monitor live, localized climate risks across Kwara LGAs (Ilorin West, Kaiama, Asa, Ifelodun, etc.).
2. **Rural SMS Pipeline (Termii API):** Translates real-time climate predictions into simple, actionable SMS advisories delivered directly to feature phones in local dialects—requiring **zero app downloads or internet access** for the farmer.

---

## ✨ Key Features

* **Real-Time Climate Ingestion:** Fetches daily precipitation, temperature ranges, and 7-day rolling rainfall totals via Open-Meteo & GEE climate endpoints.
* **Automated Planting Decision Engine:**
  * 🟢 **SAFE TO PLANT:** Sufficient 7-day moisture threshold ($\ge 30\text{mm}$) and low dry-spell streak.
  * 🟡 **CAUTION / HOLD:** Moderate moisture; flags a 24–48 hr observation window.
  * 🔴 **DO NOT PLANT:** High drought/heat risk; alerts farmers to delay sowing and fertilizer application.
* **One-Click SMS Broadcast:** Integrated with Termii’s messaging gateway to broadcast localized alerts instantly to registered farmer numbers.
* **Dynamic Interactive Dashboard:** Interactive metrics and historical rainfall charts broken down by Local Government Areas (LGAs).

---

## 🛠️ Tech Stack & Data Sources

* **Frontend & Dashboard:** Streamlit
* **Programming Language:** Python 3.12
* **Data Processing & Analytics:** Pandas, NumPy
* **Live Climate API:** Open-Meteo Forecast API & CHIRPS/ERA5 Satellite Reanalysis
* **Messaging & Communication Gateway:** Termii REST API (v4)
* **ML Model Framework (In-Development):** Scikit-Learn (`RandomForestClassifier`)

---

## 🚀 Getting Started Locally

### 1. Clone the Repository
```bash
git clone [https://github.com/Fausiyat/agrisense-kwara.git](https://github.com/Fausiyat/agrisense-kwara.git)
cd agrisense-kwara

### 2. Install Dependencies
pip install -r requirements.txt

### 3. Set Up API Credentials
Create a .streamlit/secrets.toml file in the root directory:
TERMII_API_KEY = "your_termii_live_key_here"

### 4. Run the Streamlit Dashboard
streamlit run app.py

📁 Repository Structure
├── app.py                         # Main Streamlit web application & decision engine
├── kwara_maize_climate_data.csv   # Processed historical climate baseline dataset
├── agrisense_kwara_model.pkl      # Pre-trained ML model weight file
├── requirements.txt               # Dependencies for deployment
└── README.md                      # Project documentation

git clone [https://github.com/Fausiyat/agrisense-kwara.git](https://github.com/Fausiyat/agrisense-kwara.git)
cd agrisense-kwara

Social Impact & Next Steps
Field Pilots: Partnering with agricultural extension agents across Kwara State to register smallholder cooperatives.

Multi-Language Support: Translating automated SMS advisories into Yoruba and Hausa dialects.

Pest Early-Warning Integration: Extending the ML engine to forecast Fall Armyworm outbreak risks based on heat/humidity indices.

👤 Author
Fausiyat Mahmood

Agricultural Background | Data Science & Machine Learning Practitioner
