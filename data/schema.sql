-- ======================================================================
-- Схема реляционной части проекта (SQLite): пациенты и врачи.
-- Выполнение:  sqlite3 medical.db < data/schema.sql
-- ======================================================================

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

-- ----------------------------------------------------------------------
-- Демонстрационные данные
-- ----------------------------------------------------------------------

INSERT INTO patients (full_name, birth_date, phone) VALUES
    ('Иванов Иван Иванович',       '1985-03-12', '+7-900-111-22-33'),
    ('Петрова Анна Сергеевна',     '1992-07-04', '+7-900-444-55-66'),
    ('Смирнов Алексей Петрович',   '1978-11-23', '+7-900-777-88-99'),
    ('Козлова Мария Дмитриевна',   '2001-05-18', NULL);

INSERT INTO doctors (full_name, specialization) VALUES
    ('Сидоров Пётр Алексеевич',    'Кардиолог'),
    ('Кузнецова Мария Викторовна', 'Терапевт'),
    ('Морозов Андрей Николаевич',  'Невролог');
