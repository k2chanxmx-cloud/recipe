from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date, timedelta

app = Flask(__name__)

DB_NAME = "recipes.db"

CATEGORIES = [
    "シチュー・カレー系",
    "煮物",
    "炒め物",
    "焼き物",
    "揚げ物",
    "丼・ごはん系",
    "麺系",
    "鍋・スープ系",
    "手抜き系",
    "未分類",
]

EFFORT_LEVELS = [
    "★1 死んでても作れる",
    "★2 まあ作れる",
    "★3 元気な日だけ",
    "★4 休日専用",
]


def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '未分類',
            ingredients TEXT,
            steps TEXT,
            time_minutes INTEGER,
            effort_level TEXT,
            is_two_days INTEGER DEFAULT 0,
            husband_favorite INTEGER DEFAULT 0,
            memo TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS meal_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_date TEXT NOT NULL,
            recipe_id INTEGER,
            note TEXT,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id)
        )
    """)

    conn.commit()
    conn.close()


@app.before_request
def before_request():
    init_db()


@app.route("/")
def index():
    keyword = request.args.get("keyword", "")
    category = request.args.get("category", "")

    conn = get_conn()
    cur = conn.cursor()

    sql = "SELECT * FROM recipes WHERE 1=1"
    params = []

    if keyword:
        sql += " AND title LIKE ?"
        params.append(f"%{keyword}%")

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY category, title"

    recipes = cur.execute(sql, params).fetchall()
    conn.close()

    return render_template(
        "index.html",
        recipes=recipes,
        categories=CATEGORIES,
        keyword=keyword,
        selected_category=category,
    )


@app.route("/recipes/new", methods=["GET", "POST"])
def recipe_new():
    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        ingredients = request.form.get("ingredients")
        steps = request.form.get("steps")
        time_minutes = request.form.get("time_minutes") or None
        effort_level = request.form.get("effort_level")
        is_two_days = 1 if request.form.get("is_two_days") else 0
        husband_favorite = 1 if request.form.get("husband_favorite") else 0
        memo = request.form.get("memo")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO recipes
            (title, category, ingredients, steps, time_minutes, effort_level, is_two_days, husband_favorite, memo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, category, ingredients, steps, time_minutes,
            effort_level, is_two_days, husband_favorite, memo
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    return render_template(
        "recipe_form.html",
        categories=CATEGORIES,
        effort_levels=EFFORT_LEVELS,
        recipe=None,
    )


@app.route("/recipes/<int:recipe_id>")
def recipe_detail(recipe_id):
    conn = get_conn()
    recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
    conn.close()

    if recipe is None:
        return "レシピが見つかりません", 404

    return render_template("recipe_detail.html", recipe=recipe)


@app.route("/recipes/<int:recipe_id>/edit", methods=["GET", "POST"])
def recipe_edit(recipe_id):
    conn = get_conn()
    recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()

    if recipe is None:
        conn.close()
        return "レシピが見つかりません", 404

    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        ingredients = request.form.get("ingredients")
        steps = request.form.get("steps")
        time_minutes = request.form.get("time_minutes") or None
        effort_level = request.form.get("effort_level")
        is_two_days = 1 if request.form.get("is_two_days") else 0
        husband_favorite = 1 if request.form.get("husband_favorite") else 0
        memo = request.form.get("memo")

        conn.execute("""
            UPDATE recipes
            SET title=?, category=?, ingredients=?, steps=?, time_minutes=?,
                effort_level=?, is_two_days=?, husband_favorite=?, memo=?
            WHERE id=?
        """, (
            title, category, ingredients, steps, time_minutes,
            effort_level, is_two_days, husband_favorite, memo, recipe_id
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    conn.close()

    return render_template(
        "recipe_form.html",
        categories=CATEGORIES,
        effort_levels=EFFORT_LEVELS,
        recipe=recipe,
    )


@app.route("/recipes/<int:recipe_id>/delete", methods=["POST"])
def recipe_delete(recipe_id):
    conn = get_conn()
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/meal-plan", methods=["GET", "POST"])
def meal_plan():
    today = date.today()
    start_date = today - timedelta(days=today.weekday())

    if request.method == "POST":
        conn = get_conn()
        cur = conn.cursor()

        for i in range(7):
            d = (start_date + timedelta(days=i)).isoformat()
            recipe_id = request.form.get(f"recipe_{i}") or None
            note = request.form.get(f"note_{i}")

            cur.execute("DELETE FROM meal_plans WHERE plan_date = ?", (d,))
            cur.execute("""
                INSERT INTO meal_plans (plan_date, recipe_id, note)
                VALUES (?, ?, ?)
            """, (d, recipe_id, note))

        conn.commit()
        conn.close()
        return redirect(url_for("meal_plan"))

    conn = get_conn()
    recipes = conn.execute("SELECT * FROM recipes ORDER BY category, title").fetchall()
    plans = conn.execute("""
        SELECT mp.*, r.title AS recipe_title
        FROM meal_plans mp
        LEFT JOIN recipes r ON mp.recipe_id = r.id
    """).fetchall()
    conn.close()

    plan_map = {p["plan_date"]: p for p in plans}

    week = []
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    for i in range(7):
        d = start_date + timedelta(days=i)
        week.append({
            "index": i,
            "date": d,
            "weekday": weekdays[i],
            "plan": plan_map.get(d.isoformat())
        })

    return render_template("meal_plan.html", week=week, recipes=recipes)


@app.route("/shopping-list")
def shopping_list():
    conn = get_conn()
    rows = conn.execute("""
        SELECT mp.plan_date, r.title, r.ingredients
        FROM meal_plans mp
        JOIN recipes r ON mp.recipe_id = r.id
        ORDER BY mp.plan_date
    """).fetchall()
    conn.close()

    return render_template("shopping_list.html", rows=rows)


if __name__ == "__main__":
    app.run(debug=True)