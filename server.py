from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import os
import requests
import time

# Load config
with open('config.json') as config_file:
    config = json.load(config_file)
OPENWEATHERMAP_API_KEY = config.get('openweathermap_api_key')

app = Flask(__name__)
DATA_FILE = "drawings.json"
PHONES_FILE = "phones.json"
MEASUREMENTS_FILE = "measurements.json"
NOTES_FILE = "notes.json"
RADIO_FILE = "radio_frequencies.json"

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/android.png')
def android_icon():
    # Serve the Android homescreen icon
    return send_from_directory(app.root_path + '/templates', 'android.png', mimetype='image/png')

@app.route('/manifest.json')
def manifest():
    # Serve PWA manifest
    return send_from_directory(app.root_path + '/templates', 'manifest.json', mimetype='application/json')

@app.route("/minimap")
def minimap():
    return render_template("minimap.html")

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
    heading = data.get("heading")
    alt = data.get("alt")

    if not phone_id or lat is None or lng is None:
        return jsonify({"status": "error", "message": "Missing required data"}), 400

    if os.path.exists(PHONES_FILE):
        with open(PHONES_FILE, "r") as f:
            try:
                phones = json.load(f)
            except json.JSONDecodeError:
                phones = {}
    else:
        phones = {}

    phone_data = phones.get(phone_id, {})
    phone_data["lat"] = lat
    phone_data["lng"] = lng
    phone_data["alt"] = alt # Save altitude

    # Only update heading if it's provided
    if heading is not None:
        phone_data["heading"] = heading
    
    # Persist last known heading if new update doesn't have one
    elif "heading" in phones.get(phone_id, {}):
        phone_data["heading"] = phones[phone_id]["heading"]


    phones[phone_id] = phone_data

    # Add a timestamp to know when the location was last updated
    phone_data["timestamp"] = time.time()

    with open(PHONES_FILE, "w") as f:
        json.dump(phones, f)

    return jsonify({"status": "updated"})


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

@app.route("/get_route", methods=["POST"])
def get_route():
    """Get routing directions between two points using multiple routing services"""
    data = request.get_json()
    start_lat = data.get("start_lat")
    start_lng = data.get("start_lng")
    end_lat = data.get("end_lat")
    end_lng = data.get("end_lng")
    mode = data.get("mode", "walking")  # walking, driving, cycling
    
    if not all([start_lat, start_lng, end_lat, end_lng]):
        return jsonify({"error": "Missing coordinates"}), 400
    
    # Try multiple routing services in order of preference
    route_data = None
    service_used = None
    
    # 1. Try MapBox Directions API (free tier available)
    try:
        mapbox_token = "YOUR_MAPBOX_TOKEN_HERE"  # Replace with your MapBox token
        if mapbox_token != "YOUR_MAPBOX_TOKEN_HERE":
            profile = "walking" if mode == "walking" else "driving" if mode == "driving" else "cycling"
            url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{start_lng},{start_lat};{end_lng},{end_lat}"
            params = {
                "access_token": mapbox_token,
                "geometries": "geojson",
                "overview": "full",
                "steps": "true"
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                mapbox_data = response.json()
                if mapbox_data.get("routes"):
                    route = mapbox_data["routes"][0]
                    route_data = {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "geometry": route["geometry"],
                            "properties": {
                                "distance": route.get("distance", 0),
                                "duration": route.get("duration", 0),
                                "steps": route.get("legs", [{}])[0].get("steps", []),
                                "service": "mapbox"
                            }
                        }]
                    }
                    service_used = "MapBox"
    except Exception as e:
        print(f"MapBox routing failed: {e}")
    
    # 2. Try OSRM (Open Source Routing Machine) - free public instance
    if not route_data:
        try:
            profile = "foot" if mode == "walking" else "car" if mode == "driving" else "bike"
            url = f"http://router.project-osrm.org/route/v1/{profile}/{start_lng},{start_lat};{end_lng},{end_lat}"
            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "true"
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                osrm_data = response.json()
                if osrm_data.get("routes"):
                    route = osrm_data["routes"][0]
                    route_data = {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "geometry": route["geometry"],
                            "properties": {
                                "distance": route.get("distance", 0),
                                "duration": route.get("duration", 0),
                                "steps": route.get("legs", [{}])[0].get("steps", []),
                                "service": "osrm"
                            }
                        }]
                    }
                    service_used = "OSRM"
        except Exception as e:
            print(f"OSRM routing failed: {e}")
    
    # 3. Try OpenRouteService as backup
    if not route_data:
        try:
            ors_api_key = "YOUR_ORS_API_KEY_HERE"  # Get free key from openrouteservice.org
            if ors_api_key != "YOUR_ORS_API_KEY_HERE":
                profile = "foot-walking" if mode == "walking" else "driving-car" if mode == "driving" else "cycling-regular"
                url = f"https://api.openrouteservice.org/v2/directions/{profile}"
                headers = {
                    'Accept': 'application/json, application/geo+json',
                    'Authorization': ors_api_key,
                    'Content-Type': 'application/json'
                }
                body = {
                    "coordinates": [[start_lng, start_lat], [end_lng, end_lat]],
                    "format": "geojson",
                    "instructions": True
                }
                response = requests.post(url, json=body, headers=headers, timeout=10)
                if response.status_code == 200:
                    route_data = response.json()
                    if route_data.get("features"):
                        route_data["features"][0]["properties"]["service"] = "openrouteservice"
                        service_used = "OpenRouteService"
        except Exception as e:
            print(f"OpenRouteService routing failed: {e}")
    
    # 4. Fallback: Use GraphHopper public API
    if not route_data:
        try:
            vehicle = "foot" if mode == "walking" else "car" if mode == "driving" else "bike"
            url = "https://graphhopper.com/api/1/route"
            params = {
                "point": [f"{start_lat},{start_lng}", f"{end_lat},{end_lng}"],
                "vehicle": vehicle,
                "locale": "en",
                "instructions": "true",
                "calc_points": "true",
                "debug": "false",
                "elevation": "false",
                "points_encoded": "false"
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                gh_data = response.json()
                if gh_data.get("paths"):
                    path = gh_data["paths"][0]
                    coordinates = [[point[1], point[0]] for point in path["points"]["coordinates"]]
                    route_data = {
                        "type": "FeatureCollection",
                        "features": [{
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": coordinates
                            },
                            "properties": {
                                "distance": path.get("distance", 0),
                                "time": path.get("time", 0),
                                "instructions": path.get("instructions", []),
                                "service": "graphhopper"
                            }
                        }]
                    }
                    service_used = "GraphHopper"
        except Exception as e:
            print(f"GraphHopper routing failed: {e}")
    
    # Final fallback: straight line
    if not route_data:
        route_data = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[start_lng, start_lat], [end_lng, end_lat]]
                },
                "properties": {
                    "distance": calculate_distance(start_lat, start_lng, end_lat, end_lng),
                    "fallback": True,
                    "service": "fallback"
                }
            }]
        }
        service_used = "Fallback (straight line)"
    
    # Add service info to response
    if route_data and route_data.get("features"):
        route_data["service_used"] = service_used
    
    return jsonify(route_data)

def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two points using Haversine formula"""
    import math
    
    R = 6371000  # Earth's radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

@app.route("/save_radio_frequencies", methods=["POST"])
def save_radio_frequencies():
    """Save all radio frequencies at once"""
    frequencies = request.get_json()
    
    with open(RADIO_FILE, "w") as f:
        json.dump(frequencies, f)
    
    return jsonify({"status": "saved"})

@app.route("/load_radio_frequencies", methods=["GET"])
def load_radio_frequencies():
    """Load all radio frequencies"""
    if not os.path.exists(RADIO_FILE):
        # Initialize with empty channels 1-40
        default_frequencies = {str(i): "" for i in range(1, 41)}
        return jsonify(default_frequencies)
    
    with open(RADIO_FILE, "r") as f:
        try:
            frequencies = json.load(f)
            # Ensure all channels 1-40 exist
            for i in range(1, 41):
                if str(i) not in frequencies:
                    frequencies[str(i)] = ""
            return jsonify(frequencies)
        except json.JSONDecodeError:
            # Return default if file is corrupted
            default_frequencies = {str(i): "" for i in range(1, 41)}
            return jsonify(default_frequencies)

@app.route("/clear_radio_frequencies", methods=["POST"])
def clear_radio_frequencies():
    """Clear all radio frequencies"""
    default_frequencies = {str(i): "" for i in range(1, 41)}
    with open(RADIO_FILE, "w") as f:
        json.dump(default_frequencies, f)
    return jsonify({"status": "cleared"})

@app.route("/save_current_route", methods=["POST"])
def save_current_route():
    """Save the current active navigation route"""
    try:
        route_data = request.get_json()
        with open("current_route.json", "w") as f:
            json.dump(route_data, f)
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/load_current_route", methods=["GET"])
def load_current_route():
    """Load the current active navigation route"""
    try:
        if os.path.exists("current_route.json"):
            with open("current_route.json", "r") as f:
                route_data = json.load(f)
            return jsonify(route_data)
        return jsonify(None)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear_current_route", methods=["POST"])
def clear_current_route():
    """Clear the current active navigation route"""
    try:
        if os.path.exists("current_route.json"):
            os.remove("current_route.json")
        return jsonify({"status": "cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Starting main server on port 5050...")
    app.run(debug=True, host="0.0.0.0", port=5050)
