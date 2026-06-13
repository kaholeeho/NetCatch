from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Environment, Project
from app.api import api_bp


@api_bp.route("/environment", methods=["POST"])
@jwt_required()
def create_environment():
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        project_id = data.get("project_id")
        name = (data.get("name") or "").strip()

        if not project_id:
            return jsonify({"code": 400, "msg": "项目ID不能为空", "data": None}), 400
        if not name:
            return jsonify({"code": 400, "msg": "环境名称不能为空", "data": None}), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        env = Environment(
            project_id=project_id,
            name=name,
            variables=data.get("variables", {}),
        )
        db.session.add(env)
        db.session.commit()

        return jsonify({"code": 201, "msg": "创建成功", "data": env.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建环境失败: {str(e)}", "data": None}), 500


@api_bp.route("/environment", methods=["GET"])
@jwt_required()
def list_environments():
    try:
        user_id = int(get_jwt_identity())
        project_id = request.args.get("project_id", type=int)

        if not project_id:
            return jsonify({"code": 400, "msg": "缺少 project_id 参数", "data": None}), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此项目", "data": None}), 403

        envs = Environment.query.filter_by(project_id=project_id)\
            .order_by(Environment.create_time.desc()).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": [e.to_dict() for e in envs],
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取环境列表失败: {str(e)}", "data": None}), 500


@api_bp.route("/environment/<int:env_id>", methods=["PUT"])
@jwt_required()
def update_environment(env_id):
    try:
        user_id = int(get_jwt_identity())
        env = Environment.query.get(env_id)
        if not env:
            return jsonify({"code": 404, "msg": "环境不存在", "data": None}), 404

        project = Project.query.get(env.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此环境", "data": None}), 403

        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        if "name" in data and data["name"]:
            env.name = data["name"].strip()
        if "variables" in data:
            env.variables = data["variables"]

        db.session.commit()
        return jsonify({"code": 200, "msg": "更新成功", "data": env.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新环境失败: {str(e)}", "data": None}), 500


@api_bp.route("/environment/<int:env_id>", methods=["DELETE"])
@jwt_required()
def delete_environment(env_id):
    try:
        user_id = int(get_jwt_identity())
        env = Environment.query.get(env_id)
        if not env:
            return jsonify({"code": 404, "msg": "环境不存在", "data": None}), 404

        project = Project.query.get(env.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此环境", "data": None}), 403

        db.session.delete(env)
        db.session.commit()
        return jsonify({"code": 200, "msg": "删除成功", "data": None}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除环境失败: {str(e)}", "data": None}), 500
