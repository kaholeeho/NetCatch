from datetime import datetime, timezone
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Project, TestSuite, TestTask, Environment, ApiCase
from app.api import api_bp


@api_bp.route("/suite", methods=["POST"])
@jwt_required()
def create_suite():
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
            return jsonify({"code": 400, "msg": "集合名称不能为空", "data": None}), 400

        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        suite = TestSuite(
            name=name,
            project_id=project_id,
            case_ids=data.get("case_ids", []),
        )
        db.session.add(suite)
        db.session.commit()

        return jsonify({"code": 201, "msg": "创建成功", "data": suite.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"创建集合失败: {str(e)}", "data": None}), 500


@api_bp.route("/suite", methods=["GET"])
@jwt_required()
def list_suites():
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

        suites = TestSuite.query.filter_by(project_id=project_id)\
            .order_by(TestSuite.create_time.desc()).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": [s.to_dict() for s in suites],
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取集合列表失败: {str(e)}", "data": None}), 500


@api_bp.route("/suite/<int:suite_id>", methods=["GET"])
@jwt_required()
def get_suite(suite_id):
    try:
        user_id = int(get_jwt_identity())
        suite = TestSuite.query.get(suite_id)
        if not suite:
            return jsonify({"code": 404, "msg": "测试集合不存在", "data": None}), 404

        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此集合", "data": None}), 403

        data = suite.to_dict()
        if suite.case_ids:
            cases = ApiCase.query.filter(ApiCase.id.in_(suite.case_ids)).all()
            data["cases"] = [c.to_dict() for c in cases]
        else:
            data["cases"] = []

        return jsonify({"code": 200, "msg": "获取成功", "data": data}), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取集合失败: {str(e)}", "data": None}), 500


@api_bp.route("/suite/<int:suite_id>", methods=["PUT"])
@jwt_required()
def update_suite(suite_id):
    try:
        user_id = int(get_jwt_identity())
        suite = TestSuite.query.get(suite_id)
        if not suite:
            return jsonify({"code": 404, "msg": "测试集合不存在", "data": None}), 404

        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此集合", "data": None}), 403

        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        if "name" in data and data["name"]:
            suite.name = data["name"].strip()
        if "case_ids" in data:
            suite.case_ids = data["case_ids"]

        db.session.commit()
        return jsonify({"code": 200, "msg": "更新成功", "data": suite.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"更新集合失败: {str(e)}", "data": None}), 500


@api_bp.route("/suite/<int:suite_id>", methods=["DELETE"])
@jwt_required()
def delete_suite(suite_id):
    try:
        user_id = int(get_jwt_identity())
        suite = TestSuite.query.get(suite_id)
        if not suite:
            return jsonify({"code": 404, "msg": "测试集合不存在", "data": None}), 404

        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此集合", "data": None}), 403

        db.session.delete(suite)
        db.session.commit()
        return jsonify({"code": 200, "msg": "删除成功", "data": None}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"删除集合失败: {str(e)}", "data": None}), 500

@api_bp.route("/suite/<int:suite_id>/run", methods=["POST"])
@jwt_required()
def run_suite(suite_id):
    try:
        user_id = int(get_jwt_identity())
        suite = TestSuite.query.get(suite_id)
        if not suite:
            return jsonify({"code": 404, "msg": "测试集合不存在", "data": None}), 404

        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此集合", "data": None}), 403

        if not suite.case_ids or len(suite.case_ids) == 0:
            return jsonify({"code": 400, "msg": "集合中没有用例", "data": None}), 400

        data = request.get_json() or {}
        environment_id = data.get("environment_id")

        task = TestTask(
            suite_id=suite_id,
            status="pending",
        )
        db.session.add(task)
        db.session.commit()

        try:
            from app.tasks.test_runner import run_suite_task
            run_suite_task.delay(suite_id, environment_id)
        except Exception:
            from app.tasks.test_runner import run_suite_task_sync
            run_suite_task_sync(task.id, suite_id, environment_id)

        return jsonify({
            "code": 200,
            "msg": "执行任务已提交",
            "data": {"task_id": task.id, "status": task.status},
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"提交执行失败: {str(e)}", "data": None}), 500


@api_bp.route("/task/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    try:
        user_id = int(get_jwt_identity())
        task = TestTask.query.get(task_id)
        if not task:
            return jsonify({"code": 404, "msg": "任务不存在", "data": None}), 404

        suite = TestSuite.query.get(task.suite_id)
        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此任务", "data": None}), 403

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": task.to_dict(),
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取任务失败: {str(e)}", "data": None}), 500


@api_bp.route("/task", methods=["GET"])
@jwt_required()
def list_tasks():
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

        suite_ids = [s.id for s in TestSuite.query.filter_by(project_id=project_id).all()]
        if not suite_ids:
            return jsonify({"code": 200, "msg": "获取成功", "data": []}), 200

        tasks = TestTask.query.filter(TestTask.suite_id.in_(suite_ids))\
            .order_by(TestTask.id.desc()).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": [t.to_dict() for t in tasks],
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取任务列表失败: {str(e)}", "data": None}), 500



@api_bp.route("/report/<int:task_id>", methods=["GET"])
@jwt_required()
def get_report(task_id):
    try:
        user_id = int(get_jwt_identity())
        task = TestTask.query.get(task_id)
        if not task:
            return jsonify({"code": 404, "msg": "任务不存在", "data": None}), 404

        suite = TestSuite.query.get(task.suite_id)
        project = Project.query.get(suite.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此报告", "data": None}), 403

        result = task.result or {}
        report = {
            "task_id": task.id,
            "suite_id": task.suite_id,
            "suite_name": suite.name,
            "project_id": project.id,
            "project_name": project.name,
            "status": task.status,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
            "total": result.get("total", 0),
            "passed": result.get("passed", 0),
            "failed": result.get("failed", 0),
            "total_time_ms": result.get("total_time_ms", 0),
            "pass_rate": round(result.get("passed", 0) / max(result.get("total", 1), 1) * 100, 2),
            "details": result.get("details", []),
        }

        return jsonify({"code": 200, "msg": "获取成功", "data": report}), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取报告失败: {str(e)}", "data": None}), 500


@api_bp.route("/report", methods=["GET"])
@jwt_required()
def list_reports():
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

        suite_ids = [s.id for s in TestSuite.query.filter_by(project_id=project_id).all()]
        if not suite_ids:
            return jsonify({"code": 200, "msg": "获取成功", "data": []}), 200

        tasks = TestTask.query.filter(TestTask.suite_id.in_(suite_ids))\
            .order_by(TestTask.id.desc()).all()

        reports = []
        for task in tasks:
            r = task.result or {}
            suite = TestSuite.query.get(task.suite_id)
            reports.append({
                "task_id": task.id,
                "suite_id": task.suite_id,
                "suite_name": suite.name if suite else "未知",
                "status": task.status,
                "total": r.get("total", 0),
                "passed": r.get("passed", 0),
                "failed": r.get("failed", 0),
                "pass_rate": round(r.get("passed", 0) / max(r.get("total", 1), 1) * 100, 2),
                "start_time": task.start_time.isoformat() if task.start_time else None,
                "end_time": task.end_time.isoformat() if task.end_time else None,
            })

        return jsonify({"code": 200, "msg": "获取成功", "data": reports}), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取报告列表失败: {str(e)}", "data": None}), 500
