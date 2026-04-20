import ee

# 1. Initialize the Earth Engine API
try:
    ee.Initialize(project='illegal-mining-detector-493805') # You'll get this from GEE Console
except Exception as e:
    ee.Authenticate()
    ee.Initialize()

def get_sentinel_image(lat, lon, date_start, date_end):
    """
    Fetches a cloud-free Sentinel-2 image for a specific coordinate and time.
    """
    # Define the point of interest
    poi = ee.Geometry.Point([lon, lat])

    # Filter the Sentinel-2 collection
    image = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
             .filterBounds(poi)
             .filterDate(date_start, date_end)
             # Sort by cloud cover so we get the clearest image
             .sort('CLOUDY_PIXEL_PERCENTAGE')
             .first())
    
    return image

# Test it: Let's look at a known mining region
# Example: Keonjhar, Odisha (Approx: 21.7, 85.5)
test_img = get_sentinel_image(85.5, 21.7, '2023-01-01', '2023-12-31')
print(f"Successfully fetched image ID: {test_img.get('system:id').getInfo()}")