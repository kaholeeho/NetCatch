from flask import Blueprint, jsonify

api_bp = Blueprint("api", __name__)


# 注册子模块路由
from app.api import project
from app.api import environment
from app.api import api_case
from app.api import suite
from app.api import ai_generate
from app.api import web_script


# 健康检查
@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"code": 200, "msg": "success", "data": "NetCatch API is running"})
