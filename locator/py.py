from flask import Flask
from flask_cors import CORS
import subprocess
import requests
import json
import time
import sys
import os
import math

# Configuration file for storing server settings
CONFIG_FILE = "server_config.json"

app = Flask(__name__)
CORS(app)

def load_config():
    """Load server configuration from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('server_ip_port', None)
    except Exception as e:
        print(f"Error loading config: {e}")
    return None

def save_config(server_ip_port):
    """Save server configuration to JSON file"""
    try:
        config = {'server_ip_port': server_ip_port}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Server configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

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
            alt = data.get("altitude")
            if lat is not None and lon is not None:
                return lat, lon, alt
    except Exception as e:
        print("Error getting location:", e)
    return None, None, None

# GPS tracking for movement direction
gps_history = []
MAX_GPS_HISTORY = 5  # Keep last 5 GPS positions
MIN_MOVEMENT_DISTANCE = 3  # Minimum movement in meters to calculate direction

def calculate_gps_heading(lat1, lon1, lat2, lon2):
    """Calculate heading (direction of travel) between two GPS points"""
    try:
        import math
        
        print(f"DEBUG: Calculating heading from ({lat1:.6f}, {lon1:.6f}) to ({lat2:.6f}, {lon2:.6f})")
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)
        
        # Calculate difference in longitude
        dlon = lon2_rad - lon1_rad
        
        # Calculate bearing
        y = math.sin(dlon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))
        
        bearing = math.atan2(y, x)
        
        # Convert to degrees and normalize to 0-360
        bearing_deg = math.degrees(bearing)
        if bearing_deg < 0:
            bearing_deg += 360
        
        print(f"DEBUG: Calculated raw bearing: {math.degrees(bearing):.2f}°, normalized: {bearing_deg:.2f}°")
            
        return bearing_deg
    except Exception as e:
        print(f"Error calculating GPS heading: {e}")
        return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS points in meters"""
    try:
        import math
        
        # Radius of the Earth in meters
        R = 6371000
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        distance = R * c
        return distance
    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None

def get_cardinal_direction(heading):
    """Convert heading degrees to cardinal direction"""
    if heading is None:
        return "Unknown"
    
    # 8-point compass directions
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    index = round(heading / 45) % 8
    return directions[index]

def get_movement_heading(lat, lon):
    """Calculate heading based on GPS movement history"""
    global gps_history
    
    # Add current position to history
    current_time = time.time()
    gps_history.append({
        'lat': lat,
        'lon': lon,
        'time': current_time
    })
    
    print(f"DEBUG: Added GPS point #{len(gps_history)}: {lat:.6f}, {lon:.6f}")
    
    # Keep only recent history
    if len(gps_history) > MAX_GPS_HISTORY:
        gps_history = gps_history[-MAX_GPS_HISTORY:]
        print(f"DEBUG: Trimmed GPS history to {MAX_GPS_HISTORY} points")
    
    # Need at least 2 points to calculate direction
    if len(gps_history) < 2:
        print("DEBUG: Not enough GPS points for direction calculation")
        return None
    
    # Find the best pair of points for direction calculation
    # Use the oldest and newest points that are far enough apart
    best_heading = None
    max_distance = 0
    
    current_pos = gps_history[-1]
    print(f"DEBUG: Analyzing {len(gps_history)} GPS points for direction...")
    
    for i in range(len(gps_history) - 1):
        old_pos = gps_history[i]
        distance = calculate_distance(old_pos['lat'], old_pos['lon'], 
                                    current_pos['lat'], current_pos['lon'])
        
        print(f"DEBUG: Point {i} -> current: distance = {distance:.2f}m")
        
        if distance and distance >= MIN_MOVEMENT_DISTANCE and distance > max_distance:
            heading = calculate_gps_heading(old_pos['lat'], old_pos['lon'],
                                          current_pos['lat'], current_pos['lon'])
            if heading is not None:
                cardinal = get_cardinal_direction(heading)
                print(f"DEBUG: Valid movement found! Distance: {distance:.2f}m, Heading: {heading:.1f}° ({cardinal})")
                best_heading = heading
                max_distance = distance
    
    if best_heading is None:
        print(f"DEBUG: No movement >= {MIN_MOVEMENT_DISTANCE}m detected. Max distance: {max_distance:.2f}m")
    else:
        print(f"DEBUG: Final heading: {best_heading:.1f}° ({get_cardinal_direction(best_heading)}) based on {max_distance:.2f}m movement")
    
    return best_heading
    """Calculate compass heading from magnetometer and accelerometer data"""
    try:
        import math
        
        # Extract values
        mx, my, mz = magnetometer
        ax, ay, az = accelerometer
        
        # Normalize accelerometer values
        norm = math.sqrt(ax*ax + ay*ay + az*az)
        if norm == 0:
            return None
        ax, ay, az = ax/norm, ay/norm, az/norm
        
        # Calculate roll and pitch from accelerometer
        roll = math.atan2(ay, az)
        pitch = math.atan2(-ax, math.sqrt(ay*ay + az*az))
        
        # Compensate magnetometer readings for tilt
        cos_roll = math.cos(roll)
        sin_roll = math.sin(roll)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)
        
        # Tilt compensated magnetic field components
        mx_comp = mx * cos_pitch + mz * sin_pitch
        my_comp = mx * sin_roll * sin_pitch + my * cos_roll - mz * sin_roll * cos_pitch
        
        # Calculate heading (0-360 degrees)
        heading = math.atan2(-my_comp, mx_comp) * 180 / math.pi
        
        # Normalize to 0-360
        if heading < 0:
            heading += 360
            
        return heading
    except Exception as e:
        print(f"Error calculating compass heading: {e}")
        return None

def send_location(server_url, phone_id):
    lat, lon, alt = get_gps_coords()
    if lat is not None and lon is not None:
        try:
            print(f"\nDEBUG: Got GPS coordinates: {lat:.6f}, {lon:.6f}, Alt: {alt}")
            
            # Calculate movement-based heading
            heading = get_movement_heading(lat, lon)
            
            payload = {
                "id": phone_id,
                "lat": lat,
                "lng": lon,
                "alt": alt
            }
            
            # Add heading data if available
            if heading is not None:
                cardinal = get_cardinal_direction(heading)
                payload["heading"] = heading
                payload["accuracy"] = 10  # GPS-based heading accuracy
                print(f"DEBUG: Sending heading data: {heading:.1f}° ({cardinal})")
            else:
                print("DEBUG: No heading data to send (building movement history or insufficient movement)")
            
            print(f"DEBUG: Payload: {payload}")
            response = requests.post(server_url, json=payload)
            
            if heading is not None:
                cardinal = get_cardinal_direction(heading)
                print(f"✓ Sent location for {phone_id}: {lat:.6f}, {lon:.6f}, Alt: {alt}, heading: {heading:.1f}° ({cardinal}) - Status: {response.status_code}")
            else:
                print(f"✓ Sent location for {phone_id}: {lat:.6f}, {lon:.6f}, Alt: {alt} (building movement history) - Status: {response.status_code}")
                
        except Exception as e:
            print("Error sending location:", e)

if __name__ == "__main__":
    print("GPS Location Sender with Movement Direction")
    print("-------------------------------------------")
    
    # Load existing server configuration or prompt for new one
    saved_ip = load_config()
    
    if saved_ip:
        print(f"Found saved server configuration: {saved_ip}")
        use_saved = input("Use saved server IP? (y/n, default: y): ").strip().lower()
        if use_saved in ['', 'y', 'yes']:
            server_ip_port = saved_ip
        else:
            server_ip_port = input("Enter new server IP:port: ").strip()
            if server_ip_port:
                save_config(server_ip_port)
    else:
        print("No saved server configuration found.")
        server_ip_port = input("Enter server IP:port: ").strip()
        if server_ip_port:
            save_config(server_ip_port)
    
    if not server_ip_port:
        print("Error: Server IP:port is required.")
        sys.exit(1)
    
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
    
    # Test GPS functionality
    print("Testing GPS functionality...")
    try:
        test_lat, test_lon, test_alt = get_gps_coords()
        if test_lat is not None and test_lon is not None:
            print(f"✓ GPS test successful! Current location: {test_lat:.6f}, {test_lon:.6f}, Altitude: {test_alt}m")
            print("Direction will be calculated based on movement between GPS positions.")
            print(f"Minimum movement distance for direction: {MIN_MOVEMENT_DISTANCE} meters")
        else:
            print("⚠ GPS test failed. Please check location permissions.")
    except Exception as e:
        print(f"⚠ GPS test failed: {e}")
    
    print(f"\nStarting GPS location sender with movement-based direction")
    print(f"Server URL: {SERVER_URL}")
    print(f"Phone ID: {PHONE_ID}")
    print("Press Ctrl+C to exit")
    print("----------------------------------")
    
    try:
        while True:
            # Send location data with movement-based heading
            send_location(SERVER_URL, PHONE_ID)
            time.sleep(2)  # Send location every 2 seconds
            
    except KeyboardInterrupt:
        print("\nGPS location sender stopped")
        sys.exit(0)
