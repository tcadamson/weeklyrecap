import os
import time

from flask import Flask, render_template
from werkzeug.routing import BaseConverter, ValidationError

import database
import scraper

class DatestampConverter(BaseConverter):
    regex = r"\d{5}"

    def to_python(self, value):
        # Overriding to_python isn't actually necessary (we don't transform the datestamp into a different object), however we need
        # it to perform additional validation not possible through regex
        if os.path.exists(f"static/{value}"):
            return value
        else:
            raise ValidationError

app = Flask(__name__)
# https://werkzeug.palletsprojects.com/en/2.2.x/routing/#custom-converters
app.url_map.converters["datestamp"] = DatestampConverter
# https://jinja.palletsprojects.com/en/3.0.x/templates/#whitespace-control
app.jinja_options["trim_blocks"] = True
app.jinja_options["lstrip_blocks"] = True

@app.route("/")
def home():
    return render_template("home.html", datestamp = scraper.decode_unix(time.time()))

@app.route("/view/<datestamp:datestamp>")
def view(datestamp):
    posts = []
    filenames = [x.split(".")[0] for x in os.listdir(f"static/{datestamp}")]
    connection = database.Connection(memory = True)
    cursor = connection.execute(f"select * from posts where unix in ({','.join(['?'] * len(filenames))})", filenames)
    if cursor:
        for post in cursor.fetchall():
            posts.append(dict(connection.get_row("games", post["game_id"])) | dict(post))
    connection.close()
    return render_template("view.html", datestamp = datestamp, posts = posts)
