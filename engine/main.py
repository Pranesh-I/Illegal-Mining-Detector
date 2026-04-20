import ee
import os
import uuid

# ==============================
# CONFIGURATION
# ==============================

PROJECT_ID = "illegal-mining-detector-493805"

NDVI_THRESHOLD = 0.2
BSI_THRESHOLD = 0.15
MIN_POLYGON_AREA = 500  # sqm


# ==============================
# INITIALIZE EARTH ENGINE
# ==============================

try:
    ee.Initialize(project=PROJECT_ID)
    print("✅ Connection to Google Earth Engine established.")
except Exception:
    ee.Authenticate()
    ee.Initialize(project=PROJECT_ID)


# ==============================
# FETCH SATELLITE DATA + INDICES
# ==============================

def get_mining_indices(lat, lon, date_start, date_end):
    """
    Fetch Sentinel-2 imagery and compute NDVI + BSI.
    Uses median composite for clarity improvement.
    """

    poi = ee.Geometry.Point([lon, lat])

    image = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(poi)
        .filterDate(date_start, date_end)
        .median()
    )

    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    bsi = image.expression(
        "((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))",
        {
            "B11": image.select("B11"),
            "B4": image.select("B4"),
            "B8": image.select("B8"),
            "B2": image.select("B2"),
        },
    ).rename("BSI")

    return image, ndvi, bsi


# ==============================
# DISTURBANCE ANALYSIS
# ==============================

def analyze_disturbance(lat, lon):

    print(f"\n--- Starting Analysis for Coordinates: {lat}, {lon} ---")

    _, ndvi_2023, bsi_2023 = get_mining_indices(
        lat, lon, "2023-01-01", "2023-06-01"
    )

    _, ndvi_2024, bsi_2024 = get_mining_indices(
        lat, lon, "2024-01-01", "2024-06-01"
    )

    ndvi_loss = ndvi_2023.subtract(ndvi_2024)
    bsi_gain = bsi_2024.subtract(bsi_2023)

    area = ee.Geometry.Point([lon, lat]).buffer(100)

    ndvi_stats = ndvi_loss.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=area,
        scale=10
    ).getInfo()

    bsi_stats = bsi_gain.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=area,
        scale=10
    ).getInfo()

    return ndvi_stats["NDVI"], bsi_stats["BSI"]


# ==============================
# EXTRACT DISTURBANCE POLYGONS
# ==============================

def extract_incident_polygons(lat, lon, radius=2000):

    print(f"🛰️ Scanning a {radius}m zone for illegal activity...")

    aoi = ee.Geometry.Point([lon, lat]).buffer(radius).bounds()

    _, ndvi_2023, bsi_2023 = get_mining_indices(
        lat, lon, "2023-01-01", "2023-06-01"
    )

    _, ndvi_2024, bsi_2024 = get_mining_indices(
        lat, lon, "2024-01-01", "2024-06-01"
    )

    ndvi_loss = ndvi_2023.subtract(ndvi_2024)
    bsi_gain = bsi_2024.subtract(bsi_2023)

    combined_mask = (
        ndvi_loss.gt(NDVI_THRESHOLD)
        .And(bsi_gain.gt(BSI_THRESHOLD))
    )

    mining_mask = combined_mask.selfMask()

    vectors = mining_mask.reduceToVectors(
        geometry=aoi,
        scale=10,
        geometryType="polygon",
        eightConnected=True,
        labelProperty="mining_zone"
    )

    def add_area(feature):
        return feature.set({
            "area_sqm": feature.geometry().area(maxError=1)
        })

    refined_incidents = (
        vectors.map(add_area)
        .filter(ee.Filter.gt("area_sqm", MIN_POLYGON_AREA))
        .sort("area_sqm", False)
    )

    return refined_incidents


# ==============================
# GENERATE EVIDENCE IMAGES
# ==============================

def generate_evidence_images(incident_feature, lat, lon):

    try:

        region = incident_feature.geometry().buffer(300).bounds()

        img_before, _, _ = get_mining_indices(
            lat, lon,
            "2019-01-01",
            "2019-12-31"
        )

        img_after, _, _ = get_mining_indices(
            lat, lon,
            "2024-01-01",
            "2024-12-31"
        )

        vis_params = {
            "bands": ["B12", "B11", "B4"],
            "min": 300,
            "max": 2000,
            "gamma": 1.3
        }

        before_url = img_before.getThumbURL({
            **vis_params,
            "region": region,
            "dimensions": 2048
        })

        after_url = img_after.getThumbURL({
            **vis_params,
            "region": region,
            "dimensions": 2048
        })

        if before_url is None:
            before_url = "NO_IMAGE_AVAILABLE"

        if after_url is None:
            after_url = "NO_IMAGE_AVAILABLE"

        return before_url, after_url

    except Exception as e:

        print("Thumbnail generation failed:", e)

        return "NO_IMAGE_AVAILABLE", "NO_IMAGE_AVAILABLE"


# ==============================
# MAIN EXECUTION PIPELINE
# ==============================

if __name__ == "__main__":

    target_lat = 21.825
    target_lon = 85.395

    ndvi_loss, bsi_gain = analyze_disturbance(
        target_lat,
        target_lon
    )

    print(f"Calculated NDVI Loss: {ndvi_loss:.4f}")
    print(f"Calculated BSI Gain: {bsi_gain:.4f}")

    if ndvi_loss > NDVI_THRESHOLD:
        print("🚨 Vegetation loss detected.")
    else:
        print("✅ Vegetation stable.")

    incidents = extract_incident_polygons(
        target_lat,
        target_lon
    )

    count = incidents.size().getInfo()

    print(f"🔍 Found {count} disturbance polygons.")

    if count > 0:

        top_incident = incidents.first()

        area = top_incident.get("area_sqm").getInfo()

        coords = (
            top_incident.geometry()
            .centroid(maxError=1)
            .coordinates()
            .getInfo()
        )

        before_url, after_url = generate_evidence_images(
            top_incident,
            target_lat,
            target_lon
        )

        incident_id = str(uuid.uuid4())[:8]

        print("\n" + "=" * 40)
        print("       OFFICIAL INCIDENT REPORT       ")
        print("=" * 40)
        print(f"ID:        INC-{incident_id}")
        print("STATUS:    CRITICAL DISTURBANCE")
        print(f"LOCATION:  {coords[1]:.5f} N, {coords[0]:.5f} E")
        print(f"AREA:      {area/10000:.2f} hectares")
        print("VERDICT:   Possible Illegal Excavation")
        print("-" * 40)
        print(f"Before Image: {before_url}")
        print(f"After Image:  {after_url}")
        print("=" * 40)

    else:
        print("✅ Monitoring Zone Clear.")