# CloudCinema - Backend Python (Flask) - Seminario de Sistemas 1 - Grupo 3
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import re
import os
import time
from dotenv import load_dotenv
import mimetypes
from urllib.parse import urlparse, unquote
from bd import execute_query


load_dotenv()

app = Flask(__name__)
CORS(app)


# HELPERS

def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9._]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_int(value):
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False

# HEALTH CHECK - GET /health
@app.route("/check")
def check():
    return {"ok": True, "message": "Servidor funcionando"}, 200


# REGISTRO
@app.route("/api/v1/signup", methods=["POST"])
def signup():
    body = request.get_json()
    username = (body.get("username") or "").strip()
    email = (body.get("email") or "").strip()
    password = (body.get("password") or "")
    profile_image_url = (body.get("profileImageUrl") or "").strip()

    if not username or not email or not password or not profile_image_url:
        return jsonify({ "ok": False, "message": "Campos obligatorios faltantes"}), 400

    if not valid_email(email):
        return jsonify({"ok": False,"message": "Formato inválido en correo"}), 400

    try:
        new_id = execute_query(
            """INSERT INTO usuario (username, correo, password_hash, foto_perfil_url) VALUES (%s, %s, %s, %s) RETURNING id_usuario""",
            (username, email, md5(password), profile_image_url)
        )
        return jsonify({"ok": True,"message": "Usuario registrado correctamente", "token": str(new_id) }), 201

    except Exception as error:
        return jsonify({"ok": False,"message": f"Error al guardar datos en BD: {str(error)}"}), 500


# LOGIN 
@app.route("/api/v1/login", methods=["POST"])
def login():
    body = request.get_json()
    username = (body.get("username") or "").strip()
    password = (body.get("password") or "")
    
    if not username or not password:
        return jsonify({"ok": False,"message": "Campos obligatorios faltantes"}), 400

    try:
        user = execute_query(
            "SELECT id_usuario FROM usuario WHERE username = %s AND password_hash = %s",
            (username, md5(password)),
            fetch=True
        )
        if not user:
            return jsonify({"ok": False,"message": "Nombre de usuario o contraseña incorrectos"}), 401
        return jsonify({"ok": True,"message": "Login exitoso","token": str(user[0]["id_usuario"])}), 200
    except Exception as error:
        return jsonify({"ok": False,"message": f"Error al consultar datos en BD: {str(error)}"}), 500


# LISTADO DE TAREAS
@app.route("/api/v1/tasks", methods=["GET"])
def get_tareas():
    page_raw = request.args.get("page")
    size_raw = request.args.get("size")
    id_usuario_raw = request.args.get("id_usuario")

    if not is_valid_int(id_usuario_raw):
        return jsonify({"ok": False,"message": "Debe enviar un id_usuario válido"}), 400

    id_usuario = int(id_usuario_raw)

    try:
        if not is_valid_int(page_raw) or not is_valid_int(size_raw):
            rows = execute_query(
                """ SELECT id_tarea, id_usuario, titulo, descripcion, fecha_creacion, completada FROM tarea WHERE id_usuario = %s ORDER BY fecha_creacion DESC""",
                (id_usuario,),
                fetch=True
            )
        else:
            page = int(page_raw)
            size = int(size_raw)

            if page < 1 or size < 1:
                return jsonify({"ok": False,"message": "page y size deben ser mayores a 0"}), 400

            offset = (page - 1) * size
            
            rows = execute_query(
                """SELECT id_tarea, id_usuario, titulo, descripcion, fecha_creacion, completada FROM tarea WHERE id_usuario = %s ORDER BY fecha_creacion DESC LIMIT %s OFFSET %s """,
                (id_usuario, size, offset),
                fetch=True
            )

        for row in rows:
            if row.get("fecha_creacion"):
                row["fecha_creacion"] = str(row["fecha_creacion"])

        return jsonify({"ok": True,"message": "Tareas obtenidas correctamente","tasks": rows}), 200

    except Exception as error:
        return jsonify({"ok": False,"message": f"Error al consultar tareas: {str(error)}"}), 500


# Agregar tarea
@app.route("/api/v1/tasks", methods=["POST"])
def crear_tarea():
    
    id_usuario_raw = request.args.get("id_usuario")
    if not is_valid_int(id_usuario_raw):
        return jsonify({"ok": False,"message": "Debe enviar un id_usuario válido"}), 400

    id_usuario = int(id_usuario_raw)
    body = request.get_json()
    titulo = (body.get("titulo") or "").strip()
    descripcion = (body.get("descripcion") or "").strip()
    fecha_creacion = body.get("fecha_creacion")

    if not is_valid_int(id_usuario):
        return jsonify({ "ok": False,"message": "Debe enviar un id_usuario válido"}), 400

    if not titulo:
        return jsonify({"ok": False,"message": "El título de la tarea es obligatorio"}), 400

    id_usuario = int(id_usuario)

    try:
        if not fecha_creacion:
            fecha_creacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        execute_query(
            """INSERT INTO tarea (id_usuario, titulo, descripcion, fecha_creacion) VALUES (%s, %s, %s, %s)""",
            (id_usuario, titulo, descripcion, fecha_creacion)
        )

        return jsonify({"ok": True,"message": "Tarea creada correctamente"}), 201

    except Exception as error:
        return jsonify({"ok": False,"message": f"Error al crear tarea: {str(error)}"}), 500


# Editar tarea parcialmente
@app.route("/api/v1/tasks/<int:id_tarea>", methods=["PATCH"])
def editar_tarea(id_tarea):
    body = request.get_json()

    if not body:
        return jsonify({"ok": False, "message": "Debe enviar un JSON válido"}), 400

    id_usuario = request.args.get("id_usuario")
    if not is_valid_int(id_usuario):
        return jsonify({"ok": False,"message": "Debe enviar un id_usuario válido"}), 400
    
    titulo_nuevo = body.get("titulo")
    descripcion_nueva = body.get("descripcion")
    completada_nueva = body.get("completada")

    if not is_valid_int(id_usuario):
        return jsonify({"ok": False,"message": "Debe enviar un id_usuario válido"}), 400

    id_usuario = int(id_usuario)

    if titulo_nuevo is None and descripcion_nueva is None and completada_nueva is None:
        return jsonify({"ok": False,"message": "Debe enviar al menos un campo para actualizar: titulo, descripcion o completada"}), 400

    if titulo_nuevo is not None:
        titulo_nuevo = titulo_nuevo.strip()
        if not titulo_nuevo:
            return jsonify({"ok": False,"message": "El título no puede ir vacío"}), 400

    if descripcion_nueva is not None:
        descripcion_nueva = descripcion_nueva.strip()

    if completada_nueva is not None and not isinstance(completada_nueva, bool):
        return jsonify({"ok": False,"message": "El campo completada debe ser booleano"}), 400

    try:
        tarea = execute_query(
            """SELECT id_tarea, titulo, descripcion, completada FROM tarea WHERE id_tarea = %s AND id_usuario = %s""",
            (id_tarea, id_usuario),
            fetch=True
        )

        if not tarea:
            return jsonify({"ok": False,"message": "La tarea no existe o no pertenece al usuario"}), 404

        tarea_actual = tarea[0]

        titulo_actual = tarea_actual["titulo"]
        descripcion_actual = tarea_actual["descripcion"]
        completada_actual = tarea_actual["completada"]

  
        titulo_final = titulo_nuevo if titulo_nuevo is not None else titulo_actual
        descripcion_final = descripcion_nueva if descripcion_nueva is not None else descripcion_actual
        completada_final = completada_nueva if completada_nueva is not None else completada_actual

        if (
            titulo_final == titulo_actual and
            descripcion_final == descripcion_actual and
            completada_final == completada_actual
        ):
            return jsonify({"ok": False,"message": "No se detectaron cambios en la tarea"}), 400

        execute_query(
            """UPDATE tarea SET titulo = %s, descripcion = %s, completada = %s WHERE id_tarea = %s AND id_usuario = %s """,
            (titulo_final, descripcion_final, completada_final, id_tarea, id_usuario)
        )

        return jsonify({"ok": True,"message": "Tarea actualizada correctamente"}), 200

    except Exception as error:
        return jsonify({"ok": False,"message": f"Error al editar tarea: {str(error)}"}), 500


@app.route("/api/v1/tasks/<int:id_tarea>", methods=["DELETE"])
def eliminar_tarea(id_tarea):
    id_usuario_raw = request.args.get("id_usuario")

    if not is_valid_int(id_usuario_raw):
        return jsonify({"ok": False,"message": "Debe enviar un id_usuario válido"}), 400

    id_usuario = int(id_usuario_raw)

    try:
        tarea = execute_query(
            """SELECT id_tarea FROM tarea WHERE id_tarea = %s AND id_usuario = %s""",
            (id_tarea, id_usuario),
            fetch=True
        )

        if not tarea:
            return jsonify({"ok": False,"message": "La tarea no existe o no pertenece al usuario"}), 404

        execute_query(
            """ DELETE FROM tarea WHERE id_tarea = %s AND id_usuario = %s""",
            (id_tarea, id_usuario))

        return jsonify({"ok": True, "message": "Tarea eliminada correctamente"}), 200

    except Exception as error:
        return jsonify({"ok": False, "message": f"Error al eliminar tarea: {str(error)}"}), 500



@app.route("/api/v1/files", methods=["POST"])
def cargar_archivo():
    id_usuario_raw = request.args.get("id_usuario")
    body = request.get_json()

    if not is_valid_int(id_usuario_raw):
        return jsonify({
            "message": "Debe enviar un id_usuario válido"
        }), 400

    if not body:
        return jsonify({
            "message": "Debe enviar un JSON válido"
        }), 400

    url_archivo = (body.get("url_archivo") or "").strip()
    nombre_body = (body.get("nombre") or "").strip()

    if not url_archivo:
        return jsonify({"message": "Debe enviar la url_archivo"}), 400

    id_usuario = int(id_usuario_raw)

    try:
        parsed_url = urlparse(url_archivo)
        ruta_nube = unquote(parsed_url.path.lstrip("/"))
        nombre_url = ruta_nube.split("/")[-1]
        nombre = nombre_body if nombre_body else nombre_url

        if "amazonaws.com" in url_archivo:
            proveedor_nube = "AWS"
        elif "blob.core.windows.net" in url_archivo:
            proveedor_nube = "AZURE"
        else:
            return jsonify({ "message": "Proveedor de nube no soportado"}), 400

        mime_type = mimetypes.guess_type(nombre_url)[0] or "application/octet-stream"

        execute_query(
            """INSERT INTO archivo (id_usuario, nombre, nombre_nube, proveedor_nube, url_archivo, mime_type) VALUES (%s, %s, %s, %s, %s, %s)""",
            (id_usuario,nombre, ruta_nube, proveedor_nube, url_archivo, mime_type)
        )

        return jsonify({"message": "Ingresado correctamente"}), 201

    except Exception as error:
        return jsonify({"message": f"Error al cargar archivo: {str(error)}"}), 500
    

@app.route("/api/v1/files", methods=["GET"])
def listar_archivos():
    id_usuario_raw = request.args.get("id_usuario")

    if not is_valid_int(id_usuario_raw):
        return jsonify({"ok": False,"message": "Debe enviar un id_usuario válido"}), 400
    id_usuario = int(id_usuario_raw)

    try:
        rows = execute_query(
            """SELECT id_archivo, nombre, nombre_nube, proveedor_nube, url_archivo, mime_type, fecha_subida FROM archivo WHERE id_usuario = %s ORDER BY fecha_subida DESC """,
            (id_usuario,),
            fetch=True
        )

        for row in rows:
            if row.get("fecha_subida"):
                row["fecha_subida"] = str(row["fecha_subida"])

        return jsonify({"ok": True,"message": "Archivos obtenidos correctamente","files": rows}), 200

    except Exception as error:
        return jsonify({"ok": False,"message": f"Error al listar archivos: {str(error)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)

    """
  if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    print(f"Servidor Python corriendo en puerto {port}")
    app.run(host="0.0.0.0", port=port, debug=False)  
    """
