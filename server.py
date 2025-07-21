from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)
DATA_FILE = "drawings.json"
PHONES_FILE = "phones.json"
MEASUREMENTS_FILE = "measurements.json"
NOTES_FILE = "notes.json"

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

if __name__ == "__main__":
    print("Starting main server on port 5050...")
    app.run(debug=True, host="0.0.0.0", port=5050)
