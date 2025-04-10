from flask import Flask, jsonify
from flask_cors import CORS  # ⬅️ Add this
import subprocess
import json

app = Flask(__name__)
CORS(app)  # ⬅️ Enable CORS globally

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

@app.route('/location')
def location():
    lat, lon = get_gps_coords()
    if lat is not None and lon is not None:
        return jsonify({"lat": lat, "lng": lon})
    else:
        return jsonify({"error": "Unable to get GPS data"}), 500

if __name__ == "__main__":
    print("GPS server running at http://192.168.1.89:5000/location")
    app.run(host="0.0.0.0", port=5000)
