#!/bin/bash
cd "$(dirname "$0")"
export PATH="/Users/elianmartinez/.gemini/antigravity/scratch/node-portable/bin:$PATH"
echo "Iniciando Puente RTMP (Node.js + FFmpeg)..."
node server.js
