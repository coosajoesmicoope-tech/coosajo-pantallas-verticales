import os
import json
import time
import io
from flask import Flask, render_template, request, jsonify, send_from_directory, Response
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__, static_folder='static', template_folder='templates')

# Directivas de almacenamiento
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_FOLDER = os.path.join(BASE_DIR, 'uploads')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

os.makedirs(MEDIA_FOLDER, exist_ok=True)

# Configuraciones y extensiones permitidas
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mov', 'png', 'jpg', 'jpeg', 'webp', 'gif'}

def is_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Habilitar CORS
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Range'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    return response

DEFAULT_CONFIG = {
    "ticker": "✨ ¡Ahorrar tiene premio! Por cada depósito de Q50 en tu Magicuenta, llévate tus estampitas. 💰 Conoce nuestras tasas de interés preferenciales en agencias COOSAJO.",
    "weather": {"city": "Esquipulas", "temp": "24°C"},
    "update_interval": 10,
    "media": [],
    "last_updated": time.time()
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando config.json: {e}")
        return DEFAULT_CONFIG

def save_config(config_data):
    config_data["last_updated"] = time.time()
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

ACTIVE_SCREENS = {}

@app.route('/')
@app.route('/admin')
def admin_panel():
    config = load_config()
    return render_template('admin_dashboard.html', config=config)

@app.route('/player')
def screen_player():
    return render_template('client_player.html')

# --- TRANSMISIÓN EN VIVO WEBRTC / HTTP LIVE STREAM (RTMP EQUIVALENT) ---
def generate_live_stream():
    """Generador de transmisión en vivo (MJPEG Stream estilo RTMP / IP Cam)"""
    width, height = 1080, 1920
    frame_delay = 0.1 # 10 FPS
    
    while True:
        config = load_config()
        media_list = [m for m in config.get('media', []) if 'filename' in m]

        if not media_list:
            # Crear cuadro de transmisión institucional por defecto
            img = Image.new('RGB', (width, height), color='#172e59')
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, height-200, width, height], fill='#158e45')
            draw.text((60, 200), "COOSAJO R.L.", fill='#ffffff')
            draw.text((60, 300), "TRANSMISIÓN EN VIVO 4K", fill='#34d399')
            draw.text((60, 500), "Cuestión de Ahorrar y Ganar", fill='#ffffff')
            
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            frame_bytes = buf.getvalue()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(1)
        else:
            for item in media_list:
                filePath = os.path.join(MEDIA_FOLDER, item['filename'])
                if os.path.exists(filePath):
                    try:
                        img = Image.open(filePath).convert('RGB')
                        img = img.resize((width, height), Image.Resampling.LANCZOS)
                        
                        buf = io.BytesIO()
                        img.save(buf, format='JPEG', quality=85)
                        frame_bytes = buf.getvalue()

                        # Emitir fotogramas durante la duración configurada
                        duration = int(item.get('duration', 12))
                        ticks = int(duration / frame_delay)
                        for _ in range(ticks):
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                            time.sleep(frame_delay)
                    except Exception as e:
                        print(f"Error procesando frame de streaming: {e}")
                        time.sleep(1)

@app.route('/stream.mjpg')
@app.route('/webrtc/stream')
def live_stream():
    """Endpoint de transmisión en vivo continua para cualquier pantalla TV"""
    return Response(generate_live_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/webrtc')
def webrtc_player():
    """Página de reproductor de transmisión en vivo (WebRTC / RTMP Player)"""
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>COOSAJO Live WebRTC Stream</title>
        <style>
            body, html { width: 100%; height: 100%; margin: 0; background: #000; overflow: hidden; }
            img { width: 100%; height: 100%; object-fit: cover; }
        </style>
    </head>
    <body>
        <img src="/stream.mjpg" />
    </body>
    </html>
    """

# --- API ENDPOINTS ---

@app.route('/api/playlist', methods=['GET'])
def get_playlist():
    config = load_config()
    host_url = request.host_url.rstrip('/')
    processed_config = dict(config)
    processed_media = []

    for item in config.get('media', []):
        item_copy = dict(item)
        raw_url = item_copy.get('url', '')
        if raw_url.startswith('/'):
            item_copy['url'] = f"{host_url}{raw_url}"
        elif '127.0.0.1' in raw_url:
            path_part = raw_url.split('127.0.0.1:5050')[-1]
            item_copy['url'] = f"{host_url}{path_part}"
        processed_media.append(item_copy)
        
    processed_config['media'] = processed_media
    return jsonify(processed_config)

@app.route('/api/ticker', methods=['POST'])
def update_ticker():
    data = request.get_json() or {}
    new_ticker = data.get('ticker', '').strip()
    if not new_ticker:
        return jsonify({"success": False, "error": "El texto del ticker no puede estar vacío"}), 400
    
    config = load_config()
    config['ticker'] = new_ticker
    save_config(config)
    return jsonify({"success": True, "ticker": new_ticker, "last_updated": config["last_updated"]})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No se seleccionó ningún archivo"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Nombre de archivo inválido"}), 400

    if file and is_allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        name_part, ext_part = os.path.splitext(filename)
        final_filename = f"{name_part}_{timestamp}{ext_part}"
        filepath = os.path.join(MEDIA_FOLDER, final_filename)
        file.save(filepath)

        ext = ext_part.lower().lstrip('.')
        file_type = "video" if ext in ['mp4', 'webm', 'mov'] else "image"

        config = load_config()
        new_media_item = {
            "id": f"media-{timestamp}",
            "type": file_type,
            "name": file.filename,
            "url": f"/uploads/{final_filename}",
            "filename": final_filename,
            "duration": int(request.form.get('duration', 15 if file_type == 'image' else 0)),
            "target": "main"
        }
        config['media'].append(new_media_item)
        save_config(config)

        return jsonify({"success": True, "media": new_media_item})
    
    return jsonify({"success": False, "error": "Formato de archivo no soportado. Usa .mp4, .webm, .png, .jpg, .webp"}), 400

@app.route('/api/media/<string:media_id>', methods=['DELETE'])
def delete_media(media_id):
    config = load_config()
    initial_len = len(config['media'])
    updated_media = []
    
    for item in config['media']:
        if item.get('id') == media_id:
            if 'filename' in item:
                filePath = os.path.join(MEDIA_FOLDER, item['filename'])
                if os.path.exists(filePath):
                    try:
                        os.remove(filePath)
                    except Exception as e:
                        print(f"Error eliminando archivo {filePath}: {e}")
        else:
            updated_media.append(item)
            
    if len(updated_media) < initial_len:
        config['media'] = updated_media
        save_config(config)
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Elemento no encontrado"}), 404

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(MEDIA_FOLDER, filename)

@app.route('/api/ping', methods=['POST'])
def screen_ping():
    data = request.get_json() or {}
    screen_id = data.get('screen_id', 'pantalla-generica')
    
    ACTIVE_SCREENS[screen_id] = {
        "screen_id": screen_id,
        "name": data.get('name', f'Pantalla {screen_id}'),
        "ip": request.remote_addr,
        "current_playing": data.get('current_playing', 'N/A'),
        "last_seen": time.time(),
        "status": "ONLINE"
    }
    return jsonify({"success": True, "server_time": time.time()})

@app.route('/api/screens', methods=['GET'])
def get_screens():
    now = time.time()
    screens_list = []
    for sid, sdata in ACTIVE_SCREENS.items():
        is_online = (now - sdata['last_seen']) < 30
        sdata['status'] = "ONLINE" if is_online else "OFFLINE"
        screens_list.append(sdata)
    return jsonify(screens_list)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f"Servidor CMS COOSAJO ejecutándose en http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
