import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, colorchooser
from tkcalendar import Calendar, DateEntry
import sqlite3
from datetime import datetime, date
import re

DB_FILE = "tasks.db"
DEFAULT_PRIMARY_COLOR = "#FFA2B9"
DEFAULT_SECONDARY_COLOR = "#FFD5DF"
HEX_PATTERN = re.compile(r"^#([0-9A-Fa-f]{6})$")


def is_valid_hex(color):
    return bool(HEX_PATTERN.match(color or ""))


def adjust_color(color, amount=0.0):
    if not is_valid_hex(color):
        return color
    col = color.lstrip("#")
    r, g, b = (int(col[i:i+2], 16) for i in (0, 2, 4))
    def clamp(Channel):
        return max(0, min(255, int(round(Channel))))
    if amount >= 0:
        r = clamp(r + (255 - r) * amount)
        g = clamp(g + (255 - g) * amount)
        b = clamp(b + (255 - b) * amount)
    else:
        factor = 1 - abs(amount)
        r = clamp(r * factor)
        g = clamp(g * factor)
        b = clamp(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def blend_colors(color_a, color_b, alpha=0.5):
    if not (is_valid_hex(color_a) and is_valid_hex(color_b)):
        return color_a
    alpha = max(0.0, min(1.0, alpha))
    ca = color_a.lstrip("#")
    cb = color_b.lstrip("#")
    r = int(int(ca[0:2], 16) * (1 - alpha) + int(cb[0:2], 16) * alpha)
    g = int(int(ca[2:4], 16) * (1 - alpha) + int(cb[2:4], 16) * alpha)
    b = int(int(ca[4:6], 16) * (1 - alpha) + int(cb[4:6], 16) * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        status TEXT,
        order_index INTEGER DEFAULT 0
    )
    """)
    conn.commit()

    cur.execute("PRAGMA table_info(tasks)")
    cols = [c[1] for c in cur.fetchall()]
    if "order_index" not in cols:
        try:
            cur.execute("ALTER TABLE tasks ADD COLUMN order_index INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def add_task_db(title, description, due_date, status="Pending", order_index=None):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    if order_index is None:
        cur.execute("INSERT INTO tasks (title, description, due_date, status) VALUES (?, ?, ?, ?)",
                    (title, description, due_date, status))
        conn.commit()
        last_id = cur.lastrowid
        try:
            cur.execute("UPDATE tasks SET order_index = ? WHERE id = ?", (last_id, last_id))
            conn.commit()
        except Exception:
            pass
    else:
        cur.execute("INSERT INTO tasks (title, description, due_date, status, order_index) VALUES (?, ?, ?, ?, ?)",
                    (title, description, due_date, status, order_index))
        conn.commit()
    conn.close()


def fetch_all_tasks_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, due_date, status, order_index FROM tasks")
    rows = cur.fetchall()
    conn.close()
    return rows


def fetch_tasks_by_statuses(statuses):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in statuses)
    query = f"SELECT id, title, description, due_date, status, order_index FROM tasks WHERE status IN ({placeholders})"
    cur.execute(query, tuple(statuses))
    rows = cur.fetchall()
    conn.close()
    return rows


def fetch_tasks_by_date(due_date_str):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, due_date, status, order_index FROM tasks WHERE due_date = ?", (due_date_str,))
    rows = cur.fetchall()
    conn.close()
    return rows


def update_task_status_db(task_id, new_status):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()
    conn.close()


def update_task_db(task_id, title, description, due_date, status):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    UPDATE tasks SET title = ?, description = ?, due_date = ?, status = ? WHERE id = ?
    """, (title, description, due_date, status, task_id))
    conn.commit()
    conn.close()


def delete_task_db(task_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def set_task_order_indices(pairs):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.executemany("UPDATE tasks SET order_index = ? WHERE id = ?", [(oi, tid) for (tid, oi) in pairs])
    conn.commit()
    conn.close()


def mark_missed_tasks():
    today = date.today()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, due_date, status FROM tasks WHERE status != 'Done' AND due_date IS NOT NULL")
    rows = cur.fetchall()
    to_update = []
    for r in rows:
        tid, due_s, status = r
        try:
            due_date_val = datetime.strptime(due_s, "%Y-%m-%d").date()
            if due_date_val < today and status != "Missed":
                to_update.append(tid)
        except Exception:
            continue
    if to_update:
        cur.executemany("UPDATE tasks SET status='Missed' WHERE id = ?", [(tid,) for tid in to_update])
        conn.commit()
    conn.close()


def center_window(win, w, h):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw // 2) - (w // 2)
    y = (sh // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


def iso_to_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


class TaskApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Task Management System")
        center_window(self.root, 1000, 700)
        self.root.minsize(900, 620)

        self.primary_color = DEFAULT_PRIMARY_COLOR
        self.secondary_color = DEFAULT_SECONDARY_COLOR
        self.surface_color = "#FFFFFF"
        self.surface_alt_color = "#F9F3F6"
        self.on_primary = "#311524"
        self.on_surface = "#2F2F2F"
        self.status_palette = {
            "Missed": adjust_color(self.primary_color, -0.2),
            "Pending": blend_colors(self.secondary_color, "#FFF0C2", 0.6),
            "Done": "#B8F2C8",
        }

        self.menu_buttons = []
        self.current_view = None
        self._todo_rows_container = []
        self._todo_load_rows_fn = None

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.font_body = tkfont.Font(family="Segoe UI", size=10)
        self.font_heading = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.font_title = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        self.font_subheading = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.font_button = tkfont.Font(family="Segoe UI", size=10, weight="bold")

        self.root.option_add("*Font", "{Segoe UI} 10")
        self.root.option_add("*TCombobox*Listbox*Font", "{Segoe UI} 10")
        self.root.option_add("*TCombobox*Font", "{Segoe UI} 10")
        self.root.configure(bg=self.secondary_color)

        self.header = ttk.Frame(self.root, padding=12, style="Header.TFrame")
        self.header.pack(fill="x", padx=12, pady=(12, 8))
        self.header_title = ttk.Label(self.header, text="🗂️ Task Management System", style="HeaderTitle.TLabel")
        self.header_title.pack(side="left")

        main = ttk.Frame(self.root, style="Surface.TFrame")
        main.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.menu = ttk.Frame(main, width=220, style="SideMenu.TFrame")
        self.menu.pack(side="left", fill="y", padx=(0, 12))
        self.menu.pack_propagate(False)

        self.content = ttk.Frame(main, style="Surface.TFrame")
        self.content.pack(side="left", fill="both", expand=True)

        self._add_menu_button("View Tasks", self.open_view_tasks)
        self._add_menu_button("Add Task", self.open_add_task)
        self._add_menu_button("Update Task", self.open_update_task)
        self._add_menu_button("To-Do List", self.open_todo_list)
        self._add_menu_button("Settings", self.open_settings)

        ttk.Separator(self.menu, orient="horizontal").pack(fill="x", pady=10)
        self._add_menu_button("Exit", self.on_exit, style_name="Secondary.TButton")

        init_db()
        self.apply_theme()
        self.show_welcome()

    def _add_menu_button(self, text, command, style_name="MaterialNav.TButton"):
        btn = ttk.Button(self.menu, text=text, command=command, style=style_name)
        btn.pack(fill="x", pady=6)
        self.menu_buttons.append(btn)
        return btn

    def apply_theme(self):
        self.surface_color = blend_colors(self.secondary_color, "#FFFFFF", 0.7)
        self.surface_alt_color = blend_colors(self.secondary_color, "#FFFFFF", 0.88)
        self.nav_color = blend_colors(self.secondary_color, "#FFFFFF", 0.55)
        self.nav_hover = adjust_color(self.nav_color, -0.05)
        self.checkbox_fill = adjust_color(self.primary_color, -0.18)
        self.status_palette = {
            "Missed": adjust_color(self.primary_color, -0.2),
            "Pending": blend_colors(self.secondary_color, "#FFF0C2", 0.55),
            "Done": "#B8F2C8",
        }
        self.root.configure(bg=self.secondary_color)

        style = self.style
        style.configure("TFrame", background=self.surface_color)
        style.configure("SideMenu.TFrame", background=self.secondary_color)
        style.configure("Header.TFrame", background=self.primary_color)
        style.configure("Surface.TFrame", background=self.surface_color)
        style.configure("Card.TFrame", background=self.surface_alt_color, relief="flat")
        style.configure("TLabel", background=self.surface_color, foreground=self.on_surface, font=self.font_body)
        style.configure("Heading.TLabel", background=self.surface_color, foreground=self.on_surface, font=self.font_heading)
        style.configure("HeaderTitle.TLabel", background=self.primary_color, foreground="#321725", font=self.font_title)

        style.configure("TButton", background=self.primary_color, foreground="#321725", padding=8, borderwidth=0, font=self.font_button)
        style.map("TButton",
                  background=[("active", adjust_color(self.primary_color, -0.1)), ("pressed", adjust_color(self.primary_color, -0.15))],
                  foreground=[("disabled", "#7A7A7A")])

        style.configure("Secondary.TButton", background=self.nav_color, foreground=self.on_surface, padding=8, borderwidth=0, font=self.font_body)
        style.map("Secondary.TButton",
                  background=[("active", self.nav_hover), ("pressed", adjust_color(self.nav_color, -0.08))])

        style.configure("MaterialNav.TButton", background=self.nav_color, foreground=self.on_surface, padding=10, borderwidth=0, font=self.font_body)
        style.map("MaterialNav.TButton",
                  background=[("active", self.nav_hover), ("pressed", adjust_color(self.nav_color, -0.08))])

        style.configure("TCombobox", fieldbackground=self.surface_color, foreground=self.on_surface, font=self.font_body)
        style.configure("Treeview",
                        background=self.surface_alt_color,
                        foreground=self.on_surface,
                        fieldbackground=self.surface_alt_color,
                        borderwidth=0,
                        font=self.font_body)
        style.configure("Treeview.Heading", font=self.font_button)
        style.map("Treeview",
                  background=[("selected", adjust_color(self.primary_color, -0.2))],
                  foreground=[("selected", "#FFFFFF")])

        if hasattr(self, "header"):
            self.header.configure(style="Header.TFrame")
        if hasattr(self, "menu"):
            self.menu.configure(style="SideMenu.TFrame")
        if hasattr(self, "content"):
            self.content.configure(style="Surface.TFrame")

    def clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def show_welcome(self):
        self.apply_theme()
        self.current_view = "welcome"
        self.clear_content()
        hero = ttk.Frame(self.content, padding=28, style="Card.TFrame")
        hero.pack(fill="x", padx=12, pady=40)
        ttk.Label(hero, text="Welcome!", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(hero,
                  text="Use the navigation menu to view, add, update, and prioritize your tasks.",
                  wraplength=740).pack(anchor="w", pady=(10, 0))

    def open_add_task(self):
        self.apply_theme()
        self.current_view = "add"
        self.clear_content()
        ttk.Label(self.content, text="Add New Task", style="Heading.TLabel").pack(anchor="w", padx=10, pady=(4, 12))

        card = ttk.Frame(self.content, padding=16, style="Card.TFrame")
        card.pack(padx=10, pady=4, fill="x", anchor="n")
        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Title:").grid(row=0, column=0, sticky="w", pady=6)
        title_entry = ttk.Entry(form, width=80)
        title_entry.grid(row=0, column=1, sticky="ew", pady=6, padx=8)

        ttk.Label(form, text="Description:").grid(row=1, column=0, sticky="nw", pady=6)
        desc_entry = tk.Text(form, width=60, height=6, relief="flat", bd=0, wrap="word")
        desc_entry.grid(row=1, column=1, sticky="ew", pady=6, padx=8)
        desc_entry.configure(bg=self.surface_alt_color, fg=self.on_surface, insertbackground=self.on_surface)

        ttk.Label(form, text="Due Date:").grid(row=2, column=0, sticky="w", pady=6)
        due_entry = DateEntry(form, width=18, date_pattern="yyyy-mm-dd")
        due_entry.grid(row=2, column=1, sticky="w", pady=6, padx=8)

        def save_task():
            title = title_entry.get().strip()
            desc = desc_entry.get("1.0", tk.END).strip()
            due = due_entry.get_date().strftime("%Y-%m-%d")
            if not title:
                messagebox.showwarning("Input Error", "Title is required.")
                return
            add_task_db(title, desc, due, "Pending")
            messagebox.showinfo("Saved", "Task added successfully.")
            self.open_view_tasks()

        btns = ttk.Frame(self.content, style="Surface.TFrame")
        btns.pack(pady=12)
        ttk.Button(btns, text="Save Task", command=save_task).pack(side="left", padx=6)
        ttk.Button(btns, text="Back", command=self.show_welcome, style="Secondary.TButton").pack(side="left", padx=6)

    def open_view_tasks(self):
        self.apply_theme()
        self.current_view = "view"
        self.clear_content()
        ttk.Label(self.content, text="View Tasks", style="Heading.TLabel").pack(anchor="w", padx=10, pady=(4, 10))

        mark_missed_tasks()

        top_frame = ttk.Frame(self.content, style="Surface.TFrame")
        top_frame.pack(fill="x", padx=6, pady=4)

        cal_frame = ttk.Frame(top_frame, style="Card.TFrame", padding=8)
        cal_frame.pack(side="left", padx=(0, 10))
        cal = Calendar(cal_frame, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.pack()

        legend = ttk.Frame(top_frame, style="Card.TFrame", padding=12)
        legend.pack(side="left", fill="y")
        ttk.Label(legend, text="Legend", font=self.font_subheading).pack(anchor="w", pady=(0, 8))
        legend_canvas = tk.Canvas(legend, width=160, height=110, highlightthickness=0, bd=0, bg=self.surface_alt_color)
        legend_canvas.pack(fill="both", expand=True)

        def draw_legend():
            legend_canvas.delete("all")
            colors = [
                ("Done", self.get_status_color("Done")),
                ("Pending", self.get_status_color("Pending")),
                ("Missed", self.get_status_color("Missed")),
            ]
            for idx, (label, fill) in enumerate(colors):
                y = 10 + idx * 30
                legend_canvas.create_rectangle(12, y, 40, y + 24, fill=fill, outline="")
                legend_canvas.create_text(52, y + 12, anchor="w", text=label, font=self.font_body, fill=self.on_surface)

        draw_legend()

        def refresh_calendar_markers():
            try:
                for event_id in cal.get_calevents():
                    cal.calevent_remove(event_id)
            except Exception:
                pass
            rows = fetch_all_tasks_db()
            for row in rows:
                _, title, _, due_s, status, _ = row
                if due_s:
                    try:
                        due_d = datetime.strptime(due_s, "%Y-%m-%d").date()
                        cal.calevent_create(due_d, f"{status}: {title}", status.lower())
                    except Exception:
                        continue
            for key in ("done", "pending", "missed"):
                try:
                    cal.tag_config(key, background=self.get_status_color(key.capitalize()), foreground=self.on_surface)
                except Exception:
                    pass

        right_frame = ttk.Frame(self.content, style="Surface.TFrame")
        right_frame.pack(fill="both", expand=True, padx=6, pady=(10, 0))
        ttk.Label(right_frame, text="Tasks for selected date", font=self.font_subheading).pack(anchor="w")
        sel_tasks_list = tk.Listbox(right_frame, height=6, bd=0, highlightthickness=0, bg=self.surface_alt_color, fg=self.on_surface,
                        selectbackground=adjust_color(self.primary_color, -0.2), font=self.font_body)
        sel_tasks_list.pack(fill="x", padx=4, pady=6)

        def show_tasks_for_selected_date(evt=None):
            sel_tasks_list.delete(0, tk.END)
            rows = fetch_tasks_by_date(cal.get_date())
            if not rows:
                sel_tasks_list.insert(tk.END, "No tasks for this date.")
                return
            for r in rows:
                tid, title, _, _, status, _ = r
                prefix = {"Done": "🟢", "Pending": "🟡", "Missed": "🔴"}.get(status, "⬜")
                sel_tasks_list.insert(tk.END, f"{prefix} [{tid}] {title} — {status}")

        cal.bind("<<CalendarSelected>>", show_tasks_for_selected_date)
        refresh_calendar_markers()
        cal.selection_set(date.today().strftime("%Y-%m-%d"))
        show_tasks_for_selected_date()

        ttk.Label(self.content, text="Pending & Missed Tasks", font=self.font_subheading).pack(anchor="w", padx=6, pady=(12, 4))
        list_frame = ttk.Frame(self.content, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 10))

        cols = ("ID", "Title", "Due Date", "Status")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            tree.heading(col, text=col)
        tree.column("ID", width=60, anchor="center")
        tree.column("Title", width=420, anchor="w")
        tree.column("Due Date", width=120, anchor="center")
        tree.column("Status", width=100, anchor="center")
        tree.pack(fill="both", expand=True, padx=4, pady=4)

        def populate_pending_missed():
            for item in tree.get_children():
                tree.delete(item)
            for r in fetch_tasks_by_statuses(["Pending", "Missed"]):
                tid, title, _, due_s, status, _ = r
                tree.insert("", "end", values=(tid, title, due_s, status), tags=(status.lower(),))
            tree.tag_configure("missed", background=self.get_status_color("Missed"))
            tree.tag_configure("pending", background=self.get_status_color("Pending"))

        populate_pending_missed()

        btns = ttk.Frame(self.content, style="Surface.TFrame")
        btns.pack(pady=8)

        def set_selected_status(new_status):
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection Required", "Please select a task.")
                return
            task_id = tree.item(sel[0])["values"][0]
            update_task_status_db(task_id, new_status)
            populate_pending_missed()
            refresh_calendar_markers()
            messagebox.showinfo("Updated", f"Task #{task_id} set to {new_status}.")

        def delete_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Selection Required", "Please select a task.")
                return
            task_id = tree.item(sel[0])["values"][0]
            if messagebox.askyesno("Confirm", f"Delete task #{task_id}?"):
                delete_task_db(task_id)
                populate_pending_missed()
                refresh_calendar_markers()

        ttk.Button(btns, text="Set to Done", command=lambda: set_selected_status("Done")).pack(side="left", padx=4)
        ttk.Button(btns, text="Set to Pending", command=lambda: set_selected_status("Pending")).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete Task", command=delete_selected, style="Secondary.TButton").pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh",
                   command=lambda: (mark_missed_tasks(), populate_pending_missed(), refresh_calendar_markers()),
                   style="Secondary.TButton").pack(side="left", padx=4)
        ttk.Button(btns, text="Back to Menu", command=self.show_welcome, style="Secondary.TButton").pack(side="right", padx=4)

    def open_update_task(self):
        self.apply_theme()
        self.current_view = "update"
        self.clear_content()
        ttk.Label(self.content, text="Update Task", style="Heading.TLabel").pack(anchor="w", padx=10, pady=(4, 10))

        main_frame = ttk.Frame(self.content, style="Surface.TFrame")
        main_frame.pack(fill="both", expand=True, padx=6, pady=6)

        left = ttk.Frame(main_frame, style="Card.TFrame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = ttk.Frame(main_frame, style="Card.TFrame")
        right.pack(side="left", fill="both", expand=True)

        cols = ("ID", "Title", "Due Date", "Status")
        tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("ID", width=60)
        tree.column("Title", width=260)
        tree.column("Due Date", width=120)
        tree.column("Status", width=90)
        tree.pack(fill="both", expand=True, padx=6, pady=6)

        def populate():
            for item in tree.get_children():
                tree.delete(item)
            for r in fetch_all_tasks_db():
                tree.insert("", "end", values=(r[0], r[1], r[3], r[4]))

        populate()

        ttk.Label(right, text="Edit Selected Task", style="Heading.TLabel").pack(anchor="w", pady=(8, 6), padx=8)
        form = ttk.Frame(right, style="Card.TFrame")
        form.pack(fill="both", expand=True, pady=6, padx=8)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="ID:").grid(row=0, column=0, sticky="w", pady=4)
        id_var = tk.StringVar()
        id_entry = ttk.Entry(form, textvariable=id_var, state="readonly", width=12)
        id_entry.grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Title:").grid(row=1, column=0, sticky="w", pady=4)
        title_var = tk.StringVar()
        title_entry = ttk.Entry(form, textvariable=title_var, width=48)
        title_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Description:").grid(row=2, column=0, sticky="nw", pady=4)
        desc_text = tk.Text(form, width=48, height=8, relief="flat", bd=0, wrap="word")
        desc_text.grid(row=2, column=1, sticky="ew", pady=4)
        desc_text.configure(bg=self.surface_alt_color, fg=self.on_surface, insertbackground=self.on_surface)

        ttk.Label(form, text="Due Date:").grid(row=3, column=0, sticky="w", pady=4)
        due_entry = DateEntry(form, width=18, date_pattern="yyyy-mm-dd")
        due_entry.grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Status:").grid(row=4, column=0, sticky="w", pady=4)
        status_var = tk.StringVar()
        status_box = ttk.Combobox(form, textvariable=status_var, values=["Pending", "Done", "Missed"], state="readonly", width=16)
        status_box.grid(row=4, column=1, sticky="w", pady=4)
        status_box.current(0)

        def on_tree_select(evt=None):
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])["values"]
            tid = item[0]
            rows = [r for r in fetch_all_tasks_db() if r[0] == tid]
            if not rows:
                return
            r = rows[0]
            id_var.set(r[0])
            title_var.set(r[1])
            desc_text.delete("1.0", tk.END)
            if r[2]:
                desc_text.insert(tk.END, r[2])
            if r[3]:
                try:
                    due_entry.set_date(datetime.strptime(r[3], "%Y-%m-%d").date())
                except Exception:
                    pass
            status_var.set(r[4])

        tree.bind("<<TreeviewSelect>>", on_tree_select)

        def save_changes():
            if not id_var.get():
                messagebox.showwarning("Select", "Please select a task to update.")
                return
            tid = int(id_var.get())
            title = title_var.get().strip()
            desc = desc_text.get("1.0", tk.END).strip()
            due = due_entry.get_date().strftime("%Y-%m-%d")
            status = status_var.get()
            if not title:
                messagebox.showwarning("Input Error", "Title is required.")
                return
            update_task_db(tid, title, desc, due, status)
            messagebox.showinfo("Saved", f"Task #{tid} updated.")
            populate()

        btns = ttk.Frame(right, style="Card.TFrame")
        btns.pack(pady=6, anchor="e", padx=8)
        ttk.Button(btns, text="Save Changes", command=save_changes).pack(side="left", padx=6)
        ttk.Button(btns, text="Refresh List", command=populate, style="Secondary.TButton").pack(side="left", padx=6)
        ttk.Button(btns, text="Back", command=self.show_welcome, style="Secondary.TButton").pack(side="left", padx=6)

    def open_todo_list(self):
        self.apply_theme()
        self.current_view = "todo"
        self.clear_content()
        ttk.Label(self.content, text="💖 To-Do List (Manual / Sort / Priority)", style="Heading.TLabel").pack(anchor="w", padx=10, pady=(4, 10))

        mark_missed_tasks()

        ctrl_frame = ttk.Frame(self.content, style="Surface.TFrame")
        ctrl_frame.pack(fill="x", padx=6, pady=(2, 8))
        ttk.Label(ctrl_frame, text="Order By:").pack(side="left", padx=(4, 6))
        order_var = tk.StringVar(value="Manual")
        order_box = ttk.Combobox(ctrl_frame, textvariable=order_var, values=["Manual", "Due Date Asc", "Due Date Desc", "Priority"], state="readonly", width=18)
        order_box.pack(side="left")
        order_box.current(0)

        ttk.Button(ctrl_frame, text="Save Order",
                   command=lambda: self.save_manual_order(getattr(self, "_todo_rows_container", []))).pack(side="left", padx=6)
        ttk.Button(ctrl_frame, text="Refresh", command=self.open_todo_list, style="Secondary.TButton").pack(side="left", padx=6)
        ttk.Button(ctrl_frame, text="Back", command=self.show_welcome, style="Secondary.TButton").pack(side="right", padx=6)

        container = ttk.Frame(self.content, style="Surface.TFrame")
        container.pack(fill="both", expand=True, padx=6, pady=6)

        canvas = tk.Canvas(container, highlightthickness=0, bg=self.surface_alt_color)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="Card.TFrame")
        scroll_frame.columnconfigure(0, weight=1)

        window_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def on_frame_config(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_config(event):
            canvas.itemconfig(window_id, width=event.width)

        scroll_frame.bind("<Configure>", on_frame_config)
        canvas.bind("<Configure>", on_canvas_config)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        rows_container = []
        status_priority = {"Missed": 0, "Pending": 1, "Done": 2}

        def regrid_rows():
            for idx, item in enumerate(rows_container):
                item["frame"].grid_configure(row=idx)

        def move_row_up(item):
            try:
                idx = rows_container.index(item)
            except ValueError:
                return
            if idx <= 0:
                return
            rows_container[idx], rows_container[idx - 1] = rows_container[idx - 1], rows_container[idx]
            regrid_rows()

        def move_row_down(item):
            try:
                idx = rows_container.index(item)
            except ValueError:
                return
            if idx >= len(rows_container) - 1:
                return
            rows_container[idx], rows_container[idx + 1] = rows_container[idx + 1], rows_container[idx]
            regrid_rows()

        def load_rows():
            for child in scroll_frame.winfo_children():
                child.destroy()
            rows_container.clear()

            raw = fetch_all_tasks_db()
            normed = []
            for r in raw:
                tid, title, desc, due_s, status, order_index = r
                ordering = order_index if order_index else tid
                due_dt = iso_to_date(due_s)
                normed.append((tid, title, desc, due_s, status, ordering, due_dt))

            mode = order_var.get()
            if mode == "Due Date Asc":
                normed.sort(key=lambda item: (status_priority.get(item[4], 3), item[6].toordinal() if item[6] else date.max.toordinal()))
            elif mode == "Due Date Desc":
                normed.sort(key=lambda item: (status_priority.get(item[4], 3), - (item[6].toordinal() if item[6] else date.min.toordinal())))
            elif mode == "Priority":
                normed.sort(key=lambda item: (status_priority.get(item[4], 3), item[6].toordinal() if item[6] else date.max.toordinal()))
            else:
                normed.sort(key=lambda item: item[5])

            for idx, (tid, title, desc, due_s, status, ordering, due_dt) in enumerate(normed):
                row_data = {
                    "tid": tid,
                    "title": title,
                    "description": desc,
                    "due_str": due_s,
                    "due_date": due_dt,
                    "status": status,
                }
                var = tk.BooleanVar(value=(status == "Done"))
                row_data["var"] = var

                row_frame = tk.Frame(scroll_frame, bg=self.surface_alt_color, bd=0, highlightthickness=1,
                                     highlightbackground=adjust_color(self.secondary_color, -0.2), padx=6, pady=8)
                row_frame.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)
                row_frame.columnconfigure(1, weight=1)
                row_data["frame"] = row_frame

                chk = tk.Checkbutton(row_frame, variable=var, bd=0, highlightthickness=0, onvalue=True, offvalue=False,
                                     bg=self.surface_alt_color, activebackground=self.surface_alt_color,
                                     selectcolor=self.checkbox_fill, width=2)
                chk.grid(row=0, column=0, sticky="w", padx=(4, 8))
                row_data["checkbutton"] = chk

                title_lbl = tk.Label(row_frame, text=title or "(Untitled Task)", anchor="w", bg=self.surface_alt_color,
                                     fg=self.on_surface, font=self.font_subheading)
                title_lbl.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
                row_data["title_lbl"] = title_lbl

                due_lbl = tk.Label(row_frame, text=due_s or "-", width=14, anchor="center", bg=self.surface_alt_color, fg=self.on_surface, font=self.font_body)
                due_lbl.grid(row=0, column=2, padx=6)
                row_data["due_lbl"] = due_lbl

                status_lbl = tk.Label(row_frame, text=status or "-", width=10, anchor="center", bg=self.surface_alt_color, fg=self.on_surface, font=self.font_body)
                status_lbl.grid(row=0, column=3, padx=6)
                row_data["status_lbl"] = status_lbl

                btns = tk.Frame(row_frame, bg=self.surface_alt_color)
                btns.grid(row=0, column=4, padx=6)
                row_data["button_frame"] = btns

                up_btn = ttk.Button(btns, text="↑", width=3, command=lambda item=row_data: move_row_up(item), style="Secondary.TButton")
                down_btn = ttk.Button(btns, text="↓", width=3, command=lambda item=row_data: move_row_down(item), style="Secondary.TButton")
                edit_btn = ttk.Button(btns, text="Edit", width=6, command=lambda task_id=tid: self.open_update_from_todo(task_id))
                up_btn.pack(side="left", padx=(0, 4))
                down_btn.pack(side="left", padx=(0, 4))
                edit_btn.pack(side="left")

                def on_check(item=row_data):
                    self._handle_checkbox_toggle(item)
                    if order_var.get() != "Manual":
                        load_rows()

                chk.configure(command=on_check)

                rows_container.append(row_data)
                self._apply_row_status_styles(row_data, status)

        order_box.bind("<<ComboboxSelected>>", lambda _evt: load_rows())
        load_rows()

        self._todo_rows_container = rows_container
        self._todo_load_rows_fn = load_rows

    def save_manual_order(self, rows_container):
        if not rows_container:
            messagebox.showinfo("No items", "Nothing to save.")
            return
        try:
            pairs = []
            for idx, item in enumerate(rows_container, start=1):
                pairs.append((item["tid"], idx))
            set_task_order_indices(pairs)
            messagebox.showinfo("Saved", "Manual order saved.")
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to save order: {exc}")

    def open_update_from_todo(self, task_id):
        self.open_update_task()
        tree = None
        for child in self.content.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, ttk.Treeview):
                    tree = sub
                    break
            if tree:
                break
        if not tree:
            return
        for item in tree.get_children():
            values = tree.item(item)["values"]
            if values and values[0] == task_id:
                tree.selection_set(item)
                tree.see(item)
                tree.event_generate("<<TreeviewSelect>>")
                break

    def open_settings(self):
        self.apply_theme()
        self.current_view = "settings"
        self.clear_content()
        ttk.Label(self.content, text="Theme Settings", style="Heading.TLabel").pack(anchor="w", padx=10, pady=(4, 10))

        card = ttk.Frame(self.content, padding=18, style="Card.TFrame")
        card.pack(fill="x", padx=12, pady=6)

        primary_var = tk.StringVar(value=self.primary_color)
        secondary_var = tk.StringVar(value=self.secondary_color)

        def update_preview():
            primary_preview.configure(bg=primary_var.get())
            secondary_preview.configure(bg=secondary_var.get())

        def choose_primary():
            color = colorchooser.askcolor(initialcolor=primary_var.get())[1]
            if color:
                primary_var.set(color)
                update_preview()

        def choose_secondary():
            color = colorchooser.askcolor(initialcolor=secondary_var.get())[1]
            if color:
                secondary_var.set(color)
                update_preview()

        def apply_changes():
            new_primary = primary_var.get().strip()
            new_secondary = secondary_var.get().strip()
            if not (is_valid_hex(new_primary) and is_valid_hex(new_secondary)):
                messagebox.showwarning("Invalid color", "Please provide valid hex colors like #FFA2B9.")
                return
            self.primary_color = new_primary
            self.secondary_color = new_secondary
            self.apply_theme()
            update_preview()
            messagebox.showinfo("Theme Updated", "Primary and secondary colors refreshed.")

        def reset_defaults():
            primary_var.set(DEFAULT_PRIMARY_COLOR)
            secondary_var.set(DEFAULT_SECONDARY_COLOR)
            apply_changes()

        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Primary Color:").pack(side="left")
        primary_entry = ttk.Entry(row, textvariable=primary_var, width=12)
        primary_entry.pack(side="left", padx=6)
        primary_preview = tk.Frame(row, width=48, height=24, bg=self.primary_color, bd=1, relief="ridge")
        primary_preview.pack(side="left", padx=6)
        primary_preview.pack_propagate(False)
        ttk.Button(row, text="Pick", command=choose_primary, style="Secondary.TButton").pack(side="left")

        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", pady=6)
        ttk.Label(row2, text="Secondary Color:").pack(side="left")
        secondary_entry = ttk.Entry(row2, textvariable=secondary_var, width=12)
        secondary_entry.pack(side="left", padx=6)
        secondary_preview = tk.Frame(row2, width=48, height=24, bg=self.secondary_color, bd=1, relief="ridge")
        secondary_preview.pack(side="left", padx=6)
        secondary_preview.pack_propagate(False)
        ttk.Button(row2, text="Pick", command=choose_secondary, style="Secondary.TButton").pack(side="left")

        action_row = ttk.Frame(card, style="Card.TFrame")
        action_row.pack(fill="x", pady=(12, 0))
        ttk.Button(action_row, text="Apply", command=apply_changes).pack(side="left", padx=4)
        ttk.Button(action_row, text="Reset Defaults", command=reset_defaults, style="Secondary.TButton").pack(side="left", padx=4)

        update_preview()

    def get_status_color(self, status):
        return self.status_palette.get(status, self.surface_alt_color)

    def _status_after_uncheck(self, due_date_value):
        today = date.today()
        if isinstance(due_date_value, date) and due_date_value < today:
            return "Missed"
        return "Pending"

    def _handle_checkbox_toggle(self, row):
        is_checked = bool(row["var"].get())
        new_status = "Done" if is_checked else self._status_after_uncheck(row.get("due_date"))
        update_task_status_db(row["tid"], new_status)
        row["status"] = new_status
        self._apply_row_status_styles(row, new_status)

    def _apply_row_status_styles(self, row, status):
        fill = self.get_status_color(status)
        border = adjust_color(fill, -0.25)
        row["frame"].configure(bg=fill, highlightbackground=border)
        row["title_lbl"].configure(bg=fill, fg=self.on_surface)
        row["due_lbl"].configure(bg=fill, fg=self.on_surface)
        row["status_lbl"].configure(bg=fill, fg=self.on_surface, text=status)
        row["button_frame"].configure(bg=fill)
        row["checkbutton"].configure(bg=fill, activebackground=fill, selectcolor=adjust_color(fill, -0.15))
        if row["var"].get() != (status == "Done"):
            row["var"].set(status == "Done")

    def on_exit(self):
        if messagebox.askyesno("Exit", "Exit application?"):
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = TaskApp(root)
    root.mainloop()
