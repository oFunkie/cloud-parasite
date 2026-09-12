import base64
import datetime
import math
import mimetypes
import os

import jwt
from flask import Flask, jsonify, make_response, request, send_file

app = Flask(__name__)
SECRET_KEY = "dQteuJwbDDGtMrXWdYXQqsAQVvrQoadW"

IMAGE_PATHS = {
    "1": "medium_image.jpg",
    "2": "output_gif.gif",
    "3": "run_compress.gif",
    "4": "Salut.pdf",
    "5": "notes.txt",
    "6": "test.txt.asc",
}
CHUNK_SIZE = 2800
CLIENT_IDS = list(IMAGE_PATHS.keys())  # les slots client, un par fichier configuré

# --- Etat serveur : mémoire vive, remise à zéro si le serveur redémarre ---
CLIENTS = {
    cid: {"authenticated": False, "chunks": None, "mime_type": None, "connected_at": None}
    for cid in CLIENT_IDS
}


def encode_chunks(file_path, chunk_size=CHUNK_SIZE):
    with open(file_path, "rb") as file:
        file_content = file.read()

    b64_encoded_file = base64.b64encode(file_content).decode("ascii")
    len_file = len(b64_encoded_file)
    chunk_number = math.ceil(len_file / chunk_size)

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # mimetypes ne connaît pas .gpg (et beaucoup d'autres extensions) :
        # on retombe sur un type binaire générique, à charge du client
        # (JS) de décider quoi en faire via l'extension.
        mime_type = "application/octet-stream"

    filename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    chunks = [
        b64_encoded_file[i * chunk_size : (i + 1) * chunk_size]
        for i in range(chunk_number)
    ]

    print(f"Fichier : {file_path}")
    print(f"Type MIME détecté : {mime_type}")
    print(f"Taille base64 totale : {len_file} caractères")
    print(f"Nombre de chunks : {len(chunks)}")

    return chunks, mime_type, filename, ext


# Chaque client a ses propres chunks, générés depuis son propre fichier
CLIENT_MEDIA = {
    cid: dict(zip(("chunks", "mime_type", "filename", "ext"), encode_chunks(path)))
    for cid, path in IMAGE_PATHS.items()
}


def build_jwts(client_id):
    """Génère un nouveau jeu de JWT signés pour le fichier propre à ce client."""
    media = CLIENT_MEDIA[client_id]
    tokens = {}
    for i, chunk in enumerate(media["chunks"]):
        token = jwt.encode(
            {
                "chunk_index": i,
                "total_chunks": len(media["chunks"]),
                "mime_type": media["mime_type"],
                "filename": media["filename"],
                "ext": media["ext"],
                "data": chunk,
                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            },
            SECRET_KEY,
            algorithm="HS256",
        )
        tokens[f"session_token_{i}"] = token
    return tokens


# --- Pages HTML ---

@app.route("/client/<client_id>")
def client_page(client_id):
    if client_id not in CLIENT_IDS:
        return f"Client inconnu : {client_id}", 404
    return send_file("client.html")


@app.route("/master")
def master_page():
    return send_file("master.html")


# --- API utilisée par les pages ---

@app.route("/api/client/<client_id>/login", methods=["POST"])
def client_login(client_id):
    if client_id not in CLIENT_IDS:
        return jsonify({"error": "client inconnu"}), 404

    tokens = build_jwts(client_id)
    CLIENTS[client_id] = {
        "authenticated": True,
        "chunks": tokens,
        "mime_type": CLIENT_MEDIA[client_id]["mime_type"],
        "connected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    resp = make_response(jsonify({"status": "ok", "client_id": client_id}))
    # On pose aussi les cookies sur le navigateur du client, pour rester
    # cohérent avec le concept JWT-en-cookie (utile si ce client veut
    # afficher son propre fichier via display.html séparément).
    for name, token in tokens.items():
        resp.set_cookie(name, token, httponly=False, secure=False, samesite="Lax")
    return resp


@app.route("/api/client/<client_id>/logout", methods=["POST"])
def client_logout(client_id):
    if client_id not in CLIENT_IDS:
        return jsonify({"error": "client inconnu"}), 404

    CLIENTS[client_id]["authenticated"] = False
    return jsonify({"status": "ok", "client_id": client_id})


@app.route("/api/master/status")
def master_status():
    return jsonify({"clients": CLIENTS})


if __name__ == "__main__":
    app.run(debug=True)