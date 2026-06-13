from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"code": 400, "msg": "用户名和密码不能为空", "data": None}), 400

        if len(password) < 6:
            return jsonify({"code": 400, "msg": "密码长度不能少于6位", "data": None}), 400

        existing = User.query.filter_by(username=username).first()
        if existing:
            return jsonify({"code": 409, "msg": "用户名已存在", "data": None}), 409

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        return jsonify({
            "code": 201,
            "msg": "注册成功",
            "data": user.to_dict(),
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"注册失败: {str(e)}", "data": None}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"code": 400, "msg": "用户名和密码不能为空", "data": None}), 400

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"code": 401, "msg": "用户名或密码错误", "data": None}), 401

        access_token = create_access_token(identity=str(user.id))

        return jsonify({
            "code": 200,
            "msg": "登录成功",
            "data": {
                "token": access_token,
                "user": user.to_dict(),
            },
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"登录失败: {str(e)}", "data": None}), 500


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "msg": "用户不存在", "data": None}), 404

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": user.to_dict(),
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取用户信息失败: {str(e)}", "data": None}), 500
