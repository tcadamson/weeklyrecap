import calendar
import glob
import re

from flask import Flask, render_template, request, abort
from werkzeug.exceptions import HTTPException

import database
import scraper

STATIC_PATH = "static"

app = Flask(__name__)
# https://jinja.palletsprojects.com/en/3.0.x/templates/#whitespace-control
app.jinja_options["trim_blocks"] = True
app.jinja_options["lstrip_blocks"] = True

def split_datestamp(datestamp):
    split_match = re.search(r"(?P<year>\d{2})(?P<month>\d{2})(?P<week>\d)", str(datestamp))
    if split_match:
        return {k: split_match.group(k) for k in split_match.groupdict().keys()}

def get_page():
    return int(request.args.get("page", default = 1))

@app.route("/")
def index():
    return render_template("index.html.jinja", datestamp = scraper.decode_unix())

@app.route("/archive")
def archive():
    return render_template("archive.html.jinja", datestamps = [split_datestamp(x) for x in glob.glob(f"{STATIC_PATH}/*/") if x])

@app.route("/view/<int:datestamp>")
def view(datestamp):
    rows = []
    filenames = [re.sub(r".+/(\d+).+", r"\1", x) for x in glob.glob(f"{STATIC_PATH}/{datestamp}/*")]
    if not filenames:
        abort(404)
    connection = database.Connection(memory = True)
    cursor = connection.execute(f"""
        select *
        from games
        join posts on
            games.id = posts.game_id
        where unix in
            ({','.join(['?'] * len(filenames))})
    """, filenames)
    if cursor:
        rows = cursor.fetchall()
    connection.close()
    return render_template("view.html.jinja", datestamp = datestamp, rows = rows)

@app.route("/games")
def games():
    rows = []
    connection = database.Connection(memory = True)
    cursor = connection.execute("""
        select *
        from (
            select games.id, title, dev, tools, web, unix, ext
            from games
            join posts on
                games.id = posts.game_id
            where ext != ''
            or games.id not in (
                select game_id from posts where ext != ''
            )
            order by random()
        )
        group by id
        order by id desc
    """)
    if cursor:
        rows = cursor.fetchall()
    connection.close()
    return render_template("games.html.jinja", rows = rows, page = get_page())

@app.route("/games/<title>")
def game(title):
    rows = []
    connection = database.Connection(memory = True)
    game_data = connection.get_row("games", title = title)
    if not game_data:
        abort(404)
    cursor = connection.execute(f"select * from posts where game_id = ? order by unix desc", (game_data["id"],))
    if cursor:
        rows = cursor.fetchall()
    connection.close()
    return render_template("game.html.jinja", rows = rows, page = get_page(), game_data = game_data)

@app.errorhandler(HTTPException)
def error(http_exception):
    return render_template("error.html.jinja", http_exception = http_exception), http_exception.code

@app.template_filter()
def full_year(year):
    return 2000 + int(year)

@app.template_filter()
def calendar_month(month_index):
    return calendar.month_name[int(month_index)]

@app.template_filter()
def decode_unix(unix):
    datestamp = scraper.decode_unix(unix)
    # Some legacy recaps have entries that don't "belong", i.e. the unix timestamp doesn't match the datestamp. This is because the
    # previous, manual scraping process wasn't always on time. As a consequence, we may have to search for the correct datestamp
    datestamp_pattern = r"(?P<datestamp>\d+)(?=/)"
    path = f"{STATIC_PATH}/{datestamp}/{unix}.*"
    if not glob.glob(path):
        actual_path = glob.glob(re.sub(datestamp_pattern, "*", path))
        if actual_path:
            return re.search(datestamp_pattern, next(iter(actual_path))).group("datestamp")
    return datestamp

@app.template_filter()
def semantic_datestamp(datestamp):
    datestamp_data = split_datestamp(datestamp)
    if datestamp_data:
        return f"{calendar_month(datestamp_data['month'])} {full_year(datestamp_data['year'])}, Week {datestamp_data['week']}"

@app.template_test()
def matches_datestamp(unix, datestamp):
    return decode_unix(unix) == datestamp
