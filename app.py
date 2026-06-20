from flask import Flask, render_template, jsonify, request, send_file, redirect, Response
import urllib.request
import urllib.error
from flask_cors import CORS
import os
import json
import glob
import logging
import base64
import time
import platform
import numpy as np
import sys
import subprocess
import webbrowser
import threading
import inspect
import atexit
import signal
import socket
from pathlib import Path
from data_loader import DonkeycarDataLoader
# NOTE: training_manager / neural_network は torch・mlflow を連れてくるため
# モジュール先頭では import しない（起動時間が ~7秒 増える）。
# 学習・モデル系の API が初めて呼ばれたとき、または起動後のバックグラウンド暖機で読み込む。

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize data loader
data_loader = DonkeycarDataLoader()

# --- TrainingManager の遅延初期化 ---------------------------------------
# torch+mlflow のロード(約7秒)を起動クリティカルパスから外すため、
# 最初に必要になった時点で生成する。スレッド安全のためロックで保護。
_training_manager = None
_training_manager_lock = threading.Lock()


def get_training_manager():
    """Lazily create the TrainingManager (imports torch+mlflow on first call)."""
    global _training_manager
    if _training_manager is None:
        with _training_manager_lock:
            if _training_manager is None:
                from training_manager import TrainingManager  # heavy: torch+mlflow
                _training_manager = TrainingManager()
    return _training_manager

# Track child processes for cleanup
_child_processes = []


def _cleanup_child_processes():
    """Terminate all child processes on exit"""
    for proc in _child_processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    _child_processes.clear()


atexit.register(_cleanup_child_processes)


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown"""
    _cleanup_child_processes()
    sys.exit(0)


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


@app.after_request
def _cache_vendor_assets(response):
    """同梱ライブラリ(static/vendor)はバージョン固定のため長期immutableキャッシュを付与。
    初回はローカルから取得、2回目以降はブラウザキャッシュで即時ロード（再検証もしない）。"""
    if request.path.startswith('/static/vendor/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.static_folder, 'favicon.ico'), mimetype='image/x-icon')

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
        
        # Check if current directory itself is a data folder
        current_has_catalog = any(f.endswith('.catalog') for f in os.listdir(current_path) if os.path.isfile(os.path.join(current_path, f)))

        # List directory contents
        for item in sorted(os.listdir(current_path), key=lambda x: os.path.getmtime(os.path.join(current_path, x)), reverse=True):
            if item.startswith('.'):  # Skip hidden files
                continue

            item_path = os.path.join(current_path, item)

            if os.path.isdir(item_path):
                # Check if it's a data folder
                # Pattern 1: folder/data/*.catalog (Donkeycar format)
                # Pattern 2: folder/*.catalog (direct data folder)
                has_catalog = False

                # Check Pattern 1: subfolder named 'data' with catalog files
                data_path = os.path.join(item_path, 'data')
                if os.path.exists(data_path):
                    try:
                        files = os.listdir(data_path)
                        has_catalog = any(f.endswith('.catalog') for f in files)
                    except:
                        pass

                # Check Pattern 2: catalog files directly in folder
                if not has_catalog:
                    try:
                        files = os.listdir(item_path)
                        has_catalog = any(f.endswith('.catalog') for f in files if os.path.isfile(os.path.join(item_path, f)))
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
        logger.exception('API error')
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
            if os.path.isdir(item_path) and item.startswith('data'):
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
        logger.exception('API error')
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
        
        # Add LiDAR metadata if available
        lidar_metadata = data_loader.get_lidar_metadata()
        if lidar_metadata:
            info['lidar_metadata'] = lidar_metadata

        return jsonify({'success': True, 'info': info})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/lidar/<path:npy_filename>')
def get_lidar(npy_filename):
    """Serve a single LiDAR .npy file as JSON distances"""
    try:
        distances = data_loader.load_lidar_data(npy_filename)
        if distances is None:
            return jsonify({'error': 'LiDAR data not found'}), 404

        response = jsonify({'distances': distances})
        response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
        return response
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/lidar_batch', methods=['POST'])
def get_lidar_batch():
    """Serve multiple LiDAR .npy files in a single response"""
    try:
        data = request.json
        filenames = data.get('filenames', [])

        if not filenames:
            return jsonify({'error': 'No filenames provided'}), 400

        lidar_data = {}
        for filename in filenames:
            distances = data_loader.load_lidar_data(filename)
            if distances is not None:
                lidar_data[filename] = distances

        return jsonify({'lidar_data': lidar_data})
    except Exception as e:
        logger.exception('API error')
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
        logger.exception('API error')
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
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/image/<path:image_path>')
def get_image(image_path):
    """Serve image files, optionally with reduced JPEG quality"""
    try:
        # Use data_path which points to the actual data location
        full_path = os.path.join(data_loader.data_path, 'images', image_path)

        if not os.path.exists(full_path):
            return jsonify({'error': 'Image not found'}), 404

        quality = request.args.get('quality', type=int)

        if quality and 1 <= quality < 95:
            from PIL import Image as PILImage
            import io
            img = PILImage.open(full_path)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=quality, optimize=True)
            buf.seek(0)
            response = send_file(buf, mimetype='image/jpeg')
        else:
            response = send_file(full_path, mimetype='image/jpeg')

        response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
        return response
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/images_batch', methods=['POST'])
def get_images_batch():
    """Serve multiple images in a single response as base64-encoded JSON"""
    try:
        data = request.json
        paths = data.get('paths', [])
        quality = data.get('quality', None)

        if not paths:
            return jsonify({'error': 'No paths provided'}), 400

        results = {}
        images_dir = os.path.join(data_loader.data_path, 'images')

        for image_path in paths:
            full_path = os.path.join(images_dir, image_path)
            if os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    img_data = f.read()

                if quality and 1 <= quality < 95:
                    from PIL import Image as PILImage
                    import io
                    img = PILImage.open(io.BytesIO(img_data))
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG', quality=quality, optimize=True)
                    img_data = buf.getvalue()

                results[image_path] = base64.b64encode(img_data).decode('ascii')

        return jsonify({'images': results})
    except Exception as e:
        logger.exception('API error')
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
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_indexes', methods=['POST'])
def update_delete_indexes():
    """Update deleted indexes in manifest file"""
    try:
        data = request.json
        start_idx = data.get('start_idx')
        end_idx = data.get('end_idx')

        if start_idx is None or end_idx is None:
            return jsonify({'error': 'start_idx and end_idx are required'}), 400

        if start_idx > end_idx:
            return jsonify({'error': 'start_idx must be <= end_idx'}), 400

        deleted_indexes = data_loader.update_deleted_indexes(start_idx, end_idx)

        return jsonify({
            'success': True,
            'deleted_indexes': deleted_indexes,
            'count': len(deleted_indexes)
        })
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear_delete_indexes', methods=['POST'])
def clear_delete_indexes():
    """Clear deleted indexes in manifest file"""
    try:
        data = request.json
        start_idx = data.get('start_idx')
        end_idx = data.get('end_idx')

        if start_idx is None or end_idx is None:
            return jsonify({'error': 'start_idx and end_idx are required'}), 400

        if start_idx > end_idx:
            return jsonify({'error': 'start_idx must be <= end_idx'}), 400

        deleted_indexes = data_loader.clear_deleted_indexes(start_idx, end_idx)

        return jsonify({
            'success': True,
            'deleted_indexes': deleted_indexes,
            'count': len(deleted_indexes)
        })
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


# =====================================================
# Training API Endpoints
# =====================================================

@app.route('/api/training/train', methods=['POST'])
def train_model():
    """Start new model training"""
    try:
        from neural_network import TrainingConfig  # heavy: torch（学習時のみ読み込む）
        data = request.json
        config = TrainingConfig.from_dict(data)
        result = get_training_manager().train_model(config, data_loader.records, data_path=data_loader.data_path, continue_training=False)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/continue', methods=['POST'])
def continue_training():
    """Continue training from existing model"""
    try:
        from neural_network import TrainingConfig  # heavy: torch（学習時のみ読み込む）
        data = request.json
        config = TrainingConfig.from_dict(data)
        result = get_training_manager().train_model(config, data_loader.records, data_path=data_loader.data_path, continue_training=True)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/stop', methods=['POST'])
def stop_training():
    """Stop current training"""
    try:
        result = get_training_manager().stop_training()
        return jsonify(result)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/training/progress', methods=['GET'])
def get_training_progress():
    """Get current training progress"""
    try:
        progress = get_training_manager().get_progress()
        return jsonify(progress)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


# =====================================================
# Model Management API Endpoints
# =====================================================

@app.route('/api/models', methods=['GET'])
def list_models():
    """List all saved models"""
    try:
        tm = get_training_manager()
        models = tm.list_models()
        models_dir = str(Path(tm.models_dir).resolve())
        # experiment_id は MLflow UI へのディープリンク生成にフロントで使う
        return jsonify({'models': models, 'models_dir': models_dir,
                        'mlflow_experiment_id': getattr(tm, 'experiment_id', None)})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/open_folder', methods=['POST'])
def open_folder():
    """Open a folder in the system file explorer"""
    try:
        folder_path = request.json.get('path', '')
        folder_path = os.path.abspath(folder_path)
        if not os.path.isdir(folder_path):
            return jsonify({'error': 'Folder not found'}), 404
        if platform.system() == 'Windows':
            os.startfile(folder_path)
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', folder_path])
        else:
            subprocess.Popen(['xdg-open', folder_path])
        return jsonify({'message': 'Folder opened', 'path': folder_path})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/models/load', methods=['POST'])
def load_model():
    """Load a model from file"""
    try:
        data = request.json
        model_path = data.get('model_path')

        if not model_path:
            return jsonify({'error': 'model_path is required'}), 400

        result = get_training_manager().load_model(model_path)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/models/delete', methods=['POST'])
def delete_model():
    """Delete a model file"""
    try:
        data = request.json
        model_path = data.get('model_path')

        if not model_path:
            return jsonify({'error': 'model_path is required'}), 400

        result = get_training_manager().delete_model(model_path)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/models/predict', methods=['POST'])
def predict():
    """Run prediction with current model"""
    try:
        data = request.json
        deleted_indexes = data.get('deleted_indexes', [])

        result = get_training_manager().predict(data_loader.records, deleted_indexes, data_path=data_loader.data_path)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/models/current', methods=['GET'])
def get_current_model():
    """Get current loaded model info"""
    try:
        model_info = get_training_manager().get_current_model_info()
        if model_info:
            return jsonify({'model_info': model_info})
        else:
            return jsonify({'model_info': None})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


# =====================================================
# MLflow API Endpoints
# =====================================================

def _is_mlflow_running():
    """Return True if something is already listening on the MLflow UI port (8011)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', 8011))
    sock.close()
    return result == 0


def _launch_mlflow_ui():
    """Launch the MLflow UI subprocess if not already running. Returns True if started, False if already up."""
    if _is_mlflow_running():
        return False

    # Start MLflow UI on port 8011 (to avoid conflict with data_viewer on 8010)
    # バックエンドは SQLite なので sqlite:/// URI を渡す（file:// は MLflow 3.x で禁止）
    db_path = Path(get_training_manager().mlruns_dir).resolve() / 'mlflow.db'
    backend_uri = f'sqlite:///{db_path}'
    # --static-prefix /mlflow: MLflow の全パス（静的アセット・API）に /mlflow を付与する。
    # これにより Flask 側で /mlflow/* を透過プロキシでき、HTML 書き換えが不要になる。
    # 127.0.0.1 のみで待受け（外部公開は Flask:8010 の /mlflow/ プロキシ経由のみ）。
    # RPi では uvicorn の起動が遅いためワーカー数を 1 に削減。
    proc = subprocess.Popen(
        [sys.executable, '-m', 'mlflow', 'ui',
         '--host', '127.0.0.1', '--port', '8011',
         '--backend-store-uri', backend_uri,
         '--static-prefix', '/mlflow',
         '-w', '1'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    _child_processes.append(proc)
    logger.info(f'MLflow UI process started (pid={proc.pid}), backend={backend_uri}')
    return True


@app.route('/api/mlflow/start', methods=['POST'])
def start_mlflow_ui():
    """Start MLflow UI server"""
    try:
        if not _launch_mlflow_ui():
            return jsonify({'message': 'MLflow UI already running', 'port': 8011, 'ready': True})
        return jsonify({'message': 'MLflow UI started', 'port': 8011, 'ready': False})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/mlflow/status', methods=['GET'])
def mlflow_status():
    """Check if MLflow UI is ready (TCP connect from server side to avoid browser CORS/popup issues)"""
    return jsonify({'ready': _is_mlflow_running(), 'port': 8011})


@app.route('/mlflow', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/mlflow/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/mlflow/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def mlflow_proxy(path):
    """Transparent reverse-proxy to the MLflow UI on 8011 (started with --static-prefix /mlflow).

    MLflow が全パスに /mlflow を付けるため、書き換えなしでそのまま転送できる。
    実行ポート 8011 を別途開放せずに Flask:8010 経由で MLflow にアクセスできる。
    """
    target = f'http://127.0.0.1:8011/mlflow/{path}'
    if request.query_string:
        target += '?' + request.query_string.decode()
    try:
        # Host/Content-Length は urllib に再計算させるため除外
        fwd_headers = {k: v for k, v in request.headers
                       if k.lower() not in ('host', 'content-length')}
        req = urllib.request.Request(
            target,
            data=request.get_data() or None,
            headers=fwd_headers,
            method=request.method,
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            excluded = {'content-encoding', 'transfer-encoding', 'connection', 'content-length'}
            headers = [(k, v) for k, v in resp.headers.items()
                       if k.lower() not in excluded]
            return Response(resp.read(), status=resp.status, headers=headers)
    except urllib.error.HTTPError as e:
        # MLflow からのエラー応答（JSON等）をそのまま返す
        return Response(e.read(), status=e.code,
                        content_type=e.headers.get('Content-Type', 'text/plain'))
    except Exception:
        # MLflow がまだ起動中（Connection refused 等）→ 起動を促し自動リロードする待機ページを返す。
        # 生のエラーJSONを見せず、20〜30秒で自動的に表示される。
        # 起動トリガーは別スレッドへ（_launch_mlflow_ui は torch+mlflow の重いimportを伴い
        # 同期実行するとレスポンスを数秒ブロックするため）。冪等なので多重呼び出しでも安全。
        threading.Thread(target=_launch_mlflow_ui, daemon=True).start()
        wait_html = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>MLflow 起動中</title><meta http-equiv="refresh" content="3">
<style>body{font-family:sans-serif;display:flex;flex-direction:column;align-items:center;
justify-content:center;height:100vh;margin:0;color:#555;background:#f5f3ed}
.spin{width:28px;height:28px;border:3px solid #ccc;border-top-color:#3b82f6;
border-radius:50%;animation:s 1s linear infinite;margin-bottom:1rem}
@keyframes s{to{transform:rotate(360deg)}}</style></head>
<body><div class="spin"></div><div>MLflow を起動しています...</div>
<div style="font-size:.8rem;margin-top:.5rem">初回はライブラリ読込のため20〜30秒かかります（自動で再読込します）</div>
</body></html>"""
        return Response(wait_html, status=503, content_type='text/html; charset=utf-8',
                        headers={'Retry-After': '3'})


@app.route('/api/platform', methods=['GET'])
def get_platform():
    """Detect platform (RPi vs desktop) for adaptive buffer sizing"""
    try:
        is_rpi = False
        model_name = ''

        # Check /proc/device-tree/model for Raspberry Pi
        device_tree_model = '/proc/device-tree/model'
        if os.path.exists(device_tree_model):
            try:
                with open(device_tree_model, 'r') as f:
                    model_name = f.read().strip('\x00').strip()
                if 'raspberry pi' in model_name.lower():
                    is_rpi = True
            except Exception:
                pass

        # Fallback: check ARM architecture
        if not is_rpi:
            machine = platform.machine().lower()
            if machine in ('aarch64', 'armv7l', 'armv6l'):
                is_rpi = True

        # Get total RAM from /proc/meminfo
        total_ram_mb = 0
        if os.path.exists('/proc/meminfo'):
            try:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            parts = line.split()
                            total_ram_mb = int(parts[1]) // 1024
                            break
            except Exception:
                pass

        profile = 'rpi' if is_rpi else 'desktop'

        return jsonify({
            'profile': profile,
            'model': model_name,
            'arch': platform.machine(),
            'total_ram_mb': total_ram_mb
        })
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/sensors', methods=['GET'])
def get_available_sensors():
    """Get list of available sensor keys from loaded data"""
    try:
        if not data_loader.records:
            return jsonify({'sensors': []})

        # Get first record to find sensor keys
        first_record = data_loader.records[0]

        # Find all keys that can be used as input features
        # Exclude internal keys, image keys, and output keys
        excluded_prefixes = ('_', 'cam', 'user/')
        excluded_keys = {'_index', '_absolute_index', '_display_index', '_is_deleted'}

        sensor_list = []
        for key, value in first_record.items():
            # Skip excluded keys
            if key in excluded_keys:
                continue
            if any(key.startswith(prefix) for prefix in excluded_prefixes):
                continue
            # Numerical values → scalar sensor
            if isinstance(value, (int, float)):
                sensor_list.append({'key': key, 'type': 'scalar', 'size': 1})
            # .npy string values (distance_array) → array sensor
            elif isinstance(value, str) and value.endswith('.npy') and key.endswith('/distance_array'):
                array_size = data_loader.get_lidar_array_size(value)
                if array_size is not None:
                    sensor_list.append({'key': key, 'type': 'array', 'size': array_size})

        # Preserve original order from catalog (don't sort)
        return jsonify({'sensors': sensor_list})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


@app.route('/api/code', methods=['GET'])
def get_code():
    """Get source code sections for display"""
    try:
        from training_manager import TrainingManager  # 遅延import（ソース表示用）
        sections = []

        # Section 1: Model definition (neural_network.py full file)
        nn_path = os.path.join(os.path.dirname(__file__), 'neural_network.py')
        with open(nn_path, 'r') as f:
            nn_code = f.read()
        sections.append({'title': 'モデル定義 (neural_network.py)', 'code': nn_code})

        # Section 2: Training loop (_train_model_internal method)
        train_code = inspect.getsource(TrainingManager._train_model_internal)
        sections.append({'title': '学習ループ (_train_model_internal)', 'code': train_code})

        # Section 3: Data loader (_build_input_matrix method)
        dataloader_code = inspect.getsource(TrainingManager._build_input_matrix)
        sections.append({'title': 'データローダー (_build_input_matrix)', 'code': dataloader_code})

        # Section 4: Data sample from currently loaded records
        if data_loader.records:
            sample_lines = []
            sample_lines.append(f"# データパス: {data_loader.data_path}")
            lidar_path = os.path.join(data_loader.data_path, 'lidar')
            if os.path.isdir(lidar_path):
                sample_lines.append(f"# LiDARパス: {lidar_path}")
            sample_lines.append(f"# 読み込み済みデータ: 全 {len(data_loader.records)} レコード")
            sample_lines.append(f"# キー一覧: {list(data_loader.records[0].keys())}")
            sample_lines.append("")

            sample_count = min(3, len(data_loader.records))
            for i in range(sample_count):
                rec = data_loader.records[i]
                sample_lines.append(f"# --- レコード [{i}] ---")
                sample_lines.append(f"records[{i}] = {{")
                for key, value in rec.items():
                    if isinstance(value, str) and value.endswith('.npy') and key.endswith('/distance_array'):
                        # LiDAR: .npy ファイルを読み込んで実データを表示
                        lidar_data = data_loader.load_lidar_data(value)
                        if lidar_data is not None:
                            sample_lines.append(f"    {key!r}: {value!r},")
                            sample_lines.append(f"    # ↑ LiDAR点群 ({len(lidar_data)}点): 実データ ↓")
                            # 先頭・末尾を省略表示
                            arr_str = repr(lidar_data[:10])[:-1] + ', ..., ' + repr(lidar_data[-3:])[1:]
                            sample_lines.append(f"    # distances = {arr_str}")
                            sample_lines.append(f"    # min={min(lidar_data):.1f}, max={max(lidar_data):.1f}, mean={sum(lidar_data)/len(lidar_data):.1f}")
                        else:
                            sample_lines.append(f"    {key!r}: {value!r},  # (LiDAR .npy 読み込み不可)")
                    else:
                        sample_lines.append(f"    {key!r}: {value!r},")
                sample_lines.append("}")
                sample_lines.append("")

            sections.append({
                'title': f'データサンプル（先頭 {sample_count} 件 / 全 {len(data_loader.records)} 件）',
                'code': '\n'.join(sample_lines)
            })

        return jsonify({'sections': sections})
    except Exception as e:
        logger.exception('API error')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # use_reloader=False to prevent watchdog from restarting during training
    # (PyTorch/MLflow imports trigger file changes that cause reloads)

    PORT = 8010

    def _get_local_ip():
        """Get the local IP address for LAN access"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    local_ip = _get_local_ip()
    logger.info(f'Starting data_viewer on port {PORT}')
    logger.info(f'  Local:   http://localhost:{PORT}')
    if local_ip:
        logger.info(f'  Network: http://{local_ip}:{PORT}')

    # 起動後にバックグラウンドで「学習スタックの暖機」と「MLflow UI 先行起動」を行う。
    #  - torch+mlflow の import(約7秒)を最初のページ表示クリットカルパスから外しつつ、
    #    裏で先読みしておくことで初回学習も待たされない。
    #  - 最初の数秒はページ初期描画を優先するため、少し遅らせてから開始する。
    def _warm_background():
        try:
            time.sleep(3)  # 初期ページ描画にCPUを譲ってから暖機を始める
            get_training_manager()  # torch+mlflow+TM を先読み（裏で）
            logger.info('Training stack warmed (torch+mlflow loaded in background)')
            if _launch_mlflow_ui():
                logger.info('MLflow UI pre-launching in background (ready in ~20s)')
        except Exception as e:
            logger.warning(f'Background warm-up failed (features still work on demand): {e}')

    threading.Thread(target=_warm_background, daemon=True).start()

    # Open browser automatically after a short delay
    def open_browser():
        webbrowser.open(f'http://localhost:{PORT}')

    threading.Timer(1.5, open_browser).start()

    # Kill any leftover process on the port before starting
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        if sock.connect_ex(('127.0.0.1', PORT)) == 0:
            logger.warning(f'Port {PORT} is already in use. Attempting to free it...')
            subprocess.run(['fuser', '-k', f'{PORT}/tcp'], capture_output=True)
        sock.close()
    except Exception:
        pass

    from werkzeug.serving import WSGIRequestHandler
    WSGIRequestHandler.protocol_version = "HTTP/1.1"

    # debug=False: RPi では debug の自動リロード/オーバーヘッドを避けて起動を軽くする
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)