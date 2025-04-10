from flask import Flask
from flask_cors import CORS
import subprocess
import requests
import json
import time

SERVER_URL = "http://24.95.169.161:5000/update_location"
PHONE_ID = "nota"  # You can customize this per phone

app = Flask(__name__)
CORS(app)

def get_gps_coords():
    try:
        result = subprocess.run(["termux-location"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            lat = data.get("latitude")
            lon = data.get("longitude")
            if lat is not None and lon is not None:
                return lat, lon
    except Exception as e:
        print("Error getting location:", e)
    return None, None

def send_location():
    lat, lon = get_gps_coords()
    if lat is not None and lon is not None:
        try:
            response = requests.post(SERVER_URL, json={
                "id": PHONE_ID,
                "lat": lat,
                "lng": lon
            })
            print("Sent:", response.status_code, response.json())
        except Exception as e:
            print("Error sending location:", e)

if __name__ == "__main__":
    print(f"Starting GPS location sender for {PHONE_ID}")
    while True:
        send_location()
        time.sleep(5)  # Send every 5 seconds (tweak as needed)
