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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
