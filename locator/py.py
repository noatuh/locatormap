from flask import Flask
from flask_cors import CORS
import subprocess
import requests
import json
import time
import sys

DEFAULT_SERVER_IP = "24.95.169.161:5050"

app = Flask(__name__)
CORS(app)

def get_input_with_default(prompt, default_value=None):
    if default_value:
        user_input = input(f"{prompt} (default: {default_value}): ").strip()
        if not user_input:
            return default_value
        return user_input
    else:
        return input(f"{prompt}: ").strip()

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

def send_location(server_url, phone_id):
    lat, lon = get_gps_coords()
    if lat is not None and lon is not None:
        try:
            response = requests.post(server_url, json={
                "id": phone_id,
                "lat": lat,
                "lng": lon
            })
            print(f"Sent location for {phone_id}: {lat}, {lon} - Status: {response.status_code}")
        except Exception as e:
            print("Error sending location:", e)

if __name__ == "__main__":
    print("GPS Location Sender Setup")
    print("-------------------------")
    
    # Get server IP from user or use default
    server_ip = get_input_with_default("Enter server IP:port", DEFAULT_SERVER_IP)
    SERVER_URL = f"http://{server_ip}/update_location"
    
    # Get phone ID, limited to 5 characters
    while True:
        PHONE_ID = input("Enter phone ID (max 5 characters): ").strip()
        if not PHONE_ID:
            print("Error: Phone ID cannot be empty.")
        elif len(PHONE_ID) > 5:
            print("Error: Phone ID must be 5 characters or less.")
        else:
            break
    
    print(f"\nStarting GPS location sender")
    print(f"Server URL: {SERVER_URL}")
    print(f"Phone ID: {PHONE_ID}")
    print("Send Ctrl+C to stop")
    print("-------------------------")
    
    try:
        while True:
            send_location(SERVER_URL, PHONE_ID)
            time.sleep(5)  # Send every 5 seconds
    except KeyboardInterrupt:
        print("\nGPS location sender stopped")
        sys.exit(0)
