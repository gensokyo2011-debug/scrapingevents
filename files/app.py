import json
import os
import threading
import time

from flask import Flask, jsonify, render_template, send_file

from scraper_eventos_panama import recolectar_todo, exportar

app = Flask(__name__, template_folder=".")

ESTADO = {"corriendo": False, "ultima_actualizacion": None, "total": 0, "error": None}
DATA_FILE = "eventos_panama.json"


def _correr_scraper():
    ESTADO["corriendo"] = True
    ESTADO["error"] = None
    try:
        eventos = recolectar_todo(incluir_dinamicas=True)
        exportar(eventos)
        ESTADO["total"] = len(eventos)
        ESTADO["ultima_actualizacion"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        ESTADO["error"] = str(e)
    finally:
        ESTADO["corriendo"] = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/eventos")
def api_eventos():
    if not os.path.exists(DATA_FILE):
        return jsonify([])
    with open(DATA_FILE, encoding="utf-8") as f:
        return jsonify(json.load(f))


@app.route("/api/actualizar", methods=["POST"])
def actualizar():
    if ESTADO["corriendo"]:
        return jsonify({"ok": False, "msg": "Ya hay una actualización en curso"}), 409
    threading.Thread(target=_correr_scraper, daemon=True).start()
    return jsonify({"ok": True, "msg": "Actualización iniciada"})


@app.route("/api/estado")
def estado():
    return jsonify(ESTADO)


@app.route("/api/descargar/csv")
def descargar_csv():
    if not os.path.exists("eventos_panama.csv"):
        return "Aún no hay datos, corre una actualización primero.", 404
    return send_file("eventos_panama.csv", as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
