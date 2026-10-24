import csv
import re
from getpass import getpass

import mysql.connector
from mysql.connector import Error

BATCH_SIZE = 5000   # rows sent to MySQL at a time (keeps memory small)


def connect(host, user, password, db_name):
    """Connect to MySQL, create the database if missing, and select it."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise ValueError("Database name may contain only letters, digits and _")
    conn = mysql.connector.connect(host=host, user=user, password=password)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    cur.close()
    conn.database = db_name
    return conn


def create_tables(conn):
    """Create both tables (only if they do not exist) with indexes."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Student (
            student_id INT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            spi DECIMAL(4,2) NOT NULL,
            INDEX idx_spi (spi)
        )""")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS CourseRegistration (
            student_id INT NOT NULL,
            course_id VARCHAR(20) NOT NULL,
            PRIMARY KEY (student_id, course_id),
            INDEX idx_course (course_id),
            FOREIGN KEY (student_id) REFERENCES Student(student_id)
        )""")
    conn.commit()
    cur.close()


def read_students(path, stats):
    """Yield valid (id, name, spi) rows from student.csv; count bad rows."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["student_id"])
                name = row["name"].strip()
                spi = float(row["spi"])
                if not name or not (0.0 <= spi <= 10.0):
                    raise ValueError
            except (ValueError, KeyError, TypeError, AttributeError):
                stats["bad"] += 1
                continue
            yield (sid, name, spi)


def read_registrations(path, stats):
    """Yield valid (id, course_id) rows from registration.csv."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["student_id"])
                course = row["course_id"].strip()
                if not course:
                    raise ValueError
            except (ValueError, KeyError, TypeError, AttributeError):
                stats["bad"] += 1
                continue
            yield (sid, course)


def insert_in_batches(conn, sql, rows):
    """Insert rows BATCH_SIZE at a time using a parameterized query."""
    cur = conn.cursor()
    batch, total = [], 0
    for r in rows:
        batch.append(r)
        if len(batch) >= BATCH_SIZE:
            cur.executemany(sql, batch)
            total += len(batch)
            batch = []
    if batch:
        cur.executemany(sql, batch)
        total += len(batch)
    conn.commit()
    cur.close()
    return total


def show_students(conn, course_id, threshold):
    """Print students of a course with SPI greater than threshold."""
    sql = """
        SELECT s.student_id, s.name, s.spi, r.course_id
        FROM Student s
        JOIN CourseRegistration r ON s.student_id = r.student_id
        WHERE r.course_id = %s AND s.spi > %s
        ORDER BY s.spi DESC, s.student_id ASC
    """
    cur = conn.cursor()
    cur.execute(sql, (course_id, threshold))
    found = False
    while True:
        rows = cur.fetchmany(1000)          # read results in small chunks
        if not rows:
            break
        for sid, name, spi, course in rows:
            print(sid, name, f"{float(spi):g}", course)
            found = True
    cur.close()
    if not found:
        print("No students found.")


def main():
    host = input("Host (press Enter for localhost): ").strip() or "localhost"
    user = input("MySQL user (press Enter for root): ").strip() or "root"
    password = getpass("MySQL password: ")
    db_name = input("Database name (press Enter for college_db): ").strip() or "college_db"
    student_csv = input("Student CSV path: ").strip()
    reg_csv = input("Registration CSV path: ").strip()
    course_id = input("Course id: ").strip()

    if not course_id:
        print("Error: course id cannot be empty")
        return
    try:
        threshold = float(input("SPI threshold: ").strip())
        if not (0.0 <= threshold <= 10.0):
            raise ValueError
    except ValueError:
        print("Error: SPI threshold must be a number from 0 to 10")
        return

    conn = None
    try:
        conn = connect(host, user, password, db_name)
        create_tables(conn)

        stats = {"bad": 0}
        n1 = insert_in_batches(
            conn,
            "INSERT IGNORE INTO Student (student_id, name, spi) VALUES (%s, %s, %s)",
            read_students(student_csv, stats))
        n2 = insert_in_batches(
            conn,
            "INSERT IGNORE INTO CourseRegistration (student_id, course_id) VALUES (%s, %s)",
            read_registrations(reg_csv, stats))
        print(f"Loaded {n1} student rows, {n2} registration rows, skipped {stats['bad']} bad rows.")
        print("-" * 30)
        show_students(conn, course_id, threshold)

    except Error as e:
        print("Database error:", e)
    except (FileNotFoundError, PermissionError, ValueError) as e:
        print("Error:", e)
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()