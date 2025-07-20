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

def get_sensor_data():
    """Get compass/orientation data from sensors - compatible with various Android devices"""
    try:
        # Try combined sensor call first
        result = subprocess.run(["termux-sensor", "-s", "magnetometer,accelerometer", "-n", "1"], 
                              capture_output=True, text=True, timeout=5)
        
        magnetometer = None
        accelerometer = None
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                print(f"Raw sensor data: {result.stdout}")  # Debug output
                sensor_data = json.loads(result.stdout)
                
                # Handle different possible formats
                if isinstance(sensor_data, dict):
                    # Format: {"sensor_name": {"values": [x, y, z]}, ...}
                    for sensor_name, sensor_info in sensor_data.items():
                        if isinstance(sensor_info, dict) and "values" in sensor_info:
                            sensor_lower = sensor_name.lower()
                            
                            # Check for magnetometer (various naming patterns)
                            if any(keyword in sensor_lower for keyword in ['magnetometer', 'magnetic', 'compass']):
                                magnetometer = sensor_info["values"]
                                print(f"Found magnetometer: {sensor_name}")
                                
                            # Check for accelerometer (various naming patterns)
                            elif any(keyword in sensor_lower for keyword in ['accelerometer', 'accel', 'acceleration']):
                                accelerometer = sensor_info["values"]
                                print(f"Found accelerometer: {sensor_name}")
                        
                elif isinstance(sensor_data, list):
                    # Format: [{"sensor": "magnetometer", "values": [x, y, z]}, ...]
                    for sensor in sensor_data:
                        if isinstance(sensor, dict):
                            sensor_name = sensor.get("sensor", "").lower()
                            
                            # Flexible magnetometer detection
                            if any(keyword in sensor_name for keyword in ['magnetometer', 'magnetic', 'compass']):
                                magnetometer = sensor.get("values", [0, 0, 0])
                                
                            # Flexible accelerometer detection
                            elif any(keyword in sensor_name for keyword in ['accelerometer', 'accel', 'acceleration']):
                                accelerometer = sensor.get("values", [0, 0, 0])
                
            except json.JSONDecodeError as e:
                print(f"Error parsing sensor JSON: {e}")
                print(f"Raw output: {result.stdout}")
        
        # Fallback: try individual sensor calls if combined didn't work
        if not magnetometer or not accelerometer:
            print("Trying individual sensor calls...")
            
            if not magnetometer:
                # Try different magnetometer command variations
                for mag_cmd in ["magnetometer", "magnetic_field", "compass"]:
                    try:
                        mag_result = subprocess.run(["termux-sensor", "-s", mag_cmd, "-n", "1"], 
                                                  capture_output=True, text=True, timeout=3)
                        if mag_result.returncode == 0 and mag_result.stdout.strip():
                            mag_data = json.loads(mag_result.stdout)
                            magnetometer = extract_sensor_values(mag_data, ['magnetometer', 'magnetic', 'compass'])
                            if magnetometer:
                                print(f"Found magnetometer via '{mag_cmd}' command")
                                break
                    except:
                        continue
            
            if not accelerometer:
                # Try different accelerometer command variations
                for acc_cmd in ["accelerometer", "accel", "acceleration"]:
                    try:
                        acc_result = subprocess.run(["termux-sensor", "-s", acc_cmd, "-n", "1"], 
                                                  capture_output=True, text=True, timeout=3)
                        if acc_result.returncode == 0 and acc_result.stdout.strip():
                            acc_data = json.loads(acc_result.stdout)
                            accelerometer = extract_sensor_values(acc_data, ['accelerometer', 'accel', 'acceleration'])
                            if accelerometer:
                                print(f"Found accelerometer via '{acc_cmd}' command")
                                break
                    except:
                        continue
        
        if magnetometer and accelerometer:
            # Validate sensor data (check for reasonable values)
            if is_valid_sensor_data(magnetometer, accelerometer):
                print(f"Magnetometer: {magnetometer}, Accelerometer: {accelerometer}")
                # Calculate compass heading
                heading = calculate_compass_heading(magnetometer, accelerometer)
                if heading is not None:
                    return heading, 15  # Return heading and estimated accuracy (±15 degrees)
            else:
                print("Warning: Sensor data appears invalid, skipping compass calculation")
        else:
            print(f"Missing sensor data - magnetometer: {magnetometer}, accelerometer: {accelerometer}")
            
    except Exception as e:
        print(f"Error getting sensor data: {e}")
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

def capture_and_send_photo(server_ip, phone_id):
    """Capture photo with termux and send to server along with compass data"""
    filename = f"cam_{phone_id}.jpg"
    try:
        print("Capturing photo...")
        
        # Enhanced camera capture with better parameters
        # -c 0: Use back camera (more reliable than front)
        # Add small delay before capture to allow camera to stabilize
        time.sleep(0.5)
        
        # Try capture with enhanced error handling
        result = subprocess.run([
            "termux-camera-photo", 
            "-c", "0",  # Back camera
            filename
        ], capture_output=True, text=True, timeout=15)  # Increased timeout
        
        # Check for capture errors
        if result.returncode != 0:
            print(f"Camera capture failed with return code {result.returncode}")
            if result.stderr:
                print(f"Camera error: {result.stderr}")
            return False
        
        # Verify file was actually created and has content
        if not os.path.exists(filename):
            print("Photo file was not created")
            return False
            
        # Check if file has reasonable size (not empty/corrupt)
        file_size = os.path.getsize(filename)
        if file_size < 1000:  # Less than 1KB suggests corruption
            print(f"Photo file too small ({file_size} bytes), likely corrupt")
            return False
            
        print(f"Photo captured successfully ({file_size} bytes)")
        
        try:
            # Get compass heading
            heading, accuracy = get_sensor_data()
            
            with open(filename, "rb") as f:
                photo_data = f.read()
            
            # Prepare headers
            headers = {
                "Content-Type": "application/octet-stream",
                "X-Phone-ID": phone_id
            }
            
            # Add compass data to headers if available
            if heading is not None:
                headers["X-Camera-Heading"] = str(heading)
                headers["X-Camera-Accuracy"] = str(accuracy)
                print(f"Compass heading: {heading:.1f}° (±{accuracy}°)")
                
            # Send photo to camera endpoint
            response = requests.post(f"http://{server_ip}:{CAMERA_PORT}/upload_photo", 
                                   data=photo_data,
                                   headers=headers,
                                   timeout=10)
            print(f"Sent photo: {response.status_code}")
            return True
        except Exception as e:
            print(f"Failed to send photo: {e}")
            return False
        
    except Exception as e:
        print(f"Error capturing photo: {e}")
        return False
    finally:
        # Always clean up the file
        if os.path.exists(filename):
            os.remove(filename)

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
                    print(f"Available sensors: {sensor_test.stdout}")
                    
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
                        test_heading, test_accuracy = get_sensor_data()
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
    print(f"Camera enabled: {enable_camera}")
    if enable_camera:
        print("\n📷 CAMERA OPTIMIZATION TIPS:")
        print("• Keep phone steady for 1-2 seconds after movement")
        print("• Avoid rapid movement or shaking during capture")
        print("• Ensure good lighting conditions")
        print("• If camera goes black repeatedly, toggle with 'c' key")
        print("• System will automatically skip photos after 3 consecutive failures")
        print("• Photos taken every 6 seconds when active")
    print("Press 'e' to exit, 'c' to toggle camera")
    print("----------------------------------")
    
    # Prepare terminal for key detection if camera enabled
    if enable_camera:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    
    camera_active = enable_camera
    last_photo_time = 0
    photo_interval = 6  # Increased to 6 seconds between photos
    consecutive_failures = 0
    max_failures = 3
    
    try:
        while True:
            # Always send location
            send_location(SERVER_URL, PHONE_ID)
            
            # Handle camera if enabled
            current_time = time.time()
            if camera_active and (current_time - last_photo_time) >= photo_interval:
                print(f"Attempting photo capture (consecutive failures: {consecutive_failures})")
                
                # Skip photo if too many consecutive failures
                if consecutive_failures >= max_failures:
                    print(f"Skipping photo due to {consecutive_failures} consecutive failures")
                    # Wait longer before trying again
                    last_photo_time = current_time + 10  # Extra 10 second delay
                    consecutive_failures = 0  # Reset counter
                else:
                    # Try to capture photo
                    if capture_and_send_photo(server_ip, PHONE_ID):
                        last_photo_time = current_time
                        consecutive_failures = 0  # Reset failure counter on success
                        print("✓ Photo capture successful")
                    else:
                        consecutive_failures += 1
                        last_photo_time = current_time  # Still update time to avoid rapid retries
                        print(f"✗ Photo capture failed (attempt {consecutive_failures}/{max_failures})")
            
            # Check for key presses
            if enable_camera and key_pressed():
                ch = sys.stdin.read(1).lower()
                if ch == 'e':
                    print("Exit key pressed. Exiting...")
                    break
                elif ch == 'c':
                    camera_active = not camera_active
                    consecutive_failures = 0  # Reset failures when toggling camera
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
