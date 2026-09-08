#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="eventos-panama-test"

cd "$ROOT_DIR"

echo "== Validando Python =="
python -m py_compile files/app.py files/scraper_eventos_panama.py

echo "== Construyendo Docker =="
docker build -f Dockerfile -t "$IMAGE_NAME" .

echo "== Ejecutando scraping dentro de Docker =="
docker run --rm -v "$ROOT_DIR/files:/app" "$IMAGE_NAME" python scraper_eventos_panama.py

echo "== Archivos generados =="
ls -lh files/eventos_panama.json files/eventos_panama.csv
echo "== Monitor actualizado =="