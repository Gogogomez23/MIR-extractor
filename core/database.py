import sqlite3
import os

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "mir_questions.db")


def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num TEXT,
            ano TEXT,
            enunciado TEXT,
            opciones_json TEXT,
            rc TEXT,
            tema TEXT,
            especialidad TEXT,
            dificultad TEXT,
            explicacion TEXT,
            status TEXT,
            status_msg TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_questions(questions_list):
    import json
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for q in questions_list:
        cursor.execute("""
            INSERT INTO questions (num, ano, enunciado, opciones_json, rc, tema, especialidad, dificultad, explicacion, status, status_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q["num"], q["ano"], q["enunciado"], json.dumps(q["opciones"]),
            q["rc"], q["tema"], q["especialidad"], q["dificultad"],
            q["explicacion"], q["status"], q["status_msg"]
        ))
    conn.commit()
    conn.close()


def get_all_questions(sort_by_year=False):
    import json
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT id, num, ano, enunciado, opciones_json, rc, tema, especialidad, dificultad, explicacion, status, status_msg FROM questions"
    if sort_by_year:
        query += " ORDER BY ano DESC, CAST(num AS INTEGER) ASC"
    else:
        query += " ORDER BY id ASC"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    questions = []
    for r in rows:
        questions.append({
            "id": r[0], "num": r[1], "ano": r[2], "enunciado": r[3],
            "opciones": json.loads(r[4]), "rc": r[5], "tema": r[6],
            "especialidad": r[7], "dificultad": r[8], "explicacion": r[9],
            "status": r[10], "status_msg": r[11]
        })
    return questions


def update_question(q_id, data):
    import json
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE questions SET 
            num = ?, enunciado = ?, opciones_json = ?, rc = ?, 
            tema = ?, especialidad = ?, dificultad = ?, 
            explicacion = ?, status = ?, status_msg = ?
        WHERE id = ?
    """, (
        data.get("num", ""), data["enunciado"], json.dumps(data["opciones"]), data["rc"],
        data["tema"], data["especialidad"], data["dificultad"],
        data["explicacion"], data["status"], data["status_msg"], q_id
    ))
    conn.commit()
    conn.close()
