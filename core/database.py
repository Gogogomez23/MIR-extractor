import json
import os
import sqlite3

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "mir_questions.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def _reset_autoincrement(cursor, table_names):
    if not _table_exists(cursor, "sqlite_sequence"):
        return

    for table_name in table_names:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table_name,))


def _get_or_create_legacy_extraction(cursor):
    cursor.execute(
        """
        SELECT id
        FROM extractions
        WHERE filename = ? AND page_range = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        ("legacy_imports", "legacy")
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO extractions (filename, page_range)
        VALUES (?, ?)
        """,
        ("legacy_imports", "legacy")
    )
    return cursor.lastrowid


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            page_range TEXT NOT NULL,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    if not _table_exists(cursor, "questions"):
        cursor.execute(
            """
            CREATE TABLE questions (
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
                status_msg TEXT,
                extraction_id INTEGER REFERENCES extractions(id) ON DELETE CASCADE,
                revised INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
        conn.close()
        return

    if not _column_exists(cursor, "questions", "extraction_id"):
        cursor.execute(
            """
            ALTER TABLE questions
            ADD COLUMN extraction_id INTEGER REFERENCES extractions(id) ON DELETE CASCADE
            """
        )

    if not _column_exists(cursor, "questions", "revised"):
        cursor.execute(
            """
            ALTER TABLE questions
            ADD COLUMN revised INTEGER NOT NULL DEFAULT 0
            """
        )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM questions
        WHERE extraction_id IS NULL
        """
    )
    null_batch_rows = cursor.fetchone()[0]
    if null_batch_rows:
        legacy_extraction_id = _get_or_create_legacy_extraction(cursor)
        cursor.execute(
            """
            UPDATE questions
            SET extraction_id = ?
            WHERE extraction_id IS NULL
            """,
            (legacy_extraction_id,)
        )

    conn.commit()
    conn.close()


def _find_duplicate_question(cursor, ano, num, especialidad, current_extraction_id):
    cursor.execute(
        """
        SELECT id, extraction_id
        FROM questions
        WHERE ano = ?
          AND num = ?
          AND especialidad = ?
          AND (extraction_id IS NULL OR extraction_id <> ?)
        ORDER BY id ASC
        LIMIT 1
        """,
        (ano, num, especialidad, current_extraction_id)
    )
    return cursor.fetchone()


def save_questions(questions_list, filename="", page_range=""):
    if not questions_list:
        return None

    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO extractions (filename, page_range)
        VALUES (?, ?)
        """,
        (filename or "", page_range or "")
    )
    extraction_id = cursor.lastrowid

    for q in questions_list:
        status = q.get("status", "")
        status_msg = q.get("status_msg", "")
        duplicate_row = _find_duplicate_question(
            cursor,
            q.get("ano", ""),
            q.get("num", ""),
            q.get("especialidad", ""),
            extraction_id
        )
        if duplicate_row:
            status = "🟡 DUPLICATE"
            status_msg = "Duplicate question already exists in a previous batch."

        cursor.execute(
            """
            INSERT INTO questions (
                num, ano, enunciado, opciones_json, rc, tema, especialidad,
                dificultad, explicacion, status, status_msg, extraction_id, revised
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                q.get("num", ""),
                q.get("ano", ""),
                q.get("enunciado", ""),
                json.dumps(q.get("opciones", [])),
                q.get("rc", ""),
                q.get("tema", ""),
                q.get("especialidad", ""),
                q.get("dificultad", ""),
                q.get("explicacion", ""),
                status,
                status_msg,
                extraction_id,
                int(q.get("revised", 0))
            )
        )

    conn.commit()
    conn.close()
    return extraction_id


def get_extractions():
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, filename, page_range, timestamp
        FROM extractions
        ORDER BY id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "filename": row[1],
            "page_range": row[2],
            "timestamp": row[3]
        }
        for row in rows
    ]


def get_latest_extraction_id():
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM extractions
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_unique_specialties():
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT TRIM(especialidad) AS specialty
        FROM questions
        WHERE COALESCE(TRIM(especialidad), '') <> ''
        ORDER BY specialty COLLATE NOCASE ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows]


def _normalize_optional_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value

    text_value = str(value).strip()
    if not text_value:
        return None

    try:
        return int(text_value)
    except (TypeError, ValueError):
        return None


def _build_question_filters(filters):
    filters = filters or {}
    clauses = []
    params = []

    batch_id = _normalize_optional_int(filters.get("batch_id"))
    if batch_id is not None:
        clauses.append("extraction_id = ?")
        params.append(batch_id)

    year_start = _normalize_optional_int(filters.get("year_start"))
    year_end = _normalize_optional_int(filters.get("year_end"))
    if year_start is not None:
        clauses.append("CAST(ano AS INTEGER) >= ?")
        params.append(year_start)
    if year_end is not None:
        clauses.append("CAST(ano AS INTEGER) <= ?")
        params.append(year_end)

    specialty = filters.get("specialty")
    if specialty not in (None, "", "all"):
        clauses.append("TRIM(especialidad) = ?")
        params.append(str(specialty).strip())

    review_status = str(filters.get("review_status", "all")).strip().lower()
    if review_status == "revised":
        clauses.append("COALESCE(revised, 0) = 1")
    elif review_status in {"pending", "unrevised"}:
        clauses.append("COALESCE(revised, 0) = 0")

    return clauses, params


def _build_order_clause(sorting_mode):
    mode = (sorting_mode or "id").strip().lower()
    order_map = {
        "id": "ORDER BY id ASC",
        "year": "ORDER BY CAST(ano AS INTEGER) DESC, CAST(num AS INTEGER) ASC, id ASC",
        "tema": (
            "ORDER BY COALESCE(NULLIF(TRIM(tema), ''), 'ZZZ') COLLATE NOCASE ASC, "
            "CAST(ano AS INTEGER) DESC, CAST(num AS INTEGER) ASC, id ASC"
        ),
        "num": "ORDER BY CAST(num AS INTEGER) ASC, CAST(ano AS INTEGER) DESC, id ASC",
    }
    return order_map.get(mode, order_map["id"])


def _rows_to_questions(rows):
    questions = []
    for row in rows:
        questions.append({
            "id": row[0],
            "num": row[1],
            "ano": row[2],
            "enunciado": row[3],
            "opciones": json.loads(row[4]) if row[4] else [],
            "rc": row[5],
            "tema": row[6],
            "especialidad": row[7],
            "dificultad": row[8],
            "explicacion": row[9],
            "status": row[10],
            "status_msg": row[11],
            "extraction_id": row[12],
            "revised": row[13]
        })
    return questions


def get_filtered_questions(filters=None, sorting_mode="id"):
    conn = _connect()
    cursor = conn.cursor()

    clauses, params = _build_question_filters(filters)
    query = """
        SELECT id, num, ano, enunciado, opciones_json, rc, tema, especialidad,
               dificultad, explicacion, status, status_msg, extraction_id, revised
        FROM questions
    """

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += f" {_build_order_clause(sorting_mode)}"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return _rows_to_questions(rows)


def get_explorer_questions(filters=None):
    conn = _connect()
    cursor = conn.cursor()

    clauses, params = _build_question_filters(filters)
    query = """
        SELECT id, num, ano, enunciado, opciones_json, rc, tema, especialidad,
               dificultad, explicacion, status, status_msg, extraction_id, revised
        FROM questions
    """

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    sorting_mode = None
    if isinstance(filters, dict):
        sorting_mode = filters.get("sorting_mode")

    mode = (sorting_mode or "id").strip().lower()
    order_map = {
        "id": "ORDER BY COALESCE(extraction_id, 0) DESC, id ASC",
        "year": (
            "ORDER BY COALESCE(extraction_id, 0) DESC, CAST(ano AS INTEGER) DESC, "
            "CAST(num AS INTEGER) ASC, id ASC"
        ),
        "tema": (
            "ORDER BY COALESCE(extraction_id, 0) DESC, "
            "COALESCE(NULLIF(TRIM(tema), ''), 'ZZZ') COLLATE NOCASE ASC, "
            "CAST(ano AS INTEGER) DESC, CAST(num AS INTEGER) ASC, id ASC"
        ),
        "num": "ORDER BY COALESCE(extraction_id, 0) DESC, CAST(num AS INTEGER) ASC, CAST(ano AS INTEGER) DESC, id ASC",
    }

    query += " " + order_map.get(mode, order_map["id"])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return _rows_to_questions(rows)


def get_filtered_questions_count(filters=None):
    conn = _connect()
    cursor = conn.cursor()

    clauses, params = _build_question_filters(filters)
    query = "SELECT COUNT(*) FROM questions"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count


def count_filtered_questions(filters=None):
    return get_filtered_questions_count(filters)


def get_all_questions(sort_by_year=False, extraction_id=None, sort_by_quest_num=False, sort_by_tema=False):
    filters = {}
    if extraction_id is not None:
        filters["batch_id"] = extraction_id

    # sorting_mode = "year" if sort_by_year else "id"
    if sort_by_year:
        sorting_mode = "year"
    elif sort_by_quest_num:
        sorting_mode = "num"
    elif sort_by_tema:
        sorting_mode = "tema"
    else:
        sorting_mode = "id"
    return get_filtered_questions(filters=filters, sorting_mode=sorting_mode)


def update_question(q_id, data):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE questions SET
            num = ?, enunciado = ?, opciones_json = ?, rc = ?,
            tema = ?, especialidad = ?, dificultad = ?,
            explicacion = ?, status = ?, status_msg = ?, revised = ?
        WHERE id = ?
        """,
        (
            data.get("num", ""),
            data["enunciado"],
            json.dumps(data["opciones"]),
            data["rc"],
            data["tema"],
            data["especialidad"],
            data["dificultad"],
            data["explicacion"],
            data["status"],
            data["status_msg"],
            int(data.get("revised", 0)),
            q_id
        )
    )
    conn.commit()
    conn.close()


def update_question_revision(q_id, revised):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE questions
        SET revised = ?
        WHERE id = ?
        """,
        (int(revised), q_id)
    )
    conn.commit()
    conn.close()


def delete_batch(extraction_id):
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM extractions WHERE id = ?",
        (extraction_id,)
    )
    batch_exists = cursor.fetchone()[0]
    if not batch_exists:
        conn.close()
        return {
            "batch_deleted": 0,
            "questions_deleted": 0,
            "extraction_id": extraction_id,
        }

    cursor.execute(
        "SELECT COUNT(*) FROM questions WHERE extraction_id = ?",
        (extraction_id,)
    )
    questions_deleted = cursor.fetchone()[0]

    cursor.execute(
        "DELETE FROM extractions WHERE id = ?",
        (extraction_id,)
    )
    deleted_batches = cursor.rowcount

    conn.commit()
    conn.close()
    return {
        "batch_deleted": deleted_batches,
        "questions_deleted": questions_deleted,
        "extraction_id": extraction_id,
    }


def clear_questions_only():
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM questions")
    questions_deleted = cursor.fetchone()[0]
    cursor.execute("DELETE FROM questions")
    _reset_autoincrement(cursor, ["questions"])

    conn.commit()
    conn.close()
    return {
        "questions_deleted": questions_deleted,
    }


def clear_all_data():
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM questions")
    questions_deleted = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM extractions")
    batches_deleted = cursor.fetchone()[0]

    cursor.execute("DELETE FROM questions")
    cursor.execute("DELETE FROM extractions")
    _reset_autoincrement(cursor, ["questions", "extractions"])

    conn.commit()
    conn.close()
    return {
        "questions_deleted": questions_deleted,
        "batches_deleted": batches_deleted,
    }


def get_database_stats():
    conn = _connect()
    cursor = conn.cursor()

    if not _table_exists(cursor, "extractions") or not _table_exists(cursor, "questions"):
        conn.close()
        return {
            "total_batches": 0,
            "total_questions": 0,
            "total_revised": 0,
            "total_unrevised": 0,
        }

    cursor.execute("SELECT COUNT(*) FROM extractions")
    total_batches = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(revised, 0) = 1")
    total_revised = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(revised, 0) = 0")
    total_unrevised = cursor.fetchone()[0]

    conn.close()
    return {
        "total_batches": total_batches,
        "total_questions": total_questions,
        "total_revised": total_revised,
        "total_unrevised": total_unrevised,
    }
