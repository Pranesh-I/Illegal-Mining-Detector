import ee
import os

# 1. Initialize the Earth Engine Command Center
# Using your specific Project ID
PROJECT_ID = 'illegal-mining-detector-493805'

try:
    ee.Initialize(project=PROJECT_ID)
    print("✅ Connection to Google Earth Engine established.")
except Exception as e:
    print(f"❌ Initialization failed. Did you run 'earthengine authenticate'? Error: {e}")

def get_mining_indices(lat, lon, date_start, date_end):
    """
    Fetches the best cloud-free Sentinel-2 image and calculates
    NDVI (Vegetation) and BSI (Bare Soil).
    """
    poi = ee.Geometry.Point([lon, lat])

    # Sentinel-2 Surface Reflectance Collection
    image = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
             .filterBounds(poi)
             .filterDate(date_start, date_end)
             .sort('CLOUDY_PIXEL_PERCENTAGE')
             .median())

    if image is None:
        raise ValueError(f"No satellite data found for {lat}, {lon} in range {date_start} to {date_end}")

    # FORMULA 1: NDVI (Normalized Difference Vegetation Index)
    # (NIR - Red) / (NIR + Red)
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    # FORMULA 2: BSI (Bare Soil Index)
    # ( (SWIR + Red) - (NIR + Blue) ) / ( (SWIR + Red) + (NIR + Blue) )
    bsi = image.expression(
        '(( (B11 + B4) - (B8 + B2) ) / ( (B11 + B4) + (B8 + B2) ))', {
            'B11': image.select('B11'),
            'B4': image.select('B4'),
            'B8': image.select('B8'),
            'B2': image.select('B2')
        }).rename('BSI')

    return image, ndvi, bsi

def analyze_disturbance(lat, lon):
    """
    Compares two time periods to detect forest loss and soil exposure.
    """
    print(f"\n--- Starting Analysis for Coordinates: {lat}, {lon} ---")
    
    # Define "Before" and "After" timeframes
    # Period 1: Jan - June 2023 (Baseline)
    _, ndvi_2023, bsi_2023 = get_mining_indices(lat, lon, '2023-01-01', '2023-06-01')
    
    # Period 2: Jan - June 2024 (Current)
    _, ndvi_2024, bsi_2024 = get_mining_indices(lat, lon, '2024-01-01', '2024-06-01')

    # MATH: Difference Layers
    # If this is positive, it means NDVI dropped (Vegetation Loss)
    ndvi_loss = ndvi_2023.subtract(ndvi_2024).rename('NDVI_Loss')
    
    # If this is positive, it means BSI increased (New Soil Exposure)
    bsi_gain = bsi_2024.subtract(bsi_2023).rename('BSI_Gain')

    # CALCULATE STATISTICS: Average the change within a 100m radius of the point
    area_of_interest = ee.Geometry.Point([lon, lat]).buffer(100) # 100m buffer
    
    stats = ndvi_loss.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=area_of_interest,
        scale=10
    ).getInfo()

    return stats['NDVI_Loss']

# --- EXECUTION BLOCK ---
if __name__ == "__main__":
    # SETTINGS
    target_lat, target_lon = 21.825, 85.395 # Hotspot in Keonjhar, Odisha
    alert_threshold = 0.2  # Threshold for "significant" forest loss

    try:
        change_val = analyze_disturbance(target_lat, target_lon)
        
        print(f"Calculated NDVI Loss: {change_val:.4f}")

        if change_val > alert_threshold:
            print("🚨 ALERT: Potential Illegal Mining / Surface Disturbance Detected!")
            print(f"Confidence: {min(change_val * 150, 100):.1f}%")
        elif change_val < -alert_threshold:
            print("🌱 STATUS: Significant Vegetation Regrowth Detected.")
        else:
            print("✅ STATUS: Land is stable. No major illegal activity detected.")
            
    except Exception as e:
        print(f"⚠️ An error occurred during analysis: {e}")

def extract_incident_polygons(lat, lon, radius=2000):
    print(f"🛰️ Scanning a {radius}m zone for illegal activity...")
    aoi = ee.Geometry.Point([lon, lat]).buffer(radius).bounds()

    # Get Before/After NDVI
    _, ndvi_2023, _ = get_mining_indices(lat, lon, '2023-01-01', '2023-06-01')
    _, ndvi_2024, _ = get_mining_indices(lat, lon, '2024-01-01', '2024-06-01')

    # Create Mask (NDVI Loss > 0.2)
    diff = ndvi_2023.subtract(ndvi_2024)
    mining_mask = diff.gt(0.2).selfMask()

    # Vectorize
    vectors = mining_mask.reduceToVectors(
        geometry=aoi,
        scale=10,
        geometryType='polygon',
        eightConnected=True,
        labelProperty='mining_zone'
    )

    # --- NEW: Add Area Calculation and Filtering ---
    def add_area(feature):
        return feature.set({'area_sqm': feature.geometry().area(maxError = 1)})

    # Filter out polygons smaller than 500sqm (approx 5 pixels)
    refined_incidents = (vectors.map(add_area)
                         .filter(ee.Filter.gt('area_sqm', 500))
                         .sort('area_sqm', False)) # Biggest incidents first

    return refined_incidents

import os

def generate_evidence_images(incident_feature, lat, lon, folder="data/alerts"):

    if not os.path.exists(folder):
        os.makedirs(folder)

    region = incident_feature.geometry().buffer(500).bounds()

    img_before, _, _ = get_mining_indices(lat, lon, '2023-01-01', '2023-06-01')
    img_after, _, _ = get_mining_indices(lat, lon, '2024-01-01', '2024-06-01')

    vis_params = {
        'bands': ['B4', 'B3', 'B2'],
        'min': 0,
        'max': 3000,
        'gamma': 1.4
    }

    url_before = img_before.getThumbURL({
        **vis_params,
        'region': region,
        'dimensions': 512
    })

    url_after = img_after.getThumbURL({
        **vis_params,
        'region': region,
        'dimensions': 512
    })

    print("🖼️ Evidence Generated!")
    print(f"Before Image: {url_before}")
    print(f"After Image: {url_after}")

    return url_before, url_after

# --- UPDATED EXECUTION BLOCK ---
if __name__ == "__main__":
    target_lat, target_lon = 21.825, 85.395 
    
    try:
        incidents = extract_incident_polygons(target_lat, target_lon)
        count = incidents.size().getInfo()
        
        if count > 0:
            top_incident = incidents.first()
            area = top_incident.get('area_sqm').getInfo()
            coords = top_incident.geometry().centroid(maxError=1).coordinates().getInfo()
            
            # GENERATE EVIDENCE
            before_url, after_url = generate_evidence_images(top_incident, target_lat, target_lon)

            # --- THE INCIDENT REPORT ---
            print("\n" + "="*40)
            print("       OFFICIAL INCIDENT REPORT       ")
            print("="*40)
            print(f"ID:        INC-{int(coords[0]*1000)}")
            print(f"STATUS:    CRITICAL DISTURBANCE")
            print(f"LOCATION:  {coords[1]:.5f} N, {coords[0]:.5f} E")
            print(f"AREA:      {area/10000:.2f} Hectares")
            print(f"VERDICT:   Possible Illegal Excavation")
            print("-" * 40)
            print(f"View Comparison: {before_url}")
            print("="*40)
            
        else:
            print("✅ Status: Monitoring Zone Clear.")

    except Exception as e:
        print(f"⚠️ System Error: {e}")


