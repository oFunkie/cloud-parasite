import base64
import datetime
import math
import mimetypes
import os
import uuid

import jwt
from flask import Flask, jsonify, make_response, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
SECRET_KEY = "dQteuJwbDDGtMrXWdYXQqsAQVvrQoadW"

CHUNK_SIZE = 2800

# --- Etat serveur : tout en mémoire vive, remis à zéro si le serveur redémarre ---

# Métadonnées + statut affichés au master (JSON-safe, pas de bytes bruts ici)
CLIENTS = {}
# Contenu binaire réel des fichiers uploadés, séparé pour ne jamais finir
# accidentellement dans une réponse JSON (fuite de données binaires)
CLIENT_FILES = {}


def encode_chunks_from_bytes(content, filename, chunk_size=CHUNK_SIZE):
    b64_encoded_file = base64.b64encode(content).decode("ascii")
    len_file = len(b64_encoded_file)
    chunk_number = math.ceil(len_file / chunk_size)

    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = "application/octet-stream"

    ext = os.path.splitext(filename)[1].lower()

    chunks = [
        b64_encoded_file[i * chunk_size : (i + 1) * chunk_size]
        for i in range(chunk_number)
    ]

    return chunks, mime_type, ext


def build_jwts(client_id):
    """Découpe le fichier assigné à ce client et génère un JWT signé par chunk."""
    file_info = CLIENT_FILES[client_id]
    chunks, mime_type, ext = encode_chunks_from_bytes(
        file_info["content"], file_info["filename"]
    )

    tokens = {}
    for i, chunk in enumerate(chunks):
        token = jwt.encode(
            {
                "chunk_index": i,
                "total_chunks": len(chunks),
                "mime_type": mime_type,
                "filename": file_info["filename"],
                "ext": ext,
                "data": chunk,
                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            },
            SECRET_KEY,
            algorithm="HS256",
        )
        tokens[f"session_token_{i}"] = token

    return tokens, mime_type, ext


# --- Pages HTML ---

@app.route("/client/<client_id>")
def client_page(client_id):
    if client_id not in CLIENTS:
        return f"Client inconnu : {client_id}", 404
    return send_file("client.html")


@app.route("/master")
def master_page():
    return send_file("master.html")


# --- Gestion des clients (ajout / suppression / upload) ---

@app.route("/api/master/clients", methods=["POST"])
def add_client():
    client_id = uuid.uuid4().hex[:8]
    CLIENTS[client_id] = {
        "authenticated": False,
        "connected_at": None,
        "filename": None,
        "has_file": False,
        "chunks": None,
        "mime_type": None,
    }
    CLIENT_FILES[client_id] = None
    return jsonify({"status": "ok", "client_id": client_id})


@app.route("/api/master/clients/<client_id>", methods=["DELETE"])
def remove_client(client_id):
    if client_id not in CLIENTS:
        return jsonify({"error": "client inconnu"}), 404

    del CLIENTS[client_id]
    CLIENT_FILES.pop(client_id, None)
    return jsonify({"status": "ok"})


@app.route("/api/master/clients/<client_id>/upload", methods=["POST"])
def upload_file(client_id):
    if client_id not in CLIENTS:
        return jsonify({"error": "client inconnu"}), 404

    if "file" not in request.files:
        return jsonify({"error": "aucun fichier envoyé"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "nom de fichier vide"}), 400

    filename = secure_filename(file.filename)
    content = file.read()

    CLIENT_FILES[client_id] = {"content": content, "filename": filename}

    # Un nouveau fichier invalide la session en cours : on force une
    # reconnexion pour être sûr que le client récupère les bonnes données.
    CLIENTS[client_id].update(
        {
            "authenticated": False,
            "connected_at": None,
            "chunks": None,
            "filename": filename,
            "has_file": True,
        }
    )

    return jsonify({"status": "ok", "filename": filename})


# --- API utilisée par les clients ---

@app.route("/api/client/<client_id>/login", methods=["POST"])
def client_login(client_id):
    if client_id not in CLIENTS:
        return jsonify({"error": "client inconnu"}), 404

    if not CLIENTS[client_id]["has_file"]:
        return jsonify({"error": "aucun fichier n'a été assigné à ce client par le master"}), 400

    tokens, mime_type, ext = build_jwts(client_id)
    CLIENTS[client_id].update(
        {
            "authenticated": True,
            "chunks": tokens,
            "mime_type": mime_type,
            "connected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    )

    resp = make_response(jsonify({"status": "ok", "client_id": client_id}))
    for name, token in tokens.items():
        resp.set_cookie(name, token, httponly=False, secure=False, samesite="Lax")
    return resp


@app.route("/api/client/<client_id>/logout", methods=["POST"])
def client_logout(client_id):
    if client_id not in CLIENTS:
        return jsonify({"error": "client inconnu"}), 404

    CLIENTS[client_id]["authenticated"] = False
    CLIENTS[client_id]["chunks"] = None
    CLIENTS[client_id]["connected_at"] = None
    return jsonify({"status": "ok", "client_id": client_id})


@app.route("/api/master/status")
def master_status():
    return jsonify({"clients": CLIENTS})


if __name__ == "__main__":
    app.run(debug=True)