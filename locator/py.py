from flask import Flask
from flask_cors import CORS
import subprocess
import requests
import json
import time
import sys
import os
import select
import tty
import termios
import threading

DEFAULT_SERVER_IP = "24.95.163.76:5050"
CAMERA_PORT = 5051

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

def capture_and_send_photo(server_ip, phone_id):
    """Capture photo with termux and send to server"""
    filename = f"cam_{phone_id}.jpg"
    try:
        print("Capturing photo...")
        result = subprocess.run(["termux-camera-photo", "-c", "0", filename], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(filename):
            try:
                with open(filename, "rb") as f:
                    photo_data = f.read()
                    
                # Send photo to camera endpoint
                response = requests.post(f"http://{server_ip}:{CAMERA_PORT}/upload_photo", 
                                       data=photo_data,
                                       headers={"Content-Type": "application/octet-stream",
                                               "X-Phone-ID": phone_id},
                                       timeout=10)
                print(f"Sent photo: {response.status_code}")
                return True
            except Exception as e:
                print(f"Failed to send photo: {e}")
        else:
            print("Failed to capture photo")
    except Exception as e:
        print(f"Error capturing photo: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)
    return False

def key_pressed():
    """Check if a key has been pressed (non-blocking)"""
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

if __name__ == "__main__":
    print("GPS Location Sender + Camera Setup")
    print("----------------------------------")
    
    # Get server IP from user or use default
    server_ip_port = get_input_with_default("Enter server IP:port", DEFAULT_SERVER_IP)
    server_ip = server_ip_port.split(':')[0]  # Extract just IP for camera
    SERVER_URL = f"http://{server_ip_port}/update_location"
    
    # Get phone ID, limited to 5 characters
    while True:
        PHONE_ID = input("Enter phone ID (max 5 characters): ").strip()
        if not PHONE_ID:
            print("Error: Phone ID cannot be empty.")
        elif len(PHONE_ID) > 5:
            print("Error: Phone ID must be 5 characters or less.")
        else:
            break
    
    # Ask if user wants camera functionality
    enable_camera = input("Enable camera streaming? (y/n): ").strip().lower() == 'y'
    
    if enable_camera:
        # Test camera first
        print("Testing camera...")
        test_result = subprocess.run(["termux-camera-info"], capture_output=True, text=True)
        if test_result.returncode != 0:
            print("Warning: Camera may not be available. Continuing without camera...")
            enable_camera = False
        else:
            print("Camera detected successfully!")
    
    print(f"\nStarting GPS location sender")
    print(f"Server URL: {SERVER_URL}")
    print(f"Phone ID: {PHONE_ID}")
    print(f"Camera enabled: {enable_camera}")
    print("Press 'e' to exit, 'c' to toggle camera")
    print("----------------------------------")
    
    # Prepare terminal for key detection if camera enabled
    if enable_camera:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    
    camera_active = enable_camera
    last_photo_time = 0
    photo_interval = 3  # seconds between photos
    
    try:
        while True:
            # Always send location
            send_location(SERVER_URL, PHONE_ID)
            
            # Handle camera if enabled
            current_time = time.time()
            if camera_active and (current_time - last_photo_time) >= photo_interval:
                if capture_and_send_photo(server_ip, PHONE_ID):
                    last_photo_time = current_time
            
            # Check for key presses
            if enable_camera and key_pressed():
                ch = sys.stdin.read(1).lower()
                if ch == 'e':
                    print("Exit key pressed. Exiting...")
                    break
                elif ch == 'c':
                    camera_active = not camera_active
                    print(f"Camera {'activated' if camera_active else 'deactivated'}")
            
            time.sleep(1)  # Main loop delay
            
    except KeyboardInterrupt:
        print("\nGPS location sender stopped")
    finally:
        if enable_camera:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print("Terminal input restored.")
        sys.exit(0)
