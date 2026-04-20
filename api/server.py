from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ee
import sys
import os

# Ensure engine module is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from engine.main import extract_incident_polygons, get_mining_indices


# Initialize FastAPI
app = FastAPI(title="Illegal Mining Detector API")


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