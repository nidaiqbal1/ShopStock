from flask import Blueprint, flash, render_template, request, send_file

from routes.auth import login_required, owner_required
from services import report_service as rs

bp = Blueprint("reports", __name__)


def _build():
    kind = request.args.get("type", "sales")
    if kind not in rs.REPORT_TYPES:
        kind = "sales"
    period = request.args.get("period", "monthly")
    if period not in ("daily", "weekly", "monthly", "custom"):
        period = "monthly"
    start, end = rs.resolve_range(period, request.args.get("start"), request.args.get("end"))
    return kind, period, rs.get_report(kind, start, end)


@bp.route("/reports")
@owner_required
def index():
    try:
        kind, period, report = _build()
    except ValueError as e:
        flash(str(e), "error")
        kind, period, report = "sales", "monthly", None
    return render_template("reports.html", kind=kind, period=period, report=report, types=rs.REPORT_TYPES,
                           start=request.args.get("start", ""), end=request.args.get("end", ""))


@bp.route("/reports/pdf")
@owner_required
def pdf():
    try:
        kind, _, report = _build()
    except ValueError as e:
        flash(str(e), "error")
        return index()
    return send_file(rs.build_report_pdf(report), mimetype="application/pdf", as_attachment=True,
                     download_name=f"{kind}-report.pdf")
