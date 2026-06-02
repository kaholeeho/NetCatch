from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import ApiCase, Project, Environment
from app.utils.http_client import execute_case
from app.api import api_bp


@api_bp.route("/case", methods=["POST"])
@jwt_required()
def create_case():
    """创建接口测试用例"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        project_id = data.get("project_id")
        name = (data.get("name") or "").strip()
        method = (data.get("method") or "").strip().upper()
        url = (data.get("url") or "").strip()

        if not project_id:
            return jsonify({"code": 400, "msg": "项目ID不能为空", "data": None}), 400
        if not name:
            return jsonify({"code": 400, "msg": "用例名称不能为空", "data": None}), 400
        if not method or method not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            return jsonify({"code": 400, "msg": "无效的请求方法", "data": None}), 400
        if not url:
            return jsonify({"code": 400, "msg": "请求URL不能为空", "data": None}), 400

        # 验证项目存在且属于当前用户
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        case = ApiCase(
            project_id=project_id,
            name=name,
            method=method,
            url=url,
            headers=data.get("headers"),
            params=data.get("params"),
            body=data.get("body"),
            body_type=data.get("body_type", "json"),
            assertions=data.get("assertions", []),
            extract=data.get("extract"),
            create_user=user_id,
        )
        db.session.add(case)
        db.session.commit()

        return jsonify({"code": 201, "msg": "创建成功", "data": case.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建用例失败: {str(e)}", "data": None}), 500


@api_bp.route("/case", methods=["GET"])
@jwt_required()
def list_cases():
    """查询用例列表（按项目筛选）"""
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

        cases = ApiCase.query.filter_by(project_id=project_id)\
            .order_by(ApiCase.create_time.desc()).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": [c.to_dict() for c in cases],
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取用例列表失败: {str(e)}", "data": None}), 500


@api_bp.route("/case/<int:case_id>", methods=["GET"])
@jwt_required()
def get_case(case_id):
    """获取用例详情"""
    try:
        user_id = int(get_jwt_identity())
        case = ApiCase.query.get(case_id)
        if not case:
            return jsonify({"code": 404, "msg": "用例不存在", "data": None}), 404

        # 验证项目归属
        project = Project.query.get(case.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此用例", "data": None}), 403

        return jsonify({"code": 200, "msg": "获取成功", "data": case.to_dict()}), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取用例失败: {str(e)}", "data": None}), 500


@api_bp.route("/case/<int:case_id>", methods=["PUT"])
@jwt_required()
def update_case(case_id):
    """更新用例"""
    try:
        user_id = int(get_jwt_identity())
        case = ApiCase.query.get(case_id)
        if not case:
            return jsonify({"code": 404, "msg": "用例不存在", "data": None}), 404

        project = Project.query.get(case.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此用例", "data": None}), 403

        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        if "name" in data and data["name"]:
            case.name = data["name"].strip()
        if "method" in data:
            method = data["method"].strip().upper()
            if method not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
                return jsonify({"code": 400, "msg": "无效的请求方法", "data": None}), 400
            case.method = method
        if "url" in data and data["url"]:
            case.url = data["url"].strip()
        if "headers" in data:
            case.headers = data["headers"]
        if "params" in data:
            case.params = data["params"]
        if "body" in data:
            case.body = data["body"]
        if "body_type" in data:
            case.body_type = data["body_type"]
        if "assertions" in data:
            case.assertions = data["assertions"]
        if "extract" in data:
            case.extract = data["extract"]

        db.session.commit()
        return jsonify({"code": 200, "msg": "更新成功", "data": case.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新用例失败: {str(e)}", "data": None}), 500


@api_bp.route("/case/<int:case_id>", methods=["DELETE"])
@jwt_required()
def delete_case(case_id):
    """删除用例"""
    try:
        user_id = int(get_jwt_identity())
        case = ApiCase.query.get(case_id)
        if not case:
            return jsonify({"code": 404, "msg": "用例不存在", "data": None}), 404

        project = Project.query.get(case.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此用例", "data": None}), 403

        db.session.delete(case)
        db.session.commit()
        return jsonify({"code": 200, "msg": "删除成功", "data": None}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除用例失败: {str(e)}", "data": None}), 500


@api_bp.route("/case/<int:case_id>/debug", methods=["POST"])
@jwt_required()
def debug_case(case_id):
    """
    调试单个用例（同步执行）
    可选 body 参数指定环境变量 environment_id，用于替换 {{var}}
    """
    try:
        user_id = int(get_jwt_identity())
        case = ApiCase.query.get(case_id)
        if not case:
            return jsonify({"code": 404, "msg": "用例不存在", "data": None}), 404

        project = Project.query.get(case.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此用例", "data": None}), 403

        # 获取环境变量
        data = request.get_json() or {}
        env_vars = {}
        env_id = data.get("environment_id")
        if env_id:
            env = Environment.query.get(env_id)
            if env and env.project_id == case.project_id:
                env_vars = env.variables or {}

        # 执行用例
        result = execute_case(case.to_dict(), env_vars)

        return jsonify({
            "code": 200,
            "msg": "执行完成" if result["success"] else "断言失败",
            "data": result,
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"调试执行失败: {str(e)}", "data": None}), 500
