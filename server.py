from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)
DATA_FILE = "drawings.json"
PHONES_FILE = "phones.json"

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
