from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ee
import sys
import os
import json
from fpdf import FPDF
from fastapi.responses import FileResponse

# Ensure engine module is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from engine.main import extract_incident_polygons, generate_evidence_images, get_mining_indices


# Initialize FastAPI
app = FastAPI(title="Illegal Mining Detector API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all websites (including your Flutter web app)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Earth Engine when server starts
@app.on_event("startup")
def startup_event():
    try:
        ee.Initialize(project="illegal-mining-detector-493805")
        print("✅ Connection to Google Earth Engine established.")
    except Exception as e:
        print("❌ Earth Engine initialization failed:", e)


# Request schema
class AnalysisRequest(BaseModel):
    lat: float
    lon: float
    radius: int = 2000


# Root endpoint
@app.get("/")
def home():
    return {
        "status": "Satellite System Online",
        "service": "Illegal Mining Detection API"
    }

def create_pdf_report(incident_id, lat, lon, area):
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="OFFICIAL INCIDENT REPORT", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt="Satellite-Based Illegal Mining Detection System", ln=True, align='C')
    pdf.ln(10)
    
    # Data Table
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Incident ID:", border=1)
    pdf.set_font("Arial", '', 12)
    pdf.cell(140, 10, str(incident_id), border=1, ln=True)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Coordinates:", border=1)
    pdf.set_font("Arial", '', 12)
    pdf.cell(140, 10, f"{lat}, {lon}", border=1, ln=True)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(50, 10, "Area (Hectares):", border=1)
    pdf.set_font("Arial", '', 12)
    pdf.cell(140, 10, f"{area}", border=1, ln=True)

    # Ensure directory exists
    os.makedirs("data/reports", exist_ok=True)
    file_path = f"data/reports/{incident_id}.pdf"
    pdf.output(file_path)
    return file_path

@app.get("/detect")

def detect(lat: float, lon: float):

    before_url, after_url = generate_evidence_images(...)

    return {
        "status": "success",
        "before_image": before_url,
        "after_image": after_url,
        "message": "Scan complete"
    }

# Mining detection endpoint
@app.post("/analyze")
async def analyze_area(request: AnalysisRequest):

    try:
        # Step 1: Detect incidents
        incidents = extract_incident_polygons(
            request.lat,
            request.lon,
            request.radius
        )

        count = incidents.size().getInfo()

        if count == 0:
            return {
                "alert": False,
                "message": "No mining activity detected in this area."
            }

        # Step 2: Extract largest incident
        top_incident = incidents.first()

        area_sqm = top_incident.get("area_sqm").getInfo()

        centroid = (
            top_incident
            .geometry()
            .centroid(maxError=1)
            .coordinates()
            .getInfo()
        )

        lat_detected = centroid[1]
        lon_detected = centroid[0]

        # Step 3: Prepare visualization region
        region = (
            top_incident
            .geometry()
            .buffer(500)
            .bounds()
        )

        vis_params = {
            "bands": ["B4", "B3", "B2"],
            "min": 0,
            "max": 3000,
            "gamma": 1.4
        }

        # Step 4: Fetch before/after satellite images
        img_2023, _, _ = get_mining_indices(
            request.lat,
            request.lon,
            "2023-01-01",
            "2023-06-01"
        )

        img_2024, _, _ = get_mining_indices(
            request.lat,
            request.lon,
            "2024-01-01",
            "2024-06-01"
        )

        before_url = img_2023.getThumbURL({
            **vis_params,
            "region": region,
            "dimensions": 512
        })

        after_url = img_2024.getThumbURL({
            **vis_params,
            "region": region,
            "dimensions": 512
        })

        # Step 5: Return structured detection result
        return {
            "alert": True,
            "incident_id": f"INC-{int(abs(lon_detected)*1000)}",
            "coordinates": {
                "lat": lat_detected,
                "lon": lon_detected
            },
            "area_hectares": round(area_sqm / 10000, 2),
            "evidence": {
                "before_image": before_url,
                "after_image": after_url
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}"
        )
    
# Automated Batch Scanning Endpoint
@app.get("/scan-all")
async def scan_watchlist():
    watchlist_path = os.path.join("data", "watchlist.json")
    
    if not os.path.exists(watchlist_path):
        return {"error": "Watchlist file not found in data/ folder."}

    with open(watchlist_path, "r") as f:
        watchlist = json.load(f)

    alerts = []
    for zone in watchlist:
        # We reuse your existing logic
        incidents = extract_incident_polygons(zone['lat'], zone['lon'], radius=2000)
        if incidents.size().getInfo() > 0:
            alerts.append({
                "zone_name": zone['name'],
                "location": [zone['lat'], zone['lon']],
                "status": "CRITICAL"
            })

    return {
        "total_zones_scanned": len(watchlist),
        "alerts_found": len(alerts),
        "incidents": alerts
    }



# PDF Download Endpoint
@app.get("/download-report/{incident_id}")
async def get_report(incident_id: str, lat: float, lon: float, area: float):
    file_path = create_pdf_report(incident_id, lat, lon, area)
    return FileResponse(path=file_path, filename=f"{incident_id}_Report.pdf", media_type='application/pdf')