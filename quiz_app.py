import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import random
from datetime import datetime
import requests
import html

# ----------------- Database Setup -----------------
def setup_db():
    conn = sqlite3.connect("quiz_app.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

setup_db()

# ----------------- Globals -----------------
current_user = None
score = 0
current_q = 0
shuffled_questions = []
selected_category = None
user_answers = {}
timer_id = None
time_left = 20
dark_mode = False
canvas_timer = None
arc_timer = None
text_timer = None

# ----------------- Category Map -----------------
category_map = {
    "General Knowledge": 9,
    "Science": 17,
    "Sports": 21,
    "History": 23,
}

# ----------------- Fetch Questions -----------------
def fetch_questions_from_api(category_id, amount=5):
    url = f"https://opentdb.com/api.php?amount={amount}&category={category_id}&type=multiple"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except Exception as e:
        print("API request failed:", e)
        return []

    questions = []
    if data["response_code"] == 0:
        for item in data["results"]:
            question = html.unescape(item["question"])
            correct = html.unescape(item["correct_answer"])
            incorrect = [html.unescape(ans) for ans in item["incorrect_answers"]]
            options = incorrect + [correct]
            random.shuffle(options)
            questions.append((question, options, correct))
    return questions

# ----------------- Save Score -----------------
def save_score(username, category, score):
    conn = sqlite3.connect("quiz_app.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO scores (username, category, score, timestamp) VALUES (?, ?, ?, ?)",
                   (username, category, score, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# ----------------- Utility to center window -----------------
def center_window(win, width, height):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (height / 2))
    win.geometry(f"{width}x{height}+{x}+{y}")

# ----------------- Registration -----------------
def open_register():
    global reg_win, entry_reg_username, entry_reg_password, entry_reg_repeat
    reg_win = tk.Toplevel(login_win)
    reg_win.title("Register")
    reg_win.configure(bg="#e6f7ff")
    center_window(reg_win, 450, 400)

    container = tk.Frame(reg_win, bg=reg_win["bg"])
    container.pack(expand=True)

    tk.Label(container, text="Username:", font=("Arial", 16), bg=reg_win["bg"]).pack(pady=10)
    entry_reg_username = tk.Entry(container, font=("Arial", 16))
    entry_reg_username.pack(pady=5)

    tk.Label(container, text="Password:", font=("Arial", 16), bg=reg_win["bg"]).pack(pady=10)
    entry_reg_password = tk.Entry(container, font=("Arial", 16), show="*")
    entry_reg_password.pack(pady=5)

    tk.Label(container, text="Repeat Password:", font=("Arial", 16), bg=reg_win["bg"]).pack(pady=10)
    entry_reg_repeat = tk.Entry(container, font=("Arial", 16), show="*")
    entry_reg_repeat.pack(pady=5)

    btn_register = tk.Button(container, text="Register", font=("Arial", 16),
                             command=register_user, bg="#2196f3", fg="black")
    btn_register.pack(pady=15)

def register_user():
    username = entry_reg_username.get()
    password = entry_reg_password.get()
    repeat_password = entry_reg_repeat.get()

    if not username or not password or not repeat_password:
        messagebox.showwarning("Input Error", "Please fill all fields")
        return
    if password != repeat_password:
        messagebox.showerror("Error", "Passwords do not match")
        return

    conn = sqlite3.connect("quiz_app.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                       (username, password))
        conn.commit()
        messagebox.showinfo("Success", "Registration successful! Please login.")
        reg_win.destroy()
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "Username already exists.")
    conn.close()

# ----------------- Login -----------------
def login_user():
    global current_user
    username = entry_username.get()
    password = entry_password.get()
    conn = sqlite3.connect("quiz_app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        current_user = username
        messagebox.showinfo("Login", f"Welcome {username}!")
        login_win.destroy()
        open_dashboard()
    else:
        messagebox.showerror("Error", "Invalid username or password")

# ----------------- Countdown Timer -----------------
def countdown():
    global time_left, timer_id
    if time_left > 0:
        time_left -= 1
        canvas_timer.itemconfig(text_timer, text=f"{time_left}s")

        extent = (time_left / 20) * 360
        canvas_timer.itemconfig(arc_timer, extent=extent)

        if time_left > 10:
            color = "green"
        elif time_left > 5:
            color = "orange"
        else:
            color = "red"

        canvas_timer.itemconfig(arc_timer, outline=color)
        canvas_timer.itemconfig(text_timer, fill=color)

        timer_id = quiz_win.after(1000, countdown)
    else:
        if current_q not in user_answers:
            user_answers[current_q] = None
        next_question()

# ----------------- Quiz Functions -----------------
def select_answer(opt):
    global user_answers
    user_answers[current_q] = opt
    for btn in option_buttons:
        text_opt = btn["text"][2:]
        if text_opt == opt:
            btn.config(text=f"☑ {opt}", relief="sunken", bg="lightblue")
        else:
            btn.config(text=f"☐ {text_opt}", relief="raised", bg="SystemButtonFace")

def load_question():
    global time_left, timer_id
    q, options, answer = shuffled_questions[current_q]
    lbl_question.config(text=f"Q{current_q+1}: {q}")
    selected = user_answers.get(current_q)
    for i, btn in enumerate(option_buttons):
        opt_text = options[i]
        if selected == opt_text:
            btn.config(text=f"☑ {opt_text}", relief="sunken", bg="lightblue",
                       command=lambda opt=opt_text: select_answer(opt))
        else:
            btn.config(text=f"☐ {opt_text}", relief="raised", bg="SystemButtonFace",
                       command=lambda opt=opt_text: select_answer(opt))
    time_left = 20
    canvas_timer.itemconfig(text_timer, text=f"{time_left}s")
    canvas_timer.itemconfig(arc_timer, extent=360, outline="green")
    if timer_id:
        quiz_win.after_cancel(timer_id)
    timer_id = quiz_win.after(1000, countdown)

def next_question():
    global current_q
    if current_q < len(shuffled_questions) - 1:
        current_q += 1
        load_question()
    else:
        finish_quiz()

def prev_question():
    global current_q
    if current_q > 0:
        current_q -= 1
        load_question()

def finish_quiz():
    global score
    score = 0
    for i, (q, options, answer) in enumerate(shuffled_questions):
        if user_answers.get(i) == answer:
            score += 1
    save_score(current_user, selected_category, score)
    messagebox.showinfo("Quiz Finished", f"Your Score: {score}/{len(shuffled_questions)}")
    quiz_win.destroy()

def start_quiz():
    global quiz_win, lbl_question, option_buttons, current_q, score, shuffled_questions
    global selected_category, user_answers, timer_id, time_left, canvas_timer, arc_timer, text_timer
    selected_category = category_var.get()
    if not selected_category:
        messagebox.showwarning("No Category", "Please select a category!")
        return
    
    category_id = category_map.get(selected_category)
    if not category_id:
        messagebox.showerror("Error", "Invalid category selected.")
        return
    
    shuffled_questions = fetch_questions_from_api(category_id, amount=5)
    if not shuffled_questions:
        messagebox.showerror("Error", "Failed to fetch questions from API.")
        return

    quiz_win = tk.Toplevel(dashboard_win)
    quiz_win.title("Quiz")
    quiz_win.configure(bg="#f0f8ff" if not dark_mode else "#2c3e50")
    center_window(quiz_win, 750, 550)
    
    current_q = 0
    score = 0
    user_answers = {}
    
    lbl_title = tk.Label(quiz_win, text=f"{selected_category} Quiz", font=("Arial", 24, "bold"),
                         bg=quiz_win["bg"], fg="white" if dark_mode else "#333")
    lbl_title.pack(pady=15)

    canvas_timer = tk.Canvas(quiz_win, width=120, height=120, bg=quiz_win["bg"], highlightthickness=0)
    canvas_timer.pack(pady=10)
    arc_timer = canvas_timer.create_arc(10, 10, 110, 110, start=90, extent=360, style="arc", outline="green", width=10)
    text_timer = canvas_timer.create_text(60, 60, text="20s", font=("Arial", 16, "bold"), fill="black")

    lbl_question = tk.Label(quiz_win, text="", font=("Arial", 20), wraplength=650, justify="center", bg=quiz_win["bg"],
                            fg="white" if dark_mode else "#333")
    lbl_question.pack(pady=25)
    
    option_buttons = []
    for i in range(4):
        btn = tk.Button(quiz_win, text="", width=45, font=("Arial", 18), bg="white")
        btn.pack(pady=10)
        option_buttons.append(btn)
    
    nav_frame = tk.Frame(quiz_win, bg=quiz_win["bg"])
    nav_frame.pack(pady=20)
    tk.Button(nav_frame, text="Previous", font=("Arial", 16), command=prev_question, bg="#dcdcdc").grid(row=0, column=0, padx=20)
    tk.Button(nav_frame, text="Next", font=("Arial", 16), command=next_question, bg="#dcdcdc").grid(row=0, column=1, padx=20)
    tk.Button(nav_frame, text="Finish Quiz", font=("Arial", 16), command=finish_quiz, bg="#ffcccb").grid(row=0, column=2, padx=20)
    
    load_question()

# ----------------- Leaderboard -----------------
def show_leaderboard():
    conn = sqlite3.connect("quiz_app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, category, score, timestamp FROM scores ORDER BY score DESC")
    results = cursor.fetchall()
    conn.close()
    lb_win = tk.Toplevel(dashboard_win)
    lb_win.title("Leaderboard")
    lb_win.configure(bg="#2c3e50" if dark_mode else "#e6f7ff")
    center_window(lb_win, 500, 400)
    
    tk.Label(lb_win, text="Leaderboard", font=("Arial", 22, "bold"), bg=lb_win["bg"], fg="white" if dark_mode else "#333").pack(pady=15)
    if results:
        for row in results:
            tk.Label(lb_win, text=f"{row[0]} ({row[1]}) : {row[2]} pts ({row[3]})",
                     font=("Arial", 14), bg=lb_win["bg"], fg="white" if dark_mode else "#000").pack()
    else:
        tk.Label(lb_win, text="No scores available yet!", font=("Arial", 14), bg=lb_win["bg"], fg="white" if dark_mode else "#000").pack()

# ----------------- My Scores -----------------
def show_my_scores():
    if not current_user:
        messagebox.showwarning("Not Logged In", "Please log in first!")
        return
    conn = sqlite3.connect("quiz_app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT category, score, timestamp FROM scores WHERE username=? ORDER BY timestamp DESC", (current_user,))
    results = cursor.fetchall()
    conn.close()
    ms_win = tk.Toplevel(dashboard_win)
    ms_win.title(f"{current_user}'s Scores")
    ms_win.configure(bg="#2c3e50" if dark_mode else "#f0f8ff")
    center_window(ms_win, 400, 350)
    
    tk.Label(ms_win, text=f"{current_user}'s Scores", font=("Arial", 20, "bold"),
             bg=ms_win["bg"], fg="white" if dark_mode else "#333").pack(pady=15)
    if results:
        for row in results:
            tk.Label(ms_win, text=f"{row[0]}: {row[1]} pts on {row[2]}",
                     font=("Arial", 14), bg=ms_win["bg"], fg="white" if dark_mode else "#000").pack()
    else:
        tk.Label(ms_win, text="No scores available yet!", font=("Arial", 14), bg=ms_win["bg"], fg="white" if dark_mode else "#000").pack()

# ----------------- Toggle Dark Mode -----------------
def toggle_dark_mode():
    global dark_mode
    dark_mode = not dark_mode
    bg_color = "#2c3e50" if dark_mode else "#f0f8ff"
    fg_color = "white" if dark_mode else "#333"
    dashboard_win.configure(bg=bg_color)
    for widget in dashboard_win.winfo_children():
        try:
            widget.configure(bg=bg_color, fg=fg_color)
        except:
            pass

# ----------------- Logout -----------------
def logout():
    global current_user
    current_user = None
    dashboard_win.destroy()
    open_login()

# ----------------- Open Dashboard -----------------
def open_dashboard():
    global dashboard_win, category_var
    dashboard_win = tk.Tk()
    dashboard_win.title(f"Dashboard - {current_user}")
    dashboard_win.configure(bg="#f0f8ff")
    center_window(dashboard_win, 600, 450)

    container = tk.Frame(dashboard_win, bg=dashboard_win["bg"])
    container.pack(expand=True)

    tk.Label(container, text=f"Welcome, {current_user}!", font=("Arial", 24, "bold"),
             bg=dashboard_win["bg"]).pack(pady=20)
    
    tk.Label(container, text="Select Quiz Category:", font=("Arial", 18), bg=dashboard_win["bg"]).pack(pady=10)
    
    category_var = tk.StringVar()
    categories = list(category_map.keys())
    dropdown = ttk.Combobox(container, values=categories, textvariable=category_var, state="readonly", font=("Arial", 16))
    dropdown.pack(pady=10)
    dropdown.current(0)

    tk.Button(container, text="Start Quiz", font=("Arial", 18), bg="#4caf50", fg="black", command=start_quiz).pack(pady=15)
    tk.Button(container, text="My Scores", font=("Arial", 16), command=show_my_scores).pack(pady=8)
    tk.Button(container, text="Leaderboard", font=("Arial", 16), command=show_leaderboard).pack(pady=8)
    tk.Button(container, text="Toggle Dark Mode", font=("Arial", 16), command=toggle_dark_mode).pack(pady=8)
    tk.Button(container, text="Logout", font=("Arial", 16), fg="red", command=logout).pack(pady=20)
    
    dashboard_win.mainloop()

# ----------------- Open Login -----------------
def open_login():
    global login_win, entry_username, entry_password
    login_win = tk.Tk()
    login_win.title("Login / Register")
    login_win.configure(bg="#e6f7ff")
    center_window(login_win, 450, 350)
    
    container = tk.Frame(login_win, bg=login_win["bg"])
    container.pack(expand=True)

    tk.Label(container, text="Username:", font=("Arial", 16), bg=login_win["bg"]).pack(pady=10)
    entry_username = tk.Entry(container, font=("Arial", 16))
    entry_username.pack(pady=5)
    
    tk.Label(container, text="Password:", font=("Arial", 16), bg=login_win["bg"]).pack(pady=10)
    entry_password = tk.Entry(container, font=("Arial", 16), show="*")
    entry_password.pack(pady=5)
    
    tk.Button(container, text="Login", font=("Arial", 16), command=login_user, bg="#4caf50", fg="black").pack(pady=15)
    
    tk.Label(container, text="Don't have an account?", font=("Arial", 14), bg=login_win["bg"]).pack(pady=5)
    tk.Button(container, text="Register", font=("Arial", 16), command=open_register, bg="#2196f3", fg="black").pack(pady=5)
    
    login_win.mainloop()

# ----------------- Run App -----------------
if __name__ == "__main__":
    open_login()
