from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Project
from app.api import api_bp


@api_bp.route("/project", methods=["POST"])
@jwt_required()
def create_project():
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"code": 400, "msg": "项目名称不能为空", "data": None}), 400

        project = Project(
            name=name,
            description=data.get("description", ""),
            owner_id=user_id,
        )
        db.session.add(project)
        db.session.commit()

        return jsonify({"code": 201, "msg": "创建成功", "data": project.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建项目失败: {str(e)}", "data": None}), 500


@api_bp.route("/project", methods=["GET"])
@jwt_required()
def list_projects():
    try:
        user_id = int(get_jwt_identity())
        projects = Project.query.filter_by(owner_id=user_id)\
            .order_by(Project.create_time.desc()).all()
        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": [p.to_dict() for p in projects],
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取项目列表失败: {str(e)}", "data": None}), 500


@api_bp.route("/project/<int:project_id>", methods=["PUT"])
@jwt_required()
def update_project(project_id):
    try:
        user_id = int(get_jwt_identity())
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        if "name" in data and data["name"]:
            project.name = data["name"].strip()
        if "description" in data:
            project.description = data["description"]

        db.session.commit()
        return jsonify({"code": 200, "msg": "更新成功", "data": project.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新项目失败: {str(e)}", "data": None}), 500


@api_bp.route("/project/<int:project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id):
    try:
        user_id = int(get_jwt_identity())
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        db.session.delete(project)
        db.session.commit()
        return jsonify({"code": 200, "msg": "删除成功", "data": None}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除项目失败: {str(e)}", "data": None}), 500
