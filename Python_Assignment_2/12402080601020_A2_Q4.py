import json
import re
from getpass import getpass

import mysql.connector
from mysql.connector import Error

# Whitelist: user-facing name -> (real SQL column, type)
COLUMNS = {
    "student.id":     ("s.student_id", "int"),
    "student.name":   ("s.name", "str"),
    "student.spi":    ("s.spi", "num"),
    "course.id":      ("c.course_id", "str"),
    "course.name":    ("c.name", "str"),
    "course.credits": ("c.credits", "int"),
}
OPERATORS = {"=", ">", ">=", "<", "<=", "LIKE", "BETWEEN"}
UNSAFE = re.compile(r";|--|/\*|\*/|\x00")   # extra safety check on text values
JOIN_SQL = (
    "FROM Student s "
    "JOIN CourseRegistration r ON s.student_id = r.student_id "
    "JOIN Course c ON c.course_id = r.course_id"
)


def check_value(kind, value):
    """Convert/validate one value according to the column type."""
    if kind in ("int", "num"):
        if isinstance(value, bool):
            raise ValueError("Boolean is not a valid number")
        try:
            return int(value) if kind == "int" else float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Value {value!r} must be a number")
    if not isinstance(value, str) or not value or len(value) > 100:
        raise ValueError("Text value must be 1 to 100 characters")
    if UNSAFE.search(value):
        raise ValueError(f"Unsafe characters in value {value!r}")
    return value


def build_query(spec):
    """Validate the JSON request and return (sql_template, params)."""
    if not isinstance(spec, dict):
        raise ValueError("Input must be a JSON object")

    # 1) SELECT columns
    cols = spec.get("columns")
    if not isinstance(cols, list) or not cols:
        raise ValueError("'columns' must be a non-empty list")
    if len(cols) != len(set(map(str, cols))):
        raise ValueError("Duplicate columns are not allowed")
    select_parts = []
    for c in cols:
        if c not in COLUMNS:
            raise ValueError(f"Invalid column: {c!r}")
        select_parts.append(COLUMNS[c][0])

    # 2) WHERE filters
    where_parts, params = [], []
    filters = spec.get("where", [])
    if not isinstance(filters, list):
        raise ValueError("'where' must be a list")
    for cond in filters:
        if not isinstance(cond, dict):
            raise ValueError("Each filter must be an object")
        col, op = cond.get("col"), str(cond.get("op", "")).upper()
        if col not in COLUMNS:
            raise ValueError(f"Invalid filter column: {col!r}")
        if op not in OPERATORS:
            raise ValueError(f"Invalid operator: {op!r}")
        sql_col, kind = COLUMNS[col]
        value = cond.get("value")
        if op == "BETWEEN":
            if kind == "str" or not isinstance(value, list) or len(value) != 2:
                raise ValueError("BETWEEN needs a numeric column and [low, high]")
            lo, hi = check_value(kind, value[0]), check_value(kind, value[1])
            if lo > hi:
                raise ValueError("BETWEEN low must be <= high")
            where_parts.append(f"{sql_col} BETWEEN %s AND %s")
            params += [lo, hi]
        else:
            if op == "LIKE" and kind != "str":
                raise ValueError("LIKE works only on text columns")
            if op in ("<", ">", "<=", ">=") and kind == "str":
                raise ValueError("Range operators work only on numeric columns")
            where_parts.append(f"{sql_col} {op} %s")
            params.append(check_value(kind, value))

    # 3) ORDER BY
    order_sql = ""
    order = spec.get("order")
    if order is not None:
        if not isinstance(order, dict) or order.get("col") not in COLUMNS:
            raise ValueError("Invalid order column")
        direction = str(order.get("dir", "ASC")).upper()
        if direction not in ("ASC", "DESC"):
            raise ValueError("Order direction must be ASC or DESC")
        order_sql = f" ORDER BY {COLUMNS[order['col']][0]} {direction}"

    # 4) LIMIT (1..1000)
    limit = spec.get("limit", 100)
    if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 1000):
        raise ValueError("LIMIT must be an integer from 1 to 1000")
    params.append(limit)

    sql = f"SELECT {', '.join(select_parts)} {JOIN_SQL}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += order_sql + " LIMIT %s"
    return sql, params


def setup_course_table(conn):
    """Create Course table and a few sample courses (safe to repeat)."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Course (
            course_id VARCHAR(20) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            credits INT NOT NULL
        )""")
    cur.executemany(
        "INSERT IGNORE INTO Course (course_id, name, credits) VALUES (%s, %s, %s)",
        [("PY101", "Programming with Python", 4),
         ("DB101", "Database Systems", 3)])
    conn.commit()
    cur.close()


def run_query(conn, sql, params, headers):
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    print(" | ".join(headers))
    for row in rows:
        print(" | ".join(str(v) for v in row))
    if not rows:
        print("(no rows)")


def load_request(text):
    """Accept either JSON typed on one line or a path to a .json file."""
    text = text.strip()
    if not text.startswith("{"):
        with open(text, "r", encoding="utf-8-sig") as f:
            text = f.read()
    return json.loads(text)


def main():
    host = input("Host (press Enter for localhost): ").strip() or "localhost"
    user = input("MySQL user (press Enter for root): ").strip() or "root"
    password = getpass("MySQL password: ")
    db_name = input("Database name (press Enter for college_db): ").strip() or "college_db"
    request = input("JSON file path (or JSON on one line): ")

    # Validate FIRST: bad input never reaches the database
    try:
        spec = load_request(request)
        sql, params = build_query(spec)
    except (ValueError, FileNotFoundError, PermissionError) as e:  # JSONDecodeError is a ValueError
        print("SQL_REJECTED:", e)
        return

    conn = None
    try:
        conn = mysql.connector.connect(host=host, user=user, password=password, database=db_name)
        setup_course_table(conn)
        print("SQL_OK")
        print("SQL template:", sql)
        print("Parameters  :", params)
        print("-" * 30)
        run_query(conn, sql, params, spec["columns"])
    except Error as e:
        print("Database error:", e)
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()