# Donkeycar Data Viewer

A comprehensive web-based viewer application for visualizing and managing Donkeycar training data with advanced timeline analysis, statistics, and data curation tools.

![Donkeycar Data Viewer](https://img.shields.io/badge/Python-3.7+-blue.svg) ![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [User Guide](#user-guide)
- [Data Structure](#data-structure)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Customization](#customization)

## ✨ Features

### Data Management
- **Folder Browser**: Intuitive file system navigation to select Donkeycar data folders
- **Session Filtering**: Filter data by recording session
- **Delete Index Management**: Mark and manage deleted data indexes with range selection
- **Auto-detection**: Automatically detects folders containing Donkeycar catalog files

### Visualization
- **Timeline Chart**: Interactive time-series visualization with Chart.js
  - Zoom and pan support
  - Visual markers for deleted indexes
  - Multi-key data plotting
- **Histogram**: Real-time histogram of current data distribution
- **Multi-Image Display**: View multiple camera feeds and sensor images simultaneously
  - Toggle visibility for individual image streams
  - Automatic image preloading for smooth playback
  - Responsive layout within panel

### Data Processing
- **Normalization**: Normalize data to -1~1 range for comparison
- **Smoothing Algorithms**:
  - Moving Average (MA): Window sizes 3, 5, 10, 20
  - Exponential Moving Average (EMA): Alpha values 0.1, 0.3, 0.5
  - Interactive tooltips with mathematical formulas

### Playback Controls
- **Forward/Reverse Playback**: Full bidirectional playback support
- **Step Controls**: Frame-by-frame navigation (⏮ ⏭)
- **Variable Speed**: 1x to 10x playback speed
- **Index Slider**: Direct navigation to any data point

### Statistics Panel
- **Real-time Statistics**: Automatic calculation for all numerical keys
  - Count, Mean, Standard Deviation
  - Min, Max, Median
  - Q1, Q3 (Quartiles)
- **Filterable by Session**: Statistics update based on selected session

### UI/UX
- **Eye-friendly Design**: Warm beige color palette to reduce eye strain
- **Resizable Panels**: Adjustable panel heights for customized workspace
- **Responsive Layout**: Adapts to different screen sizes
- **Current Record View**: Displays all data fields for current index

## 🚀 Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Edge, Safari)

### Dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

**requirements.txt**:
```
flask>=2.0.0
flask-cors>=3.0.0
numpy>=1.19.0
```

## 🎯 Quick Start

### 1. Start the Application

```bash
python app.py
```

Or use the provided shell script (Linux/Mac):
```bash
chmod +x run.sh
./run.sh
```

### 2. Access the Web Interface

**Local access**:
```
http://localhost:5000
```

**Remote access** (from another device on the same network):
```
http://[your-ip-address]:5000
```

For Raspberry Pi users:
```bash
# Find your IP address
hostname -I
```

### 3. Load Data

1. Click **"Select Data Folder"** button
2. Navigate to your Donkeycar data folder (contains `data/` subdirectory)
3. Click **"Load Data"** to load the selected folder
4. Data will be loaded and displayed across all panels

## 📖 User Guide

### Panel Layout

The application features four resizable panels:

1. **Images Panel** (Top): Camera and sensor image display
2. **Timeline Panel**: Time-series chart visualization
3. **Statistics Panel**: Numerical data statistics
4. **Histogram Panel** (Bottom): Data distribution visualization

**Resizing Panels**: Drag the horizontal bars between panels to adjust heights.

### Timeline Controls

**Data Selection**:
- Use the dropdown to select which data key to visualize
- Multiple numerical keys available (e.g., `user/throttle`, `user/angle`)

**Normalization**:
- Click **"正規化"** button to normalize data to -1~1 range
- Useful for comparing different scale data on same chart

**Smoothing**:
- Select smoothing algorithm from dropdown:
  - **なし** (None): Raw data
  - **MA-3, MA-5, MA-10, MA-20**: Moving Average with window size
  - **EMA-0.1, EMA-0.3, EMA-0.5**: Exponential Moving Average with alpha
- Hover over options to see mathematical formulas

**Chart Interaction**:
- **Zoom**: Scroll wheel or pinch gesture
- **Pan**: Click and drag
- **Reset Zoom**: Double-click chart

### Playback Controls

Located below the Timeline panel:

- **⏮ Step Backward**: Go to previous frame
- **⏪ Play Reverse**: Play backward at selected speed
- **⏩ Play Forward**: Play forward at selected speed
- **⏭ Step Forward**: Go to next frame
- **Speed Selector**: 1x, 2x, 5x, 10x playback speed

**Index Slider**: Drag to navigate directly to any data point.

### Delete Index Management

Mark ranges of data for deletion (useful for removing bad training data):

1. **Set Start Index**:
   - Enter value manually or click **"現在"** button to use current index
2. **Set End Index**:
   - Enter value manually or click **"現在"** button to use current index
3. **Apply Deletion**:
   - Click **"削除設定"** to mark range as deleted
4. **Clear Deletion**:
   - Click **"削除クリア"** to unmark range

**Notes**:
- Default range is 0 to maximum index
- Deleted indexes are saved to `manifest.json`
- Deleted ranges shown as red boxes on Timeline chart
- Deleted data is marked but not physically removed

### Image Display Controls

**Show/Hide Images**:
- Click image key names to toggle visibility
- **"すべて"** button: Toggle all images on/off
- Images automatically scale to fit panel

### Session Filtering

If your data contains multiple recording sessions:
- Use **Session** dropdown to filter by session ID
- All panels update to show only selected session data

## 📁 Data Structure

### Expected Folder Structure

```
data_folder/
├── data/
│   ├── catalog_0.catalog       # Data records (JSON lines)
│   ├── catalog_1.catalog
│   ├── catalog_N.catalog
│   ├── manifest.json           # Metadata and configuration
│   └── images/
│       ├── 0_cam_image_array_.jpg
│       ├── 1_cam_image_array_.jpg
│       └── ...
```

### Manifest File Format

The `manifest.json` file contains 5 lines:

1. **Line 1**: Data keys (JSON array)
2. **Line 2**: Data types (JSON array)
3. **Line 3**: Empty line
4. **Line 4**: Metadata (JSON object)
5. **Line 5**: Catalog manifest (JSON object)
   ```json
   {
     "max_len": 1000,
     "deleted_indexes": [10, 11, 12, 150, 151]
   }
   ```

### Catalog Files

Each catalog file contains JSON lines with records:

```json
{"_index": 0, "_session_id": "session_001", "_timestamp_ms": 1234567890, "user/throttle": 0.5, "user/angle": -0.1, "cam/image_array": "images/0_cam_image_array_.jpg"}
{"_index": 1, "_session_id": "session_001", "_timestamp_ms": 1234567990, "user/throttle": 0.6, "user/angle": 0.0, "cam/image_array": "images/1_cam_image_array_.jpg"}
```

**Special Keys**:
- `_index`: Local index within catalog (0-999 for max_len=1000)
- `_absolute_index`: Global index across all catalogs (calculated as `catalog_num * max_len + _index`)
- `_session_id`: Recording session identifier
- `_timestamp_ms`: Timestamp in milliseconds
- `_is_deleted`: Added at runtime to mark deleted records

## 🔌 API Reference

### Browse Directory

```http
GET /api/browse?path=/path/to/directory
```

**Response**:
```json
{
  "current_path": "/path/to/directory",
  "items": [
    {
      "name": "folder_name",
      "path": "/full/path",
      "type": "directory",
      "is_data_folder": true
    }
  ]
}
```

### Load Data

```http
POST /api/load_data
Content-Type: application/json

{
  "folder_path": "/path/to/data_folder"
}
```

**Response**:
```json
{
  "success": true,
  "info": {
    "total_records": 5000,
    "sessions": ["session_001", "session_002"],
    "data_keys": ["user/throttle", "user/angle", ...],
    "timestamp_range": {
      "min": 1234567890,
      "max": 1234657890,
      "duration_ms": 90000
    },
    "deleted_indexes": [10, 11, 12]
  }
}
```

### Get Data Records

```http
GET /api/data?start=0&end=100&session=session_001
```

**Parameters**:
- `start`: Start index (default: 0)
- `end`: End index (optional, default: all)
- `session`: Session ID filter (optional)

**Response**:
```json
{
  "records": [...],
  "total": 5000
}
```

### Get Statistics

```http
GET /api/statistics?key=user/throttle&session=session_001
```

**Response**:
```json
{
  "user/throttle": {
    "count": 5000,
    "mean": 0.45,
    "std": 0.15,
    "min": 0.0,
    "max": 1.0,
    "median": 0.5,
    "q1": 0.3,
    "q3": 0.6
  }
}
```

### Get Timeline Data

```http
GET /api/timeline?key=user/throttle&session=session_001
```

**Response**:
```json
{
  "key": "user/throttle",
  "data": [
    {"timestamp": 1234567890, "value": 0.5, "index": 0},
    {"timestamp": 1234567990, "value": 0.6, "index": 1}
  ]
}
```

### Update Delete Indexes

```http
POST /api/delete_indexes
Content-Type: application/json

{
  "start_idx": 100,
  "end_idx": 200
}
```

**Response**:
```json
{
  "success": true,
  "deleted_indexes": [10, 11, 12, 100, 101, ..., 200],
  "count": 104
}
```

### Clear Delete Indexes

```http
POST /api/clear_delete_indexes
Content-Type: application/json

{
  "start_idx": 100,
  "end_idx": 200
}
```

**Response**:
```json
{
  "success": true,
  "deleted_indexes": [10, 11, 12],
  "count": 3
}
```

### Get Image

```http
GET /api/image/<image_path>
```

Returns JPEG image file.

## 🏗 Architecture

### Technology Stack

**Backend**:
- Flask 2.0+ (Python web framework)
- Flask-CORS (Cross-origin resource sharing)
- NumPy (Statistical calculations)

**Frontend**:
- React 18 (UI framework, via Babel standalone)
- Chart.js 4.4 (Timeline and histogram charts)
- chartjs-plugin-annotation (Deleted index markers)
- chartjs-plugin-zoom (Interactive zooming)
- Tailwind CSS (Styling framework)

### File Structure

```
data_viewer/
├── app.py                  # Flask application and API endpoints
├── data_loader.py          # Data loading and processing logic
├── requirements.txt        # Python dependencies
├── run.sh                  # Startup script
├── templates/
│   └── index.html         # Single-page React application
└── README.md              # This file
```

### Data Flow

1. **User selects folder** → Browser sends path to `/api/browse`
2. **User loads data** → POST to `/api/load_data` → `DonkeycarDataLoader` loads catalogs
3. **Records loaded** → Stored in memory with indexes mapped
4. **User navigates** → GET `/api/data` with pagination
5. **Timeline renders** → GET `/api/timeline` with selected key
6. **Statistics update** → GET `/api/statistics` for numerical keys
7. **User marks deletions** → POST `/api/delete_indexes` → Updates `manifest.json` line 5

### Performance Optimizations

- **Map-based lookups**: O(n) instead of O(n²) for deleted index checks
- **Zoom range filtering**: Only render annotations in visible chart area
- **Image preloading**: Preload images ahead of playback position
- **Pagination**: Load data in chunks to reduce memory usage
- **Conditional rendering**: Skip image rendering at high playback speeds (>10x)

## 🔧 Troubleshooting

### Port Already in Use

**Error**: `OSError: [Errno 98] Address already in use`

**Solution**:
```bash
# Find and kill process using port 5000
lsof -ti:5000 | xargs kill -9

# Or use a different port
python app.py  # Edit app.py to change port
```

### CORS Errors

**Error**: `Access to fetch at 'http://...' from origin 'http://...' has been blocked by CORS policy`

**Solution**: Flask-CORS is already configured. Ensure `flask-cors` is installed:
```bash
pip install flask-cors
```

### Images Not Loading

**Symptoms**: Timeline and statistics work, but images show as broken

**Possible Causes**:
1. Image paths in catalog don't match actual file locations
2. Images folder missing or in wrong location
3. File permissions issue

**Solution**:
```bash
# Check data structure
ls -la data_folder/data/images/

# Verify image paths in catalog match actual files
cat data_folder/data/catalog_0.catalog | head -1 | python -m json.tool
```

### Deleted Indexes Not Persisting

**Symptoms**: Deleted indexes reset after restart

**Cause**: Manifest file not writable or wrong format

**Solution**:
```bash
# Check manifest file permissions
ls -la data_folder/data/manifest.json

# Verify manifest has 5 lines
wc -l data_folder/data/manifest.json

# Check line 5 contains catalog_manifest
sed -n '5p' data_folder/data/manifest.json
```

### Performance Issues with Large Datasets

**Symptoms**: Slow loading or chart rendering with >10,000 records

**Solutions**:
1. Use session filtering to reduce visible data
2. Adjust pagination limits in code
3. Consider data decimation for very large datasets

### Browser Compatibility

**Tested Browsers**:
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Edge 90+
- ✅ Safari 14+

**Known Issues**:
- Internet Explorer not supported (requires ES6+ features)

## 🎨 Customization

### Changing Color Scheme

Edit CSS variables in `templates/index.html`:

```css
:root {
    --bg-main: #f5f3ed;      /* Main background */
    --bg-panel: #faf9f5;     /* Panel background */
    --bg-hover: #f0ede4;     /* Hover state */
    --bg-input: #ffffff;     /* Input fields */
    --border-color: #e5e1d8; /* Borders */
    --text-primary: #2d2d2d; /* Primary text */
    --text-secondary: #5a5a5a; /* Secondary text */
}
```

### Adding New Data Processing

Extend `data_loader.py`:

```python
def custom_processing(self, key):
    """Your custom processing logic"""
    values = [r.get(key) for r in self.records if key in r]
    # Process values
    return processed_values
```

Add API endpoint in `app.py`:

```python
@app.route('/api/custom_endpoint', methods=['GET'])
def custom_endpoint():
    result = data_loader.custom_processing(request.args.get('key'))
    return jsonify({'result': result})
```

### Adding New Smoothing Algorithms

Edit smoothing section in `templates/index.html`:

```javascript
const applySmoothing = (data, option) => {
    // Add your custom smoothing option
    if (option.startsWith('custom-')) {
        // Your algorithm here
        return smoothedData;
    }
    // ... existing code
};
```

### Modifying Panel Layout

Adjust initial panel heights in React state:

```javascript
const [panelHeights, setPanelHeights] = React.useState({
    images: 25,    // percentage
    timeline: 35,
    statistics: 20,
    histogram: 20
});
```

## 📝 License

MIT License - feel free to use and modify for your projects.

## 🤝 Contributing

Contributions are welcome! This viewer was built to support the Donkeycar community.

## 📧 Support

For issues related to Donkeycar itself, visit: https://www.donkeycar.com/

---

**Built for Donkeycar enthusiasts** 🏎️💨
