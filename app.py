from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2
import psycopg2.extras
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

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
    "おやつ",
    "未分類",
]

EFFORT_LEVELS = [
    "★1 死んでても作れる",
    "★2 まあ作れる",
    "★3 元気な日だけ",
    "★4 休日専用",
]


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が設定されていません。.env または Render の環境変数を確認してください。")

    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


@app.route("/")
def index():
    keyword = request.args.get("keyword", "")
    category = request.args.get("category", "")

    conn = get_conn()
    cur = conn.cursor()

    sql = "SELECT * FROM recipes WHERE 1=1"
    params = []

    if keyword:
        sql += " AND title ILIKE %s"
        params.append(f"%{keyword}%")

    if category:
        sql += " AND category = %s"
        params.append(category)

    sql += " ORDER BY category, title"

    cur.execute(sql, params)
    recipes = cur.fetchall()

    cur.close()
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
        category = request.form.get("category") or "未分類"
        ingredients = request.form.get("ingredients")
        steps = request.form.get("steps")
        time_minutes = request.form.get("time_minutes") or None
        effort_level = request.form.get("effort_level")
        is_two_days = True if request.form.get("is_two_days") else False
        husband_favorite = True if request.form.get("husband_favorite") else False
        memo = request.form.get("memo")

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO recipes
            (title, category, ingredients, steps, time_minutes, effort_level, is_two_days, husband_favorite, memo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            title,
            category,
            ingredients,
            steps,
            time_minutes,
            effort_level,
            is_two_days,
            husband_favorite,
            memo
        ))

        conn.commit()
        cur.close()
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
    cur = conn.cursor()

    cur.execute("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
    recipe = cur.fetchone()

    cur.close()
    conn.close()

    if recipe is None:
        return "レシピが見つかりません", 404

    return render_template("recipe_detail.html", recipe=recipe)


@app.route("/recipes/<int:recipe_id>/edit", methods=["GET", "POST"])
def recipe_edit(recipe_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
    recipe = cur.fetchone()

    if recipe is None:
        cur.close()
        conn.close()
        return "レシピが見つかりません", 404

    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category") or "未分類"
        ingredients = request.form.get("ingredients")
        steps = request.form.get("steps")
        time_minutes = request.form.get("time_minutes") or None
        effort_level = request.form.get("effort_level")
        is_two_days = True if request.form.get("is_two_days") else False
        husband_favorite = True if request.form.get("husband_favorite") else False
        memo = request.form.get("memo")

        cur.execute("""
            UPDATE recipes
            SET title = %s,
                category = %s,
                ingredients = %s,
                steps = %s,
                time_minutes = %s,
                effort_level = %s,
                is_two_days = %s,
                husband_favorite = %s,
                memo = %s
            WHERE id = %s
        """, (
            title,
            category,
            ingredients,
            steps,
            time_minutes,
            effort_level,
            is_two_days,
            husband_favorite,
            memo,
            recipe_id
        ))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    cur.close()
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
    cur = conn.cursor()

    cur.execute("DELETE FROM recipes WHERE id = %s", (recipe_id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("index"))


@app.route("/meal-plan", methods=["GET", "POST"])
def meal_plan():
    selected_start = request.args.get("start_date") or request.form.get("start_date")

    if selected_start:
        start_date = date.fromisoformat(selected_start)
    else:
        today = date.today()
        start_date = today - timedelta(days=today.weekday())

    end_date = start_date + timedelta(days=7)

    if request.method == "POST":
        conn = get_conn()
        cur = conn.cursor()

        for i in range(7):
            d = start_date + timedelta(days=i)
            plan_date = d.isoformat()
            recipe_id = request.form.get(f"recipe_{i}") or None
            note = request.form.get(f"note_{i}")

            cur.execute("""
                INSERT INTO meal_plans (plan_date, recipe_id, note)
                VALUES (%s, %s, %s)
                ON CONFLICT (plan_date)
                DO UPDATE SET
                    recipe_id = EXCLUDED.recipe_id,
                    note = EXCLUDED.note
            """, (plan_date, recipe_id, note))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("meal_plan", start_date=start_date.isoformat()))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM recipes ORDER BY category, title")
    recipes = cur.fetchall()

    cur.execute("""
        SELECT mp.*, r.title AS recipe_title
        FROM meal_plans mp
        LEFT JOIN recipes r ON mp.recipe_id = r.id
        WHERE mp.plan_date >= %s
          AND mp.plan_date < %s
        ORDER BY mp.plan_date
    """, (start_date.isoformat(), end_date.isoformat()))

    plans = cur.fetchall()

    cur.close()
    conn.close()

    plan_map = {str(p["plan_date"]): p for p in plans}

    week = []
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]

    for i in range(7):
        d = start_date + timedelta(days=i)
        week.append({
            "index": i,
            "date": d,
            "weekday": weekdays[d.weekday()],
            "plan": plan_map.get(d.isoformat())
        })

    return render_template(
        "meal_plan.html",
        week=week,
        recipes=recipes,
        start_date=start_date
    )


@app.route("/shopping-list")
def shopping_list():
    start_param = request.args.get("start_date")
    end_param = request.args.get("end_date")

    today = date.today()

    if start_param:
        start_date = date.fromisoformat(start_param)
    else:
        start_date = today

    if end_param:
        end_date = date.fromisoformat(end_param)
    else:
        end_date = start_date + timedelta(days=6)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT mp.plan_date, r.title, r.ingredients
        FROM meal_plans mp
        JOIN recipes r ON mp.recipe_id = r.id
        WHERE mp.plan_date >= %s
          AND mp.plan_date <= %s
        ORDER BY mp.plan_date
    """, (start_date.isoformat(), end_date.isoformat()))
    rows = cur.fetchall()

    cur.execute("""
        SELECT *
        FROM shopping_lists
        ORDER BY created_at DESC
        LIMIT 10
    """)
    saved_lists = cur.fetchall()

    cur.close()
    conn.close()

    ingredient_map = {}

    for row in rows:
        ingredients_text = row["ingredients"] or ""

        for line in ingredients_text.splitlines():
            ingredient = line.strip()
            if not ingredient:
                continue

            ingredient_map[ingredient] = ingredient_map.get(ingredient, 0) + 1

    ingredients = sorted(ingredient_map.items())

    return render_template(
        "shopping_list.html",
        ingredients=ingredients,
        rows=rows,
        saved_lists=saved_lists,
        start_date=start_date,
        end_date=end_date
    )


@app.route("/shopping-list/save", methods=["POST"])
def shopping_list_save():
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    items = request.form.get("items")
    memo = request.form.get("memo")

    if not items or not items.strip():
        return redirect(url_for(
            "shopping_list",
            start_date=start_date,
            end_date=end_date
        ))

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO shopping_lists
        (start_date, end_date, items, memo)
        VALUES (%s, %s, %s, %s)
    """, (
        start_date,
        end_date,
        items.strip(),
        memo
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for(
        "shopping_list",
        start_date=start_date,
        end_date=end_date
    ))


if __name__ == "__main__":
    app.run(debug=True)