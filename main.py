import json
import sqlite3
from datetime import datetime

DB_FILE = "medical.db"


# ======================================================================
# 1. Подключение
# ======================================================================

def get_mongo_db():
    """Настоящий MongoDB, если доступен; иначе mongomock (in-memory)."""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        print("✓ MongoDB: подключено к localhost:27017")
        return client["medical_db"]
    except Exception as e:
        print(f"⚠ MongoDB недоступен ({type(e).__name__}). "
              f"Использую mongomock (данные НЕ сохранятся между запусками).")
        print("  Для сохранения: docker run -d -p 27017:27017 mongo:7")
        import mongomock
        return mongomock.MongoClient()["medical_db"]


def init_sqlite(path=DB_FILE):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name  TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            phone      TEXT
        );
        CREATE TABLE IF NOT EXISTS doctors (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name      TEXT NOT NULL,
            specialization TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


# ======================================================================
# 2. SQLite — операции
# ======================================================================

def add_patient(conn, full_name, birth_date, phone):
    cur = conn.execute(
        "INSERT INTO patients (full_name, birth_date, phone) VALUES (?, ?, ?)",
        (full_name, birth_date, phone),
    )
    conn.commit()
    return cur.lastrowid


def add_doctor(conn, full_name, specialization):
    cur = conn.execute(
        "INSERT INTO doctors (full_name, specialization) VALUES (?, ?)",
        (full_name, specialization),
    )
    conn.commit()
    return cur.lastrowid


def get_patient(conn, patient_id):
    row = conn.execute(
        "SELECT id, full_name, birth_date, phone FROM patients WHERE id = ?",
        (patient_id,),
    ).fetchone()
    if not row:
        return None
    return {"id": row[0], "full_name": row[1],
            "birth_date": row[2], "phone": row[3]}


def list_patients(conn):
    return conn.execute(
        "SELECT id, full_name, birth_date, phone FROM patients ORDER BY id"
    ).fetchall()


def list_doctors(conn):
    return conn.execute(
        "SELECT id, full_name, specialization FROM doctors ORDER BY id"
    ).fetchall()


# ======================================================================
# 3. MongoDB — операции
# ======================================================================

def add_medical_record(db, patient_id, doctor_id, diagnosis, notes,
                       test_results, visit_date):
    return db.medical_records.insert_one({
        "patient_id":   patient_id,
        "doctor_id":    doctor_id,
        "visit_date":   visit_date,
        "diagnosis":    diagnosis,
        "notes":        notes,
        "test_results": test_results,
    }).inserted_id


def get_patient_records(db, patient_id):
    return list(db.medical_records.find({"patient_id": patient_id})
                                .sort("visit_date", -1))


def search_by_diagnosis(db, substring):
    return list(db.medical_records.find(
        {"diagnosis": {"$regex": substring, "$options": "i"}}
    ).sort("visit_date", -1))


def get_full_patient_history(conn, db, patient_id):
    """Кросс-БД запрос: пациент из SQLite + история из MongoDB."""
    patient = get_patient(conn, patient_id)
    if not patient:
        return None
    return {"patient": patient, "records": get_patient_records(db, patient_id)}


# ======================================================================
# 4. Утилиты ввода
# ======================================================================

def input_int(prompt):
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("  ⚠ Введите целое число.")


def input_str(prompt, required=True):
    while True:
        s = input(prompt).strip()
        if s or not required:
            return s
        print("  ⚠ Поле не может быть пустым.")


def parse_test_results(s):
    result = {}
    for pair in s.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k, v = k.strip(), v.strip()
        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                pass
        result[k] = v
    return result


# ======================================================================
# 5. Обработчики команд
# ======================================================================

def cmd_add_patient(conn):
    full_name = input_str("ФИО пациента: ")
    birth_date = input_str("Дата рождения (ГГГГ-ММ-ДД): ")
    phone = input_str("Телефон (пусто = нет): ", required=False)
    pid = add_patient(conn, full_name, birth_date, phone or None)
    print(f"  ✓ Пациент добавлен, id = {pid}")


def cmd_add_doctor(conn):
    full_name = input_str("ФИО врача: ")
    spec = input_str("Специализация: ")
    did = add_doctor(conn, full_name, spec)
    print(f"  ✓ Врач добавлен, id = {did}")


def cmd_add_record(conn, db):
    print("\nДоступные пациенты:")
    rows = list_patients(conn)
    if not rows:
        print("  (нет, сначала добавьте пациента)"); return
    for r in rows:
        print(f"  {r[0]}. {r[1]}")

    print("Доступные врачи:")
    rows = list_doctors(conn)
    if not rows:
        print("  (нет, сначала добавьте врача)"); return
    for r in rows:
        print(f"  {r[0]}. {r[1]} ({r[2]})")

    pid = input_int("ID пациента: ")
    if not conn.execute("SELECT 1 FROM patients WHERE id = ?", (pid,)).fetchone():
        print("  ⚠ Пациент не найден."); return
    did = input_int("ID врача: ")
    if not conn.execute("SELECT 1 FROM doctors WHERE id = ?", (did,)).fetchone():
        print("  ⚠ Врач не найден."); return

    diagnosis = input_str("Диагноз: ")
    notes = input_str("Заметки (пусто = нет): ", required=False)
    tr_raw = input_str("Анализы 'key=value, key=value' (пусто = нет): ", required=False)
    date_default = datetime.now().strftime("%Y-%m-%d")
    date = input_str(f"Дата визита (пусто = {date_default}): ", required=False) or date_default

    add_medical_record(db, pid, did, diagnosis, notes or None,
                       parse_test_results(tr_raw), date)
    print("  ✓ Запись добавлена в MongoDB.")


def cmd_list_patients(conn):
    rows = list_patients(conn)
    if not rows:
        print("  (нет пациентов)"); return
    for r in rows:
        print(f"  {r[0]}. {r[1]} — ДР {r[2]}, тел: {r[3] or '—'}")


def cmd_list_doctors(conn):
    rows = list_doctors(conn)
    if not rows:
        print("  (нет врачей)"); return
    for r in rows:
        print(f"  {r[0]}. {r[1]} — {r[2]}")


def cmd_history(conn, db):
    pid = input_int("ID пациента: ")
    h = get_full_patient_history(conn, db, pid)
    if not h:
        print("  ⚠ Пациент не найден."); return

    p = h["patient"]
    print(f"\nПациент: {p['full_name']}  (ДР {p['birth_date']}, тел {p['phone'] or '—'})")

    if not h["records"]:
        print("  История пуста."); return

    # подтянем имя врача из SQLite для читаемости
    for i, r in enumerate(h["records"], 1):
        doc = conn.execute(
            "SELECT full_name, specialization FROM doctors WHERE id = ?",
            (r["doctor_id"],)
        ).fetchone()
        doc_str = f"{doc[0]} ({doc[1]})" if doc else f"id={r['doctor_id']}"
        print(f"\n  #{i}  {r['visit_date']}  врач: {doc_str}")
        print(f"    Диагноз: {r['diagnosis']}")
        if r.get("notes"):
            print(f"    Заметки: {r['notes']}")
        if r.get("test_results"):
            print(f"    Анализы: {json.dumps(r['test_results'], ensure_ascii=False)}")


def cmd_search(conn, db):
    sub = input_str("Подстрока диагноза: ")
    records = search_by_diagnosis(db, sub)
    if not records:
        print("  (ничего не найдено)"); return
    for r in records:
        p = get_patient(conn, r["patient_id"])
        name = p["full_name"] if p else f"пациент id={r['patient_id']}"
        print(f"  {r['visit_date']}  {name}: {r['diagnosis']}")


# ======================================================================
# 6. Главное меню
# ======================================================================

MENU = """
--- Меню -----------------------------------------------------
  1. Добавить пациента
  2. Добавить врача
  3. Добавить медицинскую запись
  4. Список пациентов
  5. Список врачей
  6. Полная история пациента (SQLite + MongoDB)
  7. Поиск по диагнозу (MongoDB regex)
  0. Выход
-------------------------------------------------------------
"""


def main():
    print("=" * 60)
    print("  Гибридная система: SQLite + MongoDB")
    print("=" * 60)
    conn = init_sqlite()
    db = get_mongo_db()
    print(f"SQLite: {DB_FILE}")

    try:
        while True:
            print(MENU)
            choice = input("Выбор: ").strip()
            if choice == "1":   cmd_add_patient(conn)
            elif choice == "2": cmd_add_doctor(conn)
            elif choice == "3": cmd_add_record(conn, db)
            elif choice == "4": cmd_list_patients(conn)
            elif choice == "5": cmd_list_doctors(conn)
            elif choice == "6": cmd_history(conn, db)
            elif choice == "7": cmd_search(conn, db)
            elif choice == "0":
                print("Выход."); break
            else:
                print("  ⚠ Нет такого пункта.")
    except (KeyboardInterrupt, EOFError):
        print("\nВыход.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()