# Locator Map

A web-based mapping application to track multiple phones, draw on the map, measure distances, manage points of interest (POIs), and get turn-by-turn navigation from any tracked phone.

## Features

- **Multi-Phone Tracking**: Track and display live locations and headings for multiple devices.
- **Drawing Tools**: Draw freehand lines on the map and save/load via server.
- **Distance Measurement**: Measure straight-line distances with metric and imperial units.
- **Points of Interest (POIs)**: Add, delete, and navigate to custom POIs with colored markers.
- **Notes**: Add timestamped notes on the map, view and delete notes.
- **Toggling Controls**: Show/hide side panels, phone labels, grid lines, and direction arrows.
- **Grid Overlay**: Display a global-aligned grid with unique cell references.
- **Navigation**:  
  - Set any tracked phone as the navigation origin.  
  - Click to set destinations and choose between walking 🚶, driving 🚗, or cycling 🚴 modes.  
  - View route summary, distance, estimated duration, and turn-by-turn instructions.  
- Navigate directly to any POI via its popup.

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/noatuh/locatormap.git
   ```
2. Navigate into the project directory:

   ```bash
   cd locatormap
   ```
3. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Obtain an OpenRouteService API key (optional for street routing):

   - Sign up at [OpenRouteService](https://openrouteservice.org/) and copy your API key.
   - Open `server.py` and replace `YOUR_ORS_API_KEY_HERE` with your key.

## Running the Application

- Windows (batch scripts):

  ```bash
  startserver.bat
  startsite.bat
  ```

- Linux/macOS (shell scripts):

  ```bash
  ./linux/startserver.sh
  ./linux/startsite.sh
  ```

The server runs on `http://localhost:5000` by default. Open the site in your browser and enter the password (`1234` by default) to access the map.

## Navigation Usage

### Setting Up Navigation Origin

1. Open the navigation panel via the **Navigation** button.

2. In the tracked phones list, click **Nav From** (📱) next to a device to set it as the origin.

### Calculating Routes

1. Click **Set Destination** and then click a point on the map.
   
2. Choose your transportation mode.
3. View the route on the map, with summary and directions in the navigation panel.
4. To clear the route, click **Clear Route**.

### POI Navigation
Click **Navigate Here** in any POI popup to automatically calculate a route.

## Additional Information
- **Drawing Persistence**: All drawings, measurements, phones, POIs, and notes are saved to JSON files (e.g., `drawings.json`, `phones.json`, `pois.json`, `notes.json`, `measurements.json`) on the server.
- **Customization**: Edit `index.html` and embedded CSS/JavaScript in the `templates/` folder to tweak UI and behavior.
- **Security**: The app uses a simple password overlay. Change the password in `index.html` if needed.

## License
MIT License.

---  
*Generated README combining project overview and navigation features.*
