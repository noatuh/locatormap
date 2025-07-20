from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import time

app = Flask(__name__)
DATA_FILE = "drawings.json"
PHONES_FILE = "phones.json"
MEASUREMENTS_FILE = "measurements.json"
NOTES_FILE = "notes.json"
CAMERA_DIRECTIONS_FILE = "camera_directions.json"
PHOTOS_DIR = "photos"
CAMERA_PORT = 5051
FRAME_MAPPING_FILE = "frame_mapping.json"

# Phone to frame number mapping (max 5 phones)
phone_frame_mapping = {}
next_frame_number = 1

# Load frame mapping from disk
def load_frame_mapping():
    global phone_frame_mapping, next_frame_number
    if os.path.exists(FRAME_MAPPING_FILE):
        try:
            with open(FRAME_MAPPING_FILE, 'r') as f:
                data = json.load(f)
                phone_frame_mapping = data.get('mapping', {})
                next_frame_number = data.get('next_frame_number', 1)
                print(f"Loaded frame mapping: {phone_frame_mapping}")
        except Exception as e:
            print(f"Error loading frame mapping: {e}")

# Save frame mapping to disk
def save_frame_mapping():
    try:
        data = {
            'mapping': phone_frame_mapping,
            'next_frame_number': next_frame_number
        }
        with open(FRAME_MAPPING_FILE, 'w') as f:
            json.dump(data, f)
        print(f"Saved frame mapping: {phone_frame_mapping}")
    except Exception as e:
        print(f"Error saving frame mapping: {e}")

# Ensure photos directory exists
if not os.path.exists(PHOTOS_DIR):
    os.makedirs(PHOTOS_DIR)

# Load existing frame mapping
load_frame_mapping()

def get_frame_number(phone_id):
    """Get or assign a frame number (1-5) for a phone"""
    global next_frame_number
    
    if phone_id in phone_frame_mapping:
        return phone_frame_mapping[phone_id]
    
    if next_frame_number <= 5:
        frame_num = next_frame_number
        phone_frame_mapping[phone_id] = frame_num
        next_frame_number += 1
        save_frame_mapping()  # Persist the mapping
        print(f"Assigned frame{frame_num}.jpg to phone {phone_id}")
        return frame_num
    else:
        print(f"Warning: Maximum 5 phones supported for camera. Phone {phone_id} not assigned.")
        return None

# Camera server for receiving photos
class PhotoReceiver(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/upload_photo":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                phone_id = self.headers.get('X-Phone-ID', 'unknown')
                heading = self.headers.get('X-Camera-Heading')
                accuracy = self.headers.get('X-Camera-Accuracy')
                
                if content_length > 0:
                    image_data = self.rfile.read(content_length)
                    
                    # Get frame number for this phone
                    frame_num = get_frame_number(phone_id)
                    if frame_num is None:
                        self.send_response(429)  # Too Many Requests
                        self.end_headers()
                        self.wfile.write(b"Maximum 5 phones supported")
                        return
                    
                    # Save as frameX.jpg (overwrites existing)
                    filename = f"frame{frame_num}.jpg"
                    filepath = os.path.join(PHOTOS_DIR, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                    
                    # Save compass data if available
                    if heading is not None:
                        try:
                            save_camera_direction(phone_id, float(heading), 
                                                 float(accuracy) if accuracy else None)
                            print(f"Updated {filename} from {phone_id}: {len(image_data)} bytes, heading: {heading}°")
                        except ValueError:
                            print(f"Updated {filename} from {phone_id}: {len(image_data)} bytes, invalid heading data")
                    else:
                        print(f"Updated {filename} from {phone_id}: {len(image_data)} bytes")
                    
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(f"Photo saved as {filename}".encode())
                else:
                    self.send_response(400)
                    self.end_headers()
            except Exception as e:
                print(f"Error receiving photo: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == "/upload_photo_json":
            # JSON-based photo upload (alternative method)
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    json_data = self.rfile.read(content_length).decode('utf-8')
                    data = json.loads(json_data)
                    
                    phone_id = data.get('phone_id', 'unknown')
                    photo_b64 = data.get('photo_data', '')
                    heading = data.get('heading')
                    accuracy = data.get('accuracy')
                    
                    if photo_b64:
                        # Decode base64 photo
                        import base64
                        image_data = base64.b64decode(photo_b64)
                        
                        # Get frame number for this phone
                        frame_num = get_frame_number(phone_id)
                        if frame_num is None:
                            self.send_response(429)
                            self.end_headers()
                            self.wfile.write(b'{"error": "Maximum 5 phones supported"}')
                            return
                        
                        # Save as frameX.jpg
                        filename = f"frame{frame_num}.jpg"
                        filepath = os.path.join(PHOTOS_DIR, filename)
                        
                        with open(filepath, "wb") as f:
                            f.write(image_data)
                        
                        # Save compass data if available
                        if heading is not None:
                            try:
                                save_camera_direction(phone_id, float(heading), 
                                                     float(accuracy) if accuracy else None)
                                print(f"JSON: Updated {filename} from {phone_id}: {len(image_data)} bytes, heading: {heading}°")
                            except ValueError:
                                print(f"JSON: Updated {filename} from {phone_id}: {len(image_data)} bytes, invalid heading")
                        else:
                            print(f"JSON: Updated {filename} from {phone_id}: {len(image_data)} bytes")
                        
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(f'{{"status": "success", "filename": "{filename}"}}'.encode())
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b'{"error": "No photo data"}')
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"error": "No content"}')
            except Exception as e:
                print(f"Error receiving JSON photo: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'{{"error": "{str(e)}"}}'.encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def run_camera_server():
    """Run the camera server on a separate thread"""
    try:
        server = HTTPServer(("0.0.0.0", CAMERA_PORT), PhotoReceiver)
        print(f"Camera server listening on port {CAMERA_PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"Failed to start camera server: {e}")

def save_camera_direction(phone_id, heading, accuracy=None):
    """Save camera direction data for a phone"""
    directions = {}
    if os.path.exists(CAMERA_DIRECTIONS_FILE):
        try:
            with open(CAMERA_DIRECTIONS_FILE, 'r') as f:
                directions = json.load(f)
        except:
            directions = {}
    
    directions[phone_id] = {
        'heading': heading,
        'accuracy': accuracy,
        'timestamp': time.time()
    }
    
    with open(CAMERA_DIRECTIONS_FILE, 'w') as f:
        json.dump(directions, f)

def load_camera_directions():
    """Load all camera direction data"""
    if os.path.exists(CAMERA_DIRECTIONS_FILE):
        try:
            with open(CAMERA_DIRECTIONS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/save", methods=["POST"])
def save():
    data = request.get_json()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)
    return jsonify({"status": "saved"})

@app.route("/load", methods=["GET"])
def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route("/save_phones", methods=["POST"])
def save_phones():
    data = request.get_json()
    with open(PHONES_FILE, "w") as f:
        json.dump(data, f)
    return jsonify({"status": "phones saved"})

@app.route("/load_phones", methods=["GET"])
def load_phones():
    if os.path.exists(PHONES_FILE):
        with open(PHONES_FILE, "r") as f:
            return jsonify(json.load(f))
    return jsonify({})

@app.route("/update_location", methods=["POST"])
def update_location():
    data = request.get_json()
    phone_id = data.get("id")
    lat = data.get("lat")
    lng = data.get("lng")

    if phone_id and lat is not None and lng is not None:
        phones = {}
        if os.path.exists(PHONES_FILE):
            with open(PHONES_FILE, "r") as f:
                phones = json.load(f)

        phones[phone_id] = {"lat": lat, "lng": lng}

        with open(PHONES_FILE, "w") as f:
            json.dump(phones, f)

        return jsonify({"status": "location updated"})
    
    return jsonify({"error": "missing data"}), 400

@app.route("/save_poi", methods=["POST"])
def save_poi():
    poi_data = request.get_json()
    poi_id = poi_data.get("id")
    
    if not os.path.exists("pois.json"):
        with open("pois.json", "w") as f:
            json.dump([], f)
    
    # Load existing POIs
    with open("pois.json", "r") as f:
        try:
            pois = json.load(f)
        except json.JSONDecodeError:
            pois = []
    
    # Update or add POI
    found = False
    for i, poi in enumerate(pois):
        if poi.get("id") == poi_id:
            pois[i] = poi_data
            found = True
            break
    
    if not found:
        pois.append(poi_data)
    
    # Save back to file
    with open("pois.json", "w") as f:
        json.dump(pois, f)
    
    return jsonify({"status": "saved", "id": poi_id})

@app.route("/load_pois", methods=["GET"])
def load_pois():
    if not os.path.exists("pois.json"):
        return jsonify([])
    
    with open("pois.json", "r") as f:
        try:
            pois = json.load(f)
            return jsonify(pois)
        except json.JSONDecodeError:
            return jsonify([])

@app.route("/delete_poi", methods=["POST"])
def delete_poi():
    poi_id = request.get_json().get("id")
    
    if os.path.exists("pois.json"):
        with open("pois.json", "r") as f:
            try:
                pois = json.load(f)
                pois = [poi for poi in pois if poi.get("id") != poi_id]
                
                with open("pois.json", "w") as f:
                    json.dump(pois, f)
                
                return jsonify({"status": "deleted"})
            except json.JSONDecodeError:
                return jsonify({"error": "Failed to parse POIs file"}), 500
    
    return jsonify({"error": "No POIs found"}), 404

@app.route("/save_measurement", methods=["POST"])
def save_measurement():
    measurement = request.get_json()
    
    if not os.path.exists(MEASUREMENTS_FILE):
        with open(MEASUREMENTS_FILE, "w") as f:
            json.dump([], f)
    
    # Load existing measurements
    with open(MEASUREMENTS_FILE, "r") as f:
        try:
            measurements = json.load(f)
        except json.JSONDecodeError:
            measurements = []
    
    # Update or add measurement
    found = False
    for i, m in enumerate(measurements):
        if m.get("id") == measurement.get("id"):
            measurements[i] = measurement
            found = True
            break
    
    if not found:
        measurements.append(measurement)
    
    # Save back to file
    with open(MEASUREMENTS_FILE, "w") as f:
        json.dump(measurements, f)
    
    return jsonify({"status": "saved", "id": measurement.get("id")})

@app.route("/load_measurements", methods=["GET"])
def load_measurements():
    if not os.path.exists(MEASUREMENTS_FILE):
        return jsonify([])
    
    with open(MEASUREMENTS_FILE, "r") as f:
        try:
            measurements = json.load(f)
            return jsonify(measurements)
        except json.JSONDecodeError:
            return jsonify([])

@app.route("/clear_measurements", methods=["POST"])
def clear_measurements():
    with open(MEASUREMENTS_FILE, "w") as f:
        json.dump([], f)
    return jsonify({"status": "cleared"})

@app.route("/clear_pois", methods=["POST"])
def clear_pois():
    with open("pois.json", "w") as f:
        json.dump([], f)
    return jsonify({"status": "cleared"})

@app.route("/save_note", methods=["POST"])
def save_note():
    note_data = request.get_json()
    note_id = note_data.get("id")
    
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "w") as f:
            json.dump([], f)
    
    # Load existing notes
    with open(NOTES_FILE, "r") as f:
        try:
            notes = json.load(f)
        except json.JSONDecodeError:
            notes = []
    
    # Update or add note
    found = False
    for i, note in enumerate(notes):
        if note.get("id") == note_id:
            notes[i] = note_data
            found = True
            break
    
    if not found:
        notes.append(note_data)
    
    # Save back to file
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f)
    
    return jsonify({"status": "saved", "id": note_id})

@app.route("/load_notes", methods=["GET"])
def load_notes():
    if not os.path.exists(NOTES_FILE):
        return jsonify([])
    
    with open(NOTES_FILE, "r") as f:
        try:
            notes = json.load(f)
            return jsonify(notes)
        except json.JSONDecodeError:
            return jsonify([])

@app.route("/delete_note", methods=["POST"])
def delete_note():
    note_id = request.get_json().get("id")
    
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r") as f:
            try:
                notes = json.load(f)
                notes = [note for note in notes if note.get("id") != note_id]
                
                with open(NOTES_FILE, "w") as f:
                    json.dump(notes, f)
                
                return jsonify({"status": "deleted"})
            except json.JSONDecodeError:
                return jsonify({"error": "Failed to parse notes file"}), 500
    
    return jsonify({"error": "No notes found"}), 404

@app.route("/clear_notes", methods=["POST"])
def clear_notes():
    with open(NOTES_FILE, "w") as f:
        json.dump([], f)
    return jsonify({"status": "cleared"})

@app.route("/get_photo/<phone_id>")
def get_photo(phone_id):
    """Get the photo from a specific phone by finding its frame number"""
    # Auto-assign frame number if phone exists but doesn't have one
    if phone_id not in phone_frame_mapping:
        # Check if this phone is being tracked (exists in phones.json)
        if os.path.exists(PHONES_FILE):
            try:
                with open(PHONES_FILE, 'r') as f:
                    phones = json.load(f)
                if phone_id in phones:
                    # Assign frame number to existing tracked phone
                    frame_num = get_frame_number(phone_id)
                    if frame_num is None:
                        return jsonify({"error": "Maximum 5 phones supported for camera"}), 429
            except Exception as e:
                print(f"Error checking phones file: {e}")
    
    if phone_id in phone_frame_mapping:
        frame_num = phone_frame_mapping[phone_id]
        photo_path = os.path.join(PHOTOS_DIR, f"frame{frame_num}.jpg")
        if os.path.exists(photo_path):
            return send_file(photo_path, mimetype='image/jpeg')
        else:
            return jsonify({"error": f"Photo file frame{frame_num}.jpg not found for {phone_id}"}), 404
    
    return jsonify({"error": "No photo found for this phone"}), 404

@app.route("/get_camera_direction/<phone_id>")
def get_camera_direction(phone_id):
    """Get the camera direction data for a specific phone"""
    directions = load_camera_directions()
    
    if phone_id in directions:
        direction_data = directions[phone_id]
        # Check if data is recent (within last 30 seconds)
        if time.time() - direction_data['timestamp'] < 30:
            return jsonify({
                'heading': direction_data['heading'],
                'accuracy': direction_data.get('accuracy'),
                'timestamp': direction_data['timestamp']
            })
        else:
            return jsonify({"error": "Direction data too old"}), 404
    
    return jsonify({"error": "No direction data found for this phone"}), 404

@app.route("/get_frame/<int:frame_num>")
def get_frame(frame_num):
    """Get a photo by frame number (1-5)"""
    if 1 <= frame_num <= 5:
        photo_path = os.path.join(PHOTOS_DIR, f"frame{frame_num}.jpg")
        if os.path.exists(photo_path):
            return send_file(photo_path, mimetype='image/jpeg')
    
    return jsonify({"error": "Frame not found"}), 404

@app.route("/list_photos")
def list_photos():
    """Get list of all available photos with frame mapping"""
    if not os.path.exists(PHOTOS_DIR):
        return jsonify({})
    
    photos = {}
    for phone_id, frame_num in phone_frame_mapping.items():
        filename = f"frame{frame_num}.jpg"
        file_path = os.path.join(PHOTOS_DIR, filename)
        
        if os.path.exists(file_path):
            # Get file modification time
            mod_time = os.path.getmtime(file_path)
            
            photos[phone_id] = {
                'frame_number': frame_num,
                'filename': filename,
                'last_updated': mod_time,
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
            }
    
    return jsonify(photos)

@app.route("/get_phone_mapping")
def get_phone_mapping():
    """Get the phone to frame number mapping"""
    return jsonify(phone_frame_mapping)

if __name__ == "__main__":
    # Start camera server in background thread
    camera_thread = threading.Thread(target=run_camera_server, daemon=True)
    camera_thread.start()
    
    print("Starting main server on port 5050...")
    print("Camera server running on port 5051...")
    app.run(debug=True, host="0.0.0.0", port=5050)
