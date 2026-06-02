"""
Web 自动化测试 API 路由
"""
from datetime import datetime, timezone
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Project, WebScript, WebTestTask
from app.utils.web_runner import run_web_script
from app.api import api_bp


# ==================== 脚本管理 CRUD ====================


@api_bp.route("/web/script", methods=["POST"])
@jwt_required()
def create_web_script():
    """创建 Web 测试脚本"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        project_id = data.get("project_id")
        name = (data.get("name") or "").strip()
        url = (data.get("url") or "").strip()
        steps = data.get("steps", [])

        if not project_id:
            return jsonify({"code": 400, "msg": "项目ID不能为空", "data": None}), 400
        if not name:
            return jsonify({"code": 400, "msg": "脚本名称不能为空", "data": None}), 400
        if not url:
            return jsonify({"code": 400, "msg": "起始URL不能为空", "data": None}), 400
        if not steps or not isinstance(steps, list):
            return jsonify({"code": 400, "msg": "至少需要一个操作步骤", "data": None}), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        script = WebScript(
            project_id=project_id,
            name=name,
            description=data.get("description", ""),
            url=url,
            steps=steps,
            variables=data.get("variables"),
            create_user=user_id,
        )
        db.session.add(script)
        db.session.commit()

        return jsonify({"code": 201, "msg": "创建成功", "data": script.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建脚本失败: {str(e)}", "data": None}), 500


@api_bp.route("/web/script", methods=["GET"])
@jwt_required()
def list_web_scripts():
    """查询项目下的 Web 脚本列表（支持分页）"""
    try:
        user_id = int(get_jwt_identity())
        project_id = request.args.get("project_id", type=int)
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        if not project_id:
            return jsonify({"code": 400, "msg": "缺少 project_id 参数", "data": None}), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此项目", "data": None}), 403

        query = WebScript.query.filter_by(project_id=project_id)\
            .order_by(WebScript.update_time.desc())

        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": {
                "items": [s.to_dict() for s in items],
                "total": total,
                "page": page,
                "per_page": per_page,
            },
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取脚本列表失败: {str(e)}", "data": None}), 500


@api_bp.route("/web/script/<int:script_id>", methods=["GET"])
@jwt_required()
def get_web_script(script_id):
    """获取脚本详情"""
    try:
        user_id = int(get_jwt_identity())
        script = WebScript.query.get(script_id)
        if not script:
            return jsonify({"code": 404, "msg": "脚本不存在", "data": None}), 404

        project = Project.query.get(script.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此脚本", "data": None}), 403

        return jsonify({"code": 200, "msg": "获取成功", "data": script.to_dict()}), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取脚本失败: {str(e)}", "data": None}), 500


@api_bp.route("/web/script/<int:script_id>", methods=["PUT"])
@jwt_required()
def update_web_script(script_id):
    """更新脚本"""
    try:
        user_id = int(get_jwt_identity())
        script = WebScript.query.get(script_id)
        if not script:
            return jsonify({"code": 404, "msg": "脚本不存在", "data": None}), 404

        project = Project.query.get(script.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此脚本", "data": None}), 403

        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        if "name" in data and data["name"]:
            script.name = data["name"].strip()
        if "description" in data:
            script.description = data["description"]
        if "url" in data and data["url"]:
            script.url = data["url"].strip()
        if "steps" in data:
            if not data["steps"] or not isinstance(data["steps"], list):
                return jsonify({"code": 400, "msg": "steps 必须是非空数组", "data": None}), 400
            script.steps = data["steps"]
        if "variables" in data:
            script.variables = data["variables"]

        script.update_time = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({"code": 200, "msg": "更新成功", "data": script.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新脚本失败: {str(e)}", "data": None}), 500


@api_bp.route("/web/script/<int:script_id>", methods=["DELETE"])
@jwt_required()
def delete_web_script(script_id):
    """删除脚本"""
    try:
        user_id = int(get_jwt_identity())
        script = WebScript.query.get(script_id)
        if not script:
            return jsonify({"code": 404, "msg": "脚本不存在", "data": None}), 404

        project = Project.query.get(script.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此脚本", "data": None}), 403

        db.session.delete(script)
        db.session.commit()

        return jsonify({"code": 200, "msg": "删除成功", "data": None}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除脚本失败: {str(e)}", "data": None}), 500


# ==================== 调试执行（同步）====================

@api_bp.route("/web/script/<int:script_id>/debug", methods=["POST"])
@jwt_required()
def debug_web_script(script_id):
    print("request data:", request.get_data(as_text=True))

    """同步调试单条脚本"""
    try:
        # 获取请求体，如果为空则使用空字典
        body = request.get_json(silent=True) or {}
        # 或者：body = request.json if request.is_json else {}

        script = WebScript.query.get(script_id)
        if not script:
            return jsonify({"code": 404, "msg": "脚本不存在"}), 404

        # 运行脚本，变量可以从 body 中获取（例如 body.get('variables', {})）
        result = run_web_script(script.to_dict(), variables=body.get('variables', {}))

        return jsonify({"code": 200, "data": result, "msg": "执行完成"}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": f"调试执行失败: {str(e)}"}), 500
    # try:
    #     user_id = int(get_jwt_identity())
    #     script = WebScript.query.get(script_id)
    #     if not script:
    #         return jsonify({"code": 404, "msg": "脚本不存在", "data": None}), 404
    #
    #     project = Project.query.get(script.project_id)
    #     if project.owner_id != user_id:
    #         return jsonify({"code": 403, "msg": "无权操作此脚本", "data": None}), 403
    #
    #     data = request.get_json() or {}
    #     variables = data.get("variables", {})
    #
    #     result = run_web_script(script.to_dict(), variables)
    #
    #     return jsonify({
    #         "code": 200,
    #         "msg": "执行完成" if result["success"] else "执行失败",
    #         "data": result,
    #     }), 200
    #
    # except Exception as e:
    #     return jsonify({"code": 500, "msg": f"调试执行失败: {str(e)}", "data": None}), 500


# ==================== Web 测试集合 ====================


@api_bp.route("/web/suite", methods=["POST"])
@jwt_required()
def create_web_suite():
    """创建 Web 测试集合"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        project_id = data.get("project_id")
        name = (data.get("name") or "").strip()
        script_ids = data.get("script_ids", [])

        if not project_id:
            return jsonify({"code": 400, "msg": "项目ID不能为空", "data": None}), 400
        if not name:
            return jsonify({"code": 400, "msg": "集合名称不能为空", "data": None}), 400
        if not script_ids:
            return jsonify({"code": 400, "msg": "至少选择一个脚本", "data": None}), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        # 复用现有的 TestSuite 表，增加 type 标记
        from app.models import TestSuite
        suite = TestSuite(
            name=name,
            project_id=project_id,
            case_ids=script_ids,  # 存储 WebScript IDs
        )
        db.session.add(suite)
        db.session.commit()

        # 同时创建 web 任务记录
        task = WebTestTask(
            script_id=script_ids[0],  # 占位
            task_name=name,
            status="pending",
        )
        db.session.add(task)
        db.session.commit()

        return jsonify({
            "code": 201,
            "msg": "创建成功",
            "data": {"suite": suite.to_dict(), "task_id": task.id},
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建集合失败: {str(e)}", "data": None}), 500


@api_bp.route("/web/suite/<int:suite_id>/run", methods=["POST"])
@jwt_required()
def run_web_suite(suite_id):
    """异步执行 Web 测试集合"""
    try:
        user_id = int(get_jwt_identity())
        from app.models import TestSuite

        suite = TestSuite.query.get(suite_id)
        if not suite:
            return jsonify({"code": 404, "msg": "集合不存在", "data": None}), 404

        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此集合", "data": None}), 403

        script_ids = suite.case_ids or []
        if not script_ids:
            return jsonify({"code": 400, "msg": "集合中没有脚本", "data": None}), 400

        data = request.get_json() or {}
        variables = data.get("variables", {})

        # 为集合中的每个脚本创建 WebTestTask 并启动 Celery 任务
        task_ids = []
        for sid in script_ids:
            script = WebScript.query.get(sid)
            if not script:
                continue

            task = WebTestTask(
                script_id=sid,
                task_name=suite.name + " - " + (script.name if script else f"#{sid}"),
                status="pending",
            )
            db.session.add(task)
            db.session.commit()

            # 提交异步任务
            try:
                from app.tasks.test_runner import run_web_script_task
                run_web_script_task.delay(task.id, variables)
            except Exception:
                # 回退到同步执行
                from app.tasks.test_runner import run_web_script_task_sync
                run_web_script_task_sync(task.id, variables)

            task_ids.append(task.id)

        return jsonify({
            "code": 200,
            "msg": f"已提交 {len(task_ids)} 个任务",
            "data": {"task_ids": task_ids},
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"执行集合失败: {str(e)}", "data": None}), 500


# ==================== Web 任务查询 ====================


@api_bp.route("/web/task/<int:task_id>", methods=["GET"])
@jwt_required()
def get_web_task(task_id):
    """查询 Web 测试任务状态和结果"""
    try:
        user_id = int(get_jwt_identity())
        task = WebTestTask.query.get(task_id)
        if not task:
            return jsonify({"code": 404, "msg": "任务不存在", "data": None}), 404

        # 权限验证
        script = WebScript.query.get(task.script_id)
        if script:
            project = Project.query.get(script.project_id)
            if project and project.owner_id != user_id:
                return jsonify({"code": 403, "msg": "无权查看此任务", "data": None}), 403

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": task.to_dict(),
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取任务失败: {str(e)}", "data": None}), 500


@api_bp.route("/web/task", methods=["GET"])
@jwt_required()
def list_web_tasks():
    """查询 Web 测试任务列表（按脚本筛选）"""
    try:
        user_id = int(get_jwt_identity())
        script_id = request.args.get("script_id", type=int)
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        query = WebTestTask.query

        if script_id:
            query = query.filter_by(script_id=script_id)
            # 验证权限
            script = WebScript.query.get(script_id)
            if script:
                project = Project.query.get(script.project_id)
                if project and project.owner_id != user_id:
                    return jsonify({"code": 403, "msg": "无权查看", "data": None}), 403
        else:
            # 如果没传 script_id，查用户项目下的所有任务
            project_ids = [p.id for p in Project.query.filter_by(owner_id=user_id).all()]
            script_ids = [
                s.id for s in WebScript.query.filter(
                    WebScript.project_id.in_(project_ids)
                ).all()
            ]
            if not script_ids:
                return jsonify({"code": 200, "msg": "获取成功", "data": {"items": [], "total": 0, "page": page, "per_page": per_page}}), 200
            query = query.filter(WebTestTask.script_id.in_(script_ids))

        query = query.order_by(WebTestTask.id.desc())
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": {
                "items": [t.to_dict() for t in items],
                "total": total,
                "page": page,
                "per_page": per_page,
            },
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取任务列表失败: {str(e)}", "data": None}), 500
