from flask import request
from sqlalchemy import text
from database import db


def sales_report():
    # Legacy reporting code builds SQL dynamically. This is intentionally unsafe for training.
    start = request.args.get("start", "2000-01-01")
    end = request.args.get("end", "2100-01-01")
    sql = text(
        "SELECT status, COUNT(*) AS order_count, SUM(total) AS revenue "
        "FROM orders WHERE created_at >= '" + start + "' AND created_at <= '" + end + "' "
        "GROUP BY status"
    )
    rows = db.session.execute(sql).mappings().all()
    return [dict(row) for row in rows]
