from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import os
import json
import glob
import numpy as np
from pathlib import Path
from data_loader import DonkeycarDataLoader

app = Flask(__name__)
CORS(app)

# Initialize data loader
data_loader = DonkeycarDataLoader()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/browse', methods=['GET'])
def browse_directory():
    """Browse directory structure"""
    current_path = request.args.get('path', os.path.expanduser('~'))
    try:
        # Ensure path is absolute and safe
        current_path = os.path.abspath(current_path)
        
        items = []
        
        # Add parent directory option (except for root)
        parent_path = os.path.dirname(current_path)
        if parent_path != current_path:  # Not at root
            items.append({
                'name': '..',
                'path': parent_path,
                'type': 'parent',
                'is_data_folder': False
            })
        
        # List directory contents
        for item in sorted(os.listdir(current_path)):
            if item.startswith('.'):  # Skip hidden files
                continue
                
            item_path = os.path.join(current_path, item)
            
            if os.path.isdir(item_path):
                # Check if it's a data folder
                data_path = os.path.join(item_path, 'data')
                has_catalog = False
                if os.path.exists(data_path):
                    try:
                        files = os.listdir(data_path)
                        has_catalog = any(f.endswith('.catalog') for f in files)
                    except:
                        pass
                
                items.append({
                    'name': item,
                    'path': item_path,
                    'type': 'directory',
                    'is_data_folder': has_catalog
                })
        
        return jsonify({
            'current_path': current_path,
            'items': items
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/folders', methods=['GET'])
def get_folders():
    """Get list of data folders (legacy endpoint)"""
    # Default to parent directory to find data folders
    base_path = request.args.get('path', '..')
    try:
        folders = []
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                # Check if it contains data subfolder with catalog files
                data_path = os.path.join(item_path, 'data')
                if os.path.exists(data_path):
                    try:
                        files = os.listdir(data_path)
                        if any(f.endswith('.catalog') for f in files):
                            folders.append({
                                'name': item,
                                'path': os.path.abspath(item_path),  # Use absolute path
                                'has_data': True
                            })
                    except:
                        pass
        return jsonify({'folders': folders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/load_data', methods=['POST'])
def load_data():
    """Load data from selected folder"""
    try:
        folder_path = request.json.get('folder_path')
        if not folder_path:
            return jsonify({'error': 'No folder path provided'}), 400
        
        data_loader.load_data(folder_path)
        
        # Get basic info about loaded data
        info = {
            'total_records': len(data_loader.records),
            'sessions': data_loader.get_sessions(),
            'data_keys': data_loader.get_data_keys(),
            'timestamp_range': data_loader.get_timestamp_range(),
            'deleted_indexes': data_loader.get_deleted_indexes()
        }
        
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get data records with pagination"""
    try:
        # Get query parameters
        start_idx = int(request.args.get('start', 0))
        end_idx = request.args.get('end', None)
        if end_idx is not None:
            end_idx = int(end_idx)
        session_id = request.args.get('session', None)
        
        # Get filtered records
        records = data_loader.get_records(start_idx, end_idx, session_id)
        
        return jsonify({
            'records': records,
            'total': len(data_loader.records)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """Get statistics for numerical data"""
    try:
        key = request.args.get('key')
        session_id = request.args.get('session', None)
        
        if not key:
            # Return statistics for all numerical keys
            all_stats = {}
            for k in data_loader.get_numerical_keys():
                stats = data_loader.calculate_statistics(k, session_id)
                if stats:
                    all_stats[k] = stats
            return jsonify(all_stats)
        else:
            # Return statistics for specific key
            stats = data_loader.calculate_statistics(key, session_id)
            if stats:
                return jsonify({key: stats})
            else:
                return jsonify({'error': 'Key not found or not numerical'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/image/<path:image_path>')
def get_image(image_path):
    """Serve image files"""
    try:
        # Reconstruct the full path
        full_path = os.path.join(data_loader.base_path, 'data', 'images', image_path)
        
        if os.path.exists(full_path):
            return send_file(full_path, mimetype='image/jpeg')
        else:
            return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/timeline', methods=['GET'])
def get_timeline():
    """Get timeline data for visualization"""
    try:
        session_id = request.args.get('session', None)
        key = request.args.get('key', 'user/throttle')
        
        timeline_data = data_loader.get_timeline_data(key, session_id)
        
        return jsonify({
            'key': key,
            'data': timeline_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)