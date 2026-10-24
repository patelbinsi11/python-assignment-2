import re
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import mysql.connector
    from mysql.connector import Error, IntegrityError
except ImportError:
    raise SystemExit("mysql-connector-python is missing. Run: pip install mysql-connector-python")

# ---------------- MySQL settings: change the password to yours ----------------
DB_CONFIG = {"host": "localhost", "user": "root", "password": "Binsi@412p"}
DB_NAME = "contact_db"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?\d{10,13}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{0,99}$")
CATEGORIES = ["Friend", "Family", "Faculty", "Student", "Work", "Other"]
SEARCH_FIELDS = {"Name": "name", "Email": "email", "Phone": "phone"}   # whitelist
SORT_FIELDS = {"Name": "name", "Email": "email", "Phone": "phone", "Category": "category"}


class ContactDB:
    """All MySQL work lives here. Every query uses %s parameters (no string joining of user input)."""

    def __init__(self):
        server = mysql.connector.connect(**DB_CONFIG)
        cur = server.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cur.close()
        server.close()
        self.conn = mysql.connector.connect(database=DB_NAME, **DB_CONFIG)
        cur = self.conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS Contact (
                   id INT AUTO_INCREMENT PRIMARY KEY,
                   name VARCHAR(100) NOT NULL,
                   email VARCHAR(150) NOT NULL UNIQUE,
                   phone VARCHAR(20) NOT NULL,
                   category VARCHAR(30) NOT NULL,
                   notes TEXT,
                   INDEX idx_name (name),
                   INDEX idx_phone (phone)
               )"""
        )
        self.conn.commit()
        cur.close()

    def _run(self, sql, params=(), fetch=False, many=False):
        cur = self.conn.cursor()
        try:
            if many:
                cur.executemany(sql, params)
            else:
                cur.execute(sql, params)
            rows = cur.fetchall() if fetch else None
            self.conn.commit()
            return rows
        except Error:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def add(self, name, email, phone, category, notes):
        self._run("INSERT INTO Contact (name, email, phone, category, notes) "
                  "VALUES (%s, %s, %s, %s, %s)", (name, email, phone, category, notes))

    def update(self, cid, name, email, phone, category, notes):
        self._run("UPDATE Contact SET name=%s, email=%s, phone=%s, category=%s, notes=%s "
                  "WHERE id=%s", (name, email, phone, category, notes, cid))

    def delete(self, cid):
        self._run("DELETE FROM Contact WHERE id=%s", (cid,))

    def search(self, field, text, sort_by, direction):
        """field and sort_by come from whitelists, so they are safe to put in the SQL text."""
        col = SEARCH_FIELDS.get(field, "name")
        order = SORT_FIELDS.get(sort_by, "name")
        way = "DESC" if direction == "DESC" else "ASC"
        sql = "SELECT id, name, email, phone, category, notes FROM Contact"
        params = ()
        if text:
            sql += f" WHERE {col} LIKE %s"
            params = (f"%{text}%",)
        sql += f" ORDER BY {order} {way}, id ASC"
        return self._run(sql, params, fetch=True)

    def add_samples(self, count=10000):
        rows = [(f"Sample User {i}", f"sample{i}@demo.edu", f"9{i:09d}", CATEGORIES[i % 6], "demo")
                for i in range(1, count + 1)]
        self._run("INSERT IGNORE INTO Contact (name, email, phone, category, notes) "
                  "VALUES (%s, %s, %s, %s, %s)", rows, many=True)


def validate(name, email, phone, category, notes):
    """Return cleaned values or raise ValueError with a message for the user."""
    name, email, phone, notes = name.strip(), email.strip().lower(), phone.strip(), notes.strip()
    if not NAME_RE.match(name):
        raise ValueError("Name must start with a letter and use only letters, spaces . ' -")
    if len(email) > 150 or not EMAIL_RE.match(email):
        raise ValueError("Enter a valid email, e.g. asha@adit.edu")
    if not PHONE_RE.match(phone):
        raise ValueError("Phone must be 10 to 13 digits (optional + at the start)")
    if category not in CATEGORIES:
        raise ValueError("Choose a category from the list")
    if len(notes) > 1000:
        raise ValueError("Notes can be at most 1000 characters")
    return name, email, phone, category, notes


class ContactApp:
    def __init__(self, root, db):
        self.root, self.db = root, db
        self.rows = []              # rows currently shown (same order as the Listbox)
        self.selected_id = None
        root.title("Contact Manager (MySQL)")
        self.build_menu()
        self.build_ui()
        self.refresh()

    # ---------- layout ----------
    def build_menu(self):
        bar = tk.Menu(self.root)
        file_menu = tk.Menu(bar, tearoff=0)
        file_menu.add_command(label="Clear form", command=self.clear_form)
        file_menu.add_command(label="Add 10,000 test contacts", command=self.load_samples)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        bar.add_cascade(label="File", menu=file_menu)
        sort_menu = tk.Menu(bar, tearoff=0)
        for label in SORT_FIELDS:
            sort_menu.add_command(label=f"Sort by {label}", command=lambda l=label: self.set_sort(l))
        bar.add_cascade(label="Sort", menu=sort_menu)
        self.root.config(menu=bar)

    def build_ui(self):
        f = ttk.Frame(self.root, padding=8)
        f.pack(fill="both", expand=True)
        self.v_name, self.v_email, self.v_phone = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_cat = tk.StringVar(value=CATEGORIES[0])
        self.v_search, self.v_field = tk.StringVar(), tk.StringVar(value="Name")
        self.v_sort, self.v_dir = tk.StringVar(value="Name"), tk.StringVar(value="ASC")

        ttk.Label(f, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_name, width=30).grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="Email").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_email, width=30).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="Phone").grid(row=2, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_phone, width=30).grid(row=2, column=1, sticky="w")
        ttk.Label(f, text="Category").grid(row=3, column=0, sticky="w")
        ttk.Combobox(f, textvariable=self.v_cat, values=CATEGORIES, state="readonly",
                     width=27).grid(row=3, column=1, sticky="w")
        ttk.Label(f, text="Notes").grid(row=4, column=0, sticky="nw")
        self.txt_notes = tk.Text(f, width=30, height=4)
        self.txt_notes.grid(row=4, column=1, sticky="w")

        bar = ttk.Frame(f)
        bar.grid(row=5, column=0, columnspan=2, pady=6)
        for text, cmd in (("Add", self.add_contact), ("Update", self.update_contact),
                          ("Delete", self.delete_contact), ("Clear", self.clear_form)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=3)

        box = ttk.LabelFrame(f, text="Search and sort", padding=6)
        box.grid(row=0, column=2, rowspan=6, padx=12, sticky="n")
        ttk.Label(box, text="Search in").grid(row=0, column=0, sticky="w")
        ttk.Combobox(box, textvariable=self.v_field, values=list(SEARCH_FIELDS),
                     state="readonly", width=10).grid(row=0, column=1)
        e = ttk.Entry(box, textvariable=self.v_search, width=24)
        e.grid(row=1, column=0, columnspan=2, pady=4)
        e.bind("<Return>", lambda _e: self.refresh())
        ttk.Button(box, text="Search", command=self.refresh).grid(row=2, column=0)
        ttk.Button(box, text="Show all", command=self.show_all).grid(row=2, column=1)
        ttk.Label(box, text="Sort by").grid(row=3, column=0, sticky="w", pady=(8, 0))
        cb = ttk.Combobox(box, textvariable=self.v_sort, values=list(SORT_FIELDS),
                          state="readonly", width=10)
        cb.grid(row=3, column=1, pady=(8, 0))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Radiobutton(box, text="Ascending", variable=self.v_dir, value="ASC",
                        command=self.refresh).grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(box, text="Descending", variable=self.v_dir, value="DESC",
                        command=self.refresh).grid(row=5, column=0, columnspan=2, sticky="w")

        self.lbl_count = ttk.Label(f, text="")
        self.lbl_count.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.listbox = tk.Listbox(f, width=105, height=14, font=("Consolas", 10), exportselection=False)
        sb = ttk.Scrollbar(f, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.grid(row=7, column=0, columnspan=3, sticky="nsew")
        sb.grid(row=7, column=3, sticky="ns")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        f.rowconfigure(7, weight=1)
        f.columnconfigure(2, weight=1)

    # ---------- helpers ----------
    def form_values(self):
        return validate(self.v_name.get(), self.v_email.get(), self.v_phone.get(),
                        self.v_cat.get(), self.txt_notes.get("1.0", "end-1c"))

    def clear_form(self):
        self.selected_id = None
        for v in (self.v_name, self.v_email, self.v_phone):
            v.set("")
        self.v_cat.set(CATEGORIES[0])
        self.txt_notes.delete("1.0", "end")
        self.listbox.selection_clear(0, "end")

    def set_sort(self, label):
        self.v_sort.set(label)
        self.refresh()

    def show_all(self):
        self.v_search.set("")
        self.refresh()

    def db_error(self, e):
        if isinstance(e, IntegrityError):
            messagebox.showerror("Duplicate email", "A contact with this email already exists.")
        else:
            messagebox.showerror("Database error", str(e))

    # ---------- actions ----------
    def add_contact(self):
        try:
            values = self.form_values()
        except ValueError as e:
            return messagebox.showerror("Invalid input", str(e))
        try:
            self.db.add(*values)
        except Error as e:
            return self.db_error(e)
        self.clear_form()
        self.refresh()
        messagebox.showinfo("Contact", "Record inserted.")

    def update_contact(self):
        if self.selected_id is None:
            return messagebox.showwarning("Update", "Select a contact from the list first.")
        try:
            values = self.form_values()
        except ValueError as e:
            return messagebox.showerror("Invalid input", str(e))
        try:
            self.db.update(self.selected_id, *values)
        except Error as e:
            return self.db_error(e)
        self.refresh()
        messagebox.showinfo("Contact", "Record updated.")

    def delete_contact(self):
        if self.selected_id is None:
            return messagebox.showwarning("Delete", "Select a contact from the list first.")
        if not messagebox.askyesno("Delete", "Delete the selected contact?"):
            return
        try:
            self.db.delete(self.selected_id)
        except Error as e:
            return self.db_error(e)
        self.clear_form()
        self.refresh()

    def load_samples(self):
        try:
            self.db.add_samples(10000)
        except Error as e:
            return self.db_error(e)
        self.refresh()
        messagebox.showinfo("Test data", "10,000 test contacts added.")

    def refresh(self):
        try:
            self.rows = self.db.search(self.v_field.get(), self.v_search.get().strip(),
                                       self.v_sort.get(), self.v_dir.get())
        except Error as e:
            return self.db_error(e)
        self.listbox.delete(0, "end")
        for cid, name, email, phone, cat, _notes in self.rows:
            self.listbox.insert("end", f"{cid:<6}{name:<24}{email:<32}{phone:<16}{cat}")
        self.lbl_count.config(text=f"{len(self.rows)} contact(s) shown")

    def on_select(self, _event):
        sel = self.listbox.curselection()
        if not sel:
            return
        cid, name, email, phone, cat, notes = self.rows[sel[0]]
        self.selected_id = cid
        self.v_name.set(name)
        self.v_email.set(email)
        self.v_phone.set(phone)
        self.v_cat.set(cat)
        self.txt_notes.delete("1.0", "end")
        self.txt_notes.insert("1.0", notes or "")


if __name__ == "__main__":
    try:
        database = ContactDB()
    except Error as err:
        raise SystemExit(f"Cannot connect to MySQL: {err}\nCheck that MySQL is running and the password in DB_CONFIG is correct.")
    window = tk.Tk()
    ContactApp(window, database)
    window.mainloop()