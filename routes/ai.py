from flask import Blueprint, jsonify, render_template, request

from routes.auth import login_required, owner_required
from services import ai_service

bp = Blueprint("ai", __name__)


@bp.route("/ai")
@owner_required
def assistant():
    return render_template("ai_assistant.html", configured=ai_service.is_configured())


@bp.route("/ai/ask", methods=["POST"])
@owner_required
def ask():
    data = request.get_json(silent=True) or {}
    return jsonify(ai_service.ask(data.get("question", "")))
