"""
System capability API routes.
"""
from flask import jsonify, request

from utils.runtime_capabilities import get_runtime_capabilities


def register_system_routes(app):
    @app.route("/api/system/capabilities", methods=["GET"])
    def get_system_capabilities():
        refresh = str(request.args.get("refresh", "")).strip().lower() in {"1", "true", "yes"}
        caps = get_runtime_capabilities(refresh=refresh)
        return jsonify({"success": True, "capabilities": caps})
