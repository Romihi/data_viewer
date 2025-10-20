# Donkeycar Data Viewer

A web-based viewer application for visualizing Donkeycar data in real-time with statistics and timeline views.

## Features

- **Folder Selection**: Browse and select Donkeycar data folders
- **Timeline Visualization**: Interactive timeline view of all numerical data
- **Multi-Image Support**: Display multiple camera and sensor images simultaneously
- **Real-time Playback**: Playback recorded data with adjustable speed
- **Statistics**: Automatic calculation of statistics for all numerical data
- **Responsive Design**: Works on desktop and mobile devices

## Installation

1. Navigate to the viewer directory:
```bash
cd /home/pi/projects/mycar_donkey5/donkeycar_viewer
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the Flask server:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

Or from a remote PC, use your Raspberry Pi's IP address:
```
http://[raspberry-pi-ip]:5000
```

3. Select a data folder that contains Donkeycar recordings

## Data Structure

The viewer expects the following data structure:
```
data_folder/
├── data/
│   ├── catalog_0.catalog
│   ├── catalog_1.catalog
│   ├── ...
│   ├── manifest.json
│   └── images/
│       ├── 0_cam_image_array_.jpg
│       ├── 1_cam_image_array_.jpg
│       └── ...
```

## Customization

The application uses a modular design that makes it easy to customize:

- **Frontend**: Edit `templates/index.html` to modify the UI
- **API**: Modify `app.py` to add new endpoints
- **Data Processing**: Update `data_loader.py` to add new data processing features

## API Endpoints

- `GET /api/folders` - List available data folders
- `POST /api/load_data` - Load data from selected folder
- `GET /api/data` - Get paginated record data
- `GET /api/statistics` - Get statistics for numerical data
- `GET /api/image/<path>` - Serve image files
- `GET /api/timeline` - Get timeline data for visualization