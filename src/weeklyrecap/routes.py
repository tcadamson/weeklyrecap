import calendar
import datetime
import re

import dateutil.relativedelta
import flask

from . import app


def _timestamp_to_datestamp(timestamp: float) -> int:
    monday_date = (
        timestamp_date := datetime.datetime.fromtimestamp(
            float(str(timestamp)[:10]), tz=datetime.UTC
        )
    ) - datetime.timedelta(days=timestamp_date.weekday())
    week_length = 7
    week_threshold = week_length // 2
    week = (
        monday_date.day
        # First weekday maps to offset of 0, 1, 2, 3, -3, -2, -1
        + (
            (monday_date.replace(day=1).weekday() - week_threshold - 1) % week_length
            - week_threshold
        )
        - 1
    ) // week_length + 1

    if (
        (monday_date + dateutil.relativedelta.relativedelta(day=31)).day
        - monday_date.day
    ) < week_threshold:
        week = 1
        monday_date += dateutil.relativedelta.relativedelta(months=1)

    return int(f"{monday_date.strftime("%y%m")}{week}")


@app.template_filter()
def full_datestamp(datestamp: int) -> str:  # noqa: D103
    if not (datestamp_match := re.search(r"^(\d{2})(\d{2})(\d)$", str(datestamp))):
        return ""

    year, month, week = datestamp_match.groups()

    return f"{calendar.month_name[int(month)]} {2000 + int(year)}, week {week}"


@app.route("/")
def index() -> str:  # noqa: D103
    return flask.render_template(
        "index.html",
        datestamp=_timestamp_to_datestamp(
            datetime.datetime.now(datetime.UTC).timestamp()
        ),
    )
