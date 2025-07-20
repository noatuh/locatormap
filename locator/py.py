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
import base64

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

# --- New Global State and Sensor Thread ---

# Thread-safe lock for accessing sensor data
sensor_data_lock = threading.Lock()

# Global dictionary to hold the latest sensor readings and phone state
latest_sensor_data = {
    "accelerometer": None,
    "magnetometer": None,
    "heading": None,
    "accuracy": None,
    "is_stable": False,
    "last_accel_raw": None,
    "stable_since": 0
}

# Constants for stability detection
STABILITY_THRESHOLD = 0.5  # Lower is more sensitive. Change in m/s^2
STABILITY_DURATION = 0.5   # Must be stable for this many seconds

def sensor_polling_thread():
    """A dedicated thread to continuously poll sensors and determine stability."""
    global latest_sensor_data
    print("Sensor polling thread started")

    while True:
        try:
            # Fetch raw sensor data without processing
            raw_accel, raw_magnet = get_raw_sensor_data()
            
            is_currently_stable = False
            
            if raw_accel:
                # --- Motion Detection Logic ---
                with sensor_data_lock:
                    last_accel = latest_sensor_data.get("last_accel_raw")
                
                if last_accel:
                    # Calculate the magnitude of the change in acceleration
                    delta = sum(abs(raw_accel[i] - last_accel[i]) for i in range(3))
                    
                    if delta < STABILITY_THRESHOLD:
                        # Phone is currently stable
                        with sensor_data_lock:
                            if latest_sensor_data["stable_since"] == 0:
                                latest_sensor_data["stable_since"] = time.time()
                            
                            # Check if it's been stable for long enough
                            if (time.time() - latest_sensor_data["stable_since"]) > STABILITY_DURATION:
                                is_currently_stable = True
                    else:
                        # Phone is moving
                        with sensor_data_lock:
                            latest_sensor_data["stable_since"] = 0
                
                with sensor_data_lock:
                    latest_sensor_data["last_accel_raw"] = raw_accel
            
            # --- Update Global State ---
            with sensor_data_lock:
                latest_sensor_data["is_stable"] = is_currently_stable
                
                if raw_accel and raw_magnet:
                    latest_sensor_data["accelerometer"] = raw_accel
                    latest_sensor_data["magnetometer"] = raw_magnet
                    
                    # Calculate heading only if we have valid data
                    if is_valid_sensor_data(raw_magnet, raw_accel):
                        heading = calculate_compass_heading(raw_magnet, raw_accel)
                        if heading is not None:
                            latest_sensor_data["heading"] = heading
                            latest_sensor_data["accuracy"] = 15 # Default accuracy
            
            # Adjust polling frequency
            time.sleep(0.25) # Poll 4 times per second

        except Exception as e:
            print(f"Error in sensor thread: {e}")
            time.sleep(1) # Wait a bit before retrying

def get_raw_sensor_data():
    """Gets raw accelerometer and magnetometer data without complex logic."""
    try:
        result = subprocess.run(["termux-sensor", "-s", "magnetometer,accelerometer", "-n", "1"], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and result.stdout.strip():
            sensor_data = json.loads(result.stdout)
            magnetometer = None
            accelerometer = None

            if isinstance(sensor_data, dict):
                for name, info in sensor_data.items():
                    if isinstance(info, dict) and "values" in info:
                        if 'magnetometer' in name.lower():
                            magnetometer = info["values"]
                        elif 'accelerometer' in name.lower():
                            accelerometer = info["values"]
            return accelerometer, magnetometer
            
    except Exception as e:
        print(f"Could not get raw sensor data: {e}")
        
    return None, None

def get_sensor_data():
    """Get compass/orientation data from the sensor thread's cache."""
    try:
        # Use cached sensor data for faster access
        with sensor_data_lock:
            heading = latest_sensor_data.get("heading")
            accuracy = latest_sensor_data.get("accuracy")
        
        if heading is not None:
            return heading, accuracy
        else:
            # This is expected if the sensor thread hasn't produced a heading yet
            pass
            
    except Exception as e:
        print(f"Error getting sensor data from cache: {e}")
    return None, None

def extract_sensor_values(sensor_data, keywords):
    """Extract sensor values from various data formats"""
    try:
        if isinstance(sensor_data, dict):
            for sensor_name, sensor_info in sensor_data.items():
                if isinstance(sensor_info, dict) and "values" in sensor_info:
                    if any(keyword in sensor_name.lower() for keyword in keywords):
                        return sensor_info["values"]
        elif isinstance(sensor_data, list) and len(sensor_data) > 0:
            for item in sensor_data:
                if isinstance(item, dict) and "values" in item:
                    sensor_name = item.get("sensor", "").lower()
                    if any(keyword in sensor_name for keyword in keywords):
                        return item["values"]
    except:
        pass
    return None

def is_valid_sensor_data(magnetometer, accelerometer):
    """Validate that sensor data contains reasonable values"""
    try:
        # Check magnetometer values (typical range: -100 to +100 μT)
        if len(magnetometer) != 3 or not all(isinstance(x, (int, float)) for x in magnetometer):
            return False
        mag_magnitude = sum(x*x for x in magnetometer)**0.5
        if mag_magnitude < 1 or mag_magnitude > 200:  # Reasonable magnetic field range
            print(f"Warning: Magnetometer magnitude {mag_magnitude:.1f} μT seems unusual")
            
        # Check accelerometer values (typical range: -20 to +20 m/s²)
        if len(accelerometer) != 3 or not all(isinstance(x, (int, float)) for x in accelerometer):
            return False
        acc_magnitude = sum(x*x for x in accelerometer)**0.5
        if acc_magnitude < 5 or acc_magnitude > 25:  # Should be close to 9.8 m/s²
            print(f"Warning: Accelerometer magnitude {acc_magnitude:.1f} m/s² seems unusual")
            
        return True
    except:
        return False

def calculate_compass_heading(magnetometer, accelerometer):
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

def warm_up_camera():
    """Warm up camera to prevent black screen issues"""
    try:
        temp_file = "temp_warmup.jpg"
        print("Warming up camera...")
        
        # Quick capture to warm up camera (don't save/send this)
        result = subprocess.run([
            "termux-camera-photo", 
            "-c", "0", 
            temp_file
        ], capture_output=True, text=True, timeout=10)
        
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        if result.returncode == 0:
            print("Camera warmed up successfully")
            return True
        else:
            print("Camera warm-up failed")
            return False
    except Exception as e:
        print(f"Error warming up camera: {e}")
        return False

def release_camera():
    """Force release camera resources to prevent conflicts"""
    try:
        # Kill any existing camera processes
        subprocess.run(["pkill", "-f", "termux-camera"], capture_output=True, timeout=3)
        time.sleep(0.2)  # Short delay to let processes die
    except:
        pass

def advanced_camera_capture(filename, retries=2):
    """Enhanced camera capture with session management"""
    for attempt in range(retries + 1):
        try:
            if attempt > 0:
                print(f"Camera capture retry {attempt}/{retries}")
                # Release any stuck camera processes
                release_camera()
                time.sleep(1.0)  # Longer delay between retries
            
            # Use different camera parameters for reliability
            camera_args = [
                "termux-camera-photo",
                "-c", "0",  # Back camera
                filename
            ]
            
            # Add autofocus if device supports it (helps with black screens)
            result = subprocess.run(camera_args, 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=20)  # Longer timeout for difficult captures
            
            if result.returncode == 0:
                # Verify capture was successful
                if os.path.exists(filename):
                    file_size = os.path.getsize(filename)
                    if file_size > 5000:  # Require at least 5KB for valid image
                        print(f"Camera capture successful on attempt {attempt + 1} ({file_size} bytes)")
                        return True
                    else:
                        print(f"Captured file too small ({file_size} bytes), retrying...")
                        if os.path.exists(filename):
                            os.remove(filename)
                else:
                    print("No file created, retrying...")
            else:
                print(f"Camera returned error code {result.returncode}: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"Camera capture timeout on attempt {attempt + 1}")
            # Kill the hung process
            try:
                subprocess.run(["pkill", "-f", "termux-camera"], timeout=2)
            except:
                pass
        except Exception as e:
            print(f"Camera capture error on attempt {attempt + 1}: {e}")
    
    return False

def send_photo_json(server_ip, phone_id, photo_data, heading=None, accuracy=None):
    """Alternative transmission method using JSON encoding"""
    try:
        # Encode photo as base64
        photo_b64 = base64.b64encode(photo_data).decode('utf-8')
        
        # Prepare JSON payload
        payload = {
            "phone_id": phone_id,
            "photo_data": photo_b64,
            "timestamp": int(time.time()),
            "file_size": len(photo_data)
        }
        
        # Add compass data if available
        if heading is not None:
            payload["heading"] = heading
            payload["accuracy"] = accuracy
        
        # Send as JSON
        response = requests.post(f"http://{server_ip}:{CAMERA_PORT}/upload_photo_json", 
                               json=payload,
                               headers={"Content-Type": "application/json"},
                               timeout=20)
        
        if response.status_code == 200:
            print(f"✓ Photo uploaded via JSON ({len(photo_data)} bytes)")
            return True
        else:
            print(f"✗ JSON upload failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"JSON upload error: {e}")
        return False

def send_photo_binary(server_ip, phone_id, photo_data, heading=None, accuracy=None):
    """Original binary transmission method"""
    try:
        # Prepare headers with enhanced metadata
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Phone-ID": phone_id,
            "X-Timestamp": str(int(time.time())),
            "X-File-Size": str(len(photo_data))
        }
        
        # Add compass data to headers if available
        if heading is not None:
            headers["X-Camera-Heading"] = str(heading)
            headers["X-Camera-Accuracy"] = str(accuracy)
        
        # Send with binary data
        response = requests.post(f"http://{server_ip}:{CAMERA_PORT}/upload_photo", 
                               data=photo_data,
                               headers=headers,
                               timeout=15,
                               stream=False)
        
        if response.status_code == 200:
            print(f"✓ Photo uploaded via binary ({len(photo_data)} bytes)")
            return True
        else:
            print(f"✗ Binary upload failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Binary upload error: {e}")
        return False

def capture_and_send_photo(server_ip, phone_id):
    """Capture photo with termux and send to server along with compass data"""
    filename = f"cam_{phone_id}.jpg"
    try:
        print("Capturing photo...")
        
        # Enhanced camera capture with session management
        time.sleep(0.3)  # Brief stabilization delay
        
        # Use advanced capture method with retries
        if not advanced_camera_capture(filename):
            print("All camera capture attempts failed")
            return False
            
        print(f"Photo captured successfully")
        
        try:
            # Get compass heading
            heading, accuracy = get_sensor_data()
            
            with open(filename, "rb") as f:
                photo_data = f.read()
            
            # Try both transmission methods for reliability
            success = False
            
            # First try binary method (faster)
            if send_photo_binary(server_ip, phone_id, photo_data, heading, accuracy):
                success = True
            # If binary fails, try JSON method (more reliable)
            elif send_photo_json(server_ip, phone_id, photo_data, heading, accuracy):
                success = True
                print("Used JSON fallback transmission")
            
            if success and heading is not None:
                print(f"Compass heading: {heading:.1f}° (±{accuracy}°)")
                
            return success
                
        except Exception as e:
            print(f"Failed to process photo: {e}")
            return False
        
    except Exception as e:
        print(f"Error capturing photo: {e}")
        return False
    finally:
        # Always clean up the file
        if os.path.exists(filename):
            os.remove(filename)

# Thread-safe lock for camera state
camera_active_lock = threading.Lock()

def camera_capture_thread(server_ip, phone_id):
    """A dedicated thread to capture photos when the phone is stable."""
    global camera_active
    last_capture_time = 0
    capture_interval = 8  # Minimum seconds between captures

    print("Camera capture thread started")

    while True:
        try:
            with camera_active_lock:
                is_active = camera_active

            if not is_active:
                time.sleep(1)
                continue

            current_time = time.time()
            is_stable = False
            with sensor_data_lock:
                is_stable = latest_sensor_data.get("is_stable", False)

            # Check for stability and time interval
            if is_stable and (current_time - last_capture_time) > capture_interval:
                print("Phone is stable, attempting to capture photo...")
                success = capture_and_send_photo(server_ip, phone_id)
                if success:
                    print("✓ Photo capture and send successful.")
                    last_capture_time = time.time()
                else:
                    print("✗ Photo capture failed. Will retry when stable again.")
                    # Optional: add a small delay after a failure to prevent rapid retries
                    time.sleep(2)
            
            time.sleep(0.5) # Check for stability twice a second

        except Exception as e:
            print(f"Error in camera thread: {e}")
            time.sleep(2) # Wait a bit before retrying

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
            
            # Warm up camera to prevent initial black screen
            print("Warming up camera system...")
            if warm_up_camera():
                print("✓ Camera system ready")
            else:
                print("⚠ Camera warm-up failed, may have issues initially")
            
            # Test sensors for compass functionality
            print("Testing compass sensors...")
            try:
                sensor_test = subprocess.run(["termux-sensor", "-l"], capture_output=True, text=True, timeout=5)
                if sensor_test.returncode == 0:
                    available_sensors = sensor_test.stdout.lower()
                    
                    # Check for magnetometer variants
                    has_magnetometer = any(keyword in available_sensors for keyword in 
                                         ['magnetometer', 'magnetic', 'compass'])
                    
                    # Check for accelerometer variants  
                    has_accelerometer = any(keyword in available_sensors for keyword in 
                                          ['accelerometer', 'accel', 'acceleration'])
                    
                    if has_magnetometer and has_accelerometer:
                        print("✓ Compass sensors available!")
                        # Test actual sensor reading
                        print("Testing sensor data retrieval...")
                        # We need to give the sensor thread a moment to start and get a reading
                        time.sleep(2) 
                        with sensor_data_lock:
                            test_heading = latest_sensor_data.get("heading")

                        if test_heading is not None:
                            print(f"✓ Compass test successful! Current heading: {test_heading:.1f}°")
                        else:
                            print("⚠ Compass sensors detected but data retrieval failed")
                    else:
                        missing = []
                        if not has_magnetometer:
                            missing.append("magnetometer")
                        if not has_accelerometer:
                            missing.append("accelerometer")
                        print(f"⚠ Missing sensors for compass: {', '.join(missing)}")
                        print("Photos will be sent without direction data.")
                else:
                    print("⚠ Could not detect sensors. Photos will be sent without direction data.")
            except Exception as e:
                print(f"⚠ Sensor test failed: {e}. Photos will be sent without direction data.")
    
    print(f"\nStarting GPS location sender")
    print(f"Server URL: {SERVER_URL}")
    print(f"Phone ID: {PHONE_ID}")
    
    # Global flag for camera state
    camera_active = enable_camera

    if camera_active:
        print("\n📷 STABILITY-BASED CAMERA SYSTEM:")
        print("• Camera captures photos ONLY when the phone is held steady.")
        print("• Decoupled sensor and camera threads for reliability.")
        print("• Eliminates black screens caused by motion/resource conflicts.")
        print("\n🎮 CONTROLS:")
        print("• 'c' = Toggle camera on/off")
        print("• 'e' = Exit application")
    else:
        print("Press 'e' to exit")
    print("----------------------------------")
    
    # Prepare terminal for key detection
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    
    # Start the background threads
    sensor_thread = threading.Thread(target=sensor_polling_thread, daemon=True)
    sensor_thread.start()

    if camera_active:
        camera_thread = threading.Thread(target=camera_capture_thread, args=(server_ip, PHONE_ID), daemon=True)
        camera_thread.start()
    
    try:
        while True:
            # Main thread only sends location and handles user input
            send_location(SERVER_URL, PHONE_ID)
            
            # Check for key presses
            if key_pressed():
                ch = sys.stdin.read(1).lower()
                if ch == 'e':
                    print("Exit key pressed. Exiting...")
                    break
                elif ch == 'c' and enable_camera:
                    with camera_active_lock:
                        camera_active = not camera_active
                    status = "activated" if camera_active else "deactivated"
                    print(f"\nCamera has been {status}.")
            
            time.sleep(2)  # Location update interval
            
    except KeyboardInterrupt:
        print("\nGPS location sender stopped")
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print("Terminal input restored.")
        sys.exit(0)
