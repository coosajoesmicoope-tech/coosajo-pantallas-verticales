process.on('uncaughtException', (err) => {
    console.error('🔴 EXCEPCIÓN NO CONTROLADA (Evitando caída del servidor):', err);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('🔴 PROMESA NO CONTROLADA:', reason);
});

const http = require('http');
const fs = require('fs');
const path = require('path');
const WebSocket = require('ws');
const { spawn } = require('child_process');
const ffmpegPath = require('@ffmpeg-installer/ffmpeg').path;

const PORT = 8081;
const RTMP_URL = 'rtmp://10.60.59.15/Mundial';

// Crear servidor HTTP estático
const server = http.createServer((req, res) => {
    // Definimos el directorio base (NUEVO_SISTEMA_RTMP)
    const baseDir = path.join(__dirname, '..', 'NUEVO_SISTEMA_RTMP');
    
    // Si piden la raíz, redirigir a la mesa técnica
    let filePath = path.join(baseDir, req.url === '/' ? 'mesa_tecnica_rtmp.html' : req.url);
    
    // Seguridad para no salir del directorio
    if (!filePath.startsWith(baseDir)) {
        res.statusCode = 403;
        return res.end('Acceso denegado');
    }

    const extname = path.extname(filePath);
    let contentType = 'text/html';
    switch (extname) {
        case '.js': contentType = 'text/javascript'; break;
        case '.css': contentType = 'text/css'; break;
        case '.json': contentType = 'application/json'; break;
        case '.png': contentType = 'image/png'; break;      
        case '.jpg': contentType = 'image/jpg'; break;
    }

    fs.readFile(filePath, (error, content) => {
        if (error) {
            if(error.code == 'ENOENT') {
                res.writeHead(404);
                res.end('Archivo no encontrado');
                res.end(); 
            } else {
                res.writeHead(500);
                res.end('Error interno: '+error.code+' ..\n');
                res.end(); 
            }
        } else {
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(content, 'utf-8');
        }
    });
});

// Adjuntar el servidor WebSocket al mismo servidor HTTP
const wss = new WebSocket.Server({ server });

wss.on('connection', (ws, req) => {
    console.log('🟢 Navegador conectado a la Mesa Técnica (WebSocket)');

    // Extraer calidad y URL RTMP desde la URL (ej. /?quality=720&rtmp=...)
    const url = new URL(req.url, `http://localhost:${PORT}`);
    const quality = url.searchParams.get('quality') || '720';
    const clientRtmpUrl = url.searchParams.get('rtmp') || RTMP_URL;

    let vBitrate = '2000k';
    let bufSize = '4000k';
    if (quality === '480') {
        vBitrate = '1500k';
        bufSize = '3000k';
    } else if (quality === '1080') {
        vBitrate = '3000k';
        bufSize = '6000k';
    }

    console.log(`🎬 Calidad seleccionada: ${quality}p -> Bitrate: ${vBitrate}`);
    console.log(`📡 Transmitiendo a RTMP: ${clientRtmpUrl}`);

    const ffmpegArgs = [
        '-f', 'matroska', 
        '-i', '-', 
        '-c:v', 'libx264',
        '-preset', 'ultrafast', 
        '-tune', 'zerolatency',
        '-b:v', vBitrate,
        '-minrate', vBitrate,
        '-maxrate', vBitrate,
        '-bufsize', bufSize,
        '-pix_fmt', 'yuv420p',
        '-g', '50', 
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100',
        '-f', 'flv',
        clientRtmpUrl
    ];

    const ffmpeg = spawn(ffmpegPath, ffmpegArgs);

    ffmpeg.on('error', (err) => {
        console.error('🔴 ERROR CRÍTICO: No se pudo ejecutar FFmpeg. ¿Está instalado en esta Mac?', err);
        ws.close();
    });

    ffmpeg.on('close', (code, signal) => {
        console.log(`🔴 FFmpeg se cerró con el código ${code} y señal ${signal}`);
        ws.close();
    });

    ffmpeg.stdin.on('error', (e) => {
        // Ignorar el error de "pipe closed" silenciosamente
    });

    ffmpeg.stderr.on('data', (data) => {
        console.log('FFmpeg Log:', data.toString()); 
    });

    ws.on('message', (msg) => {
        if (Buffer.isBuffer(msg) && ffmpeg.stdin.writable) {
            try {
                ffmpeg.stdin.write(msg);
            } catch (err) {
                console.error('🔴 Error al escribir en FFmpeg stdin:', err.message);
            }
        }
    });

    ws.on('close', () => {
        console.log('🔌 Navegador desconectado.');
        ffmpeg.kill('SIGINT');
    });
});

server.listen(PORT, () => {
    console.log(`\n======================================================`);
    console.log(`🚀 SERVIDOR PUENTE INICIADO CORRECTAMENTE`);
    console.log(`======================================================`);
    console.log(`\nPara abrir la Mesa Técnica, copia este enlace y pégalo en Google Chrome:\n`);
    console.log(`➡️  http://localhost:${PORT}/  ⬅️`);
    console.log(`\nNo cierres esta ventanita negra mientras transmites.`);
    console.log(`Destino RTMP configurado: ${RTMP_URL}\n`);
});
