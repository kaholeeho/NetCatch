from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Project, ApiCase, AiGenerateRecord
from app.utils.ai_client import generate_cases
from app.api import api_bp


@api_bp.route("/ai/generate/api-case", methods=["POST"])
@jwt_required()
def generate_api_case():
    """
    AI 生成接口测试用例
    请求体: {
        "project_id": 1,
        "api_url": "/api/user",
        "api_method": "POST",
        "api_params": {},
        "prompt": "根据用户注册接口生成测试用例...",
        "case_count": 10
    }
    """
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        project_id = data.get("project_id")
        api_url = (data.get("api_url") or "").strip()
        api_method = (data.get("api_method") or "GET").strip().upper()
        prompt = (data.get("prompt") or "").strip()

        if not project_id:
            return jsonify({"code": 400, "msg": "项目ID不能为空", "data": None}), 400
        if not api_url:
            return jsonify({"code": 400, "msg": "接口路径不能为空", "data": None}), 400
        if not prompt:
            return jsonify({"code": 400, "msg": "提示词不能为空", "data": None}), 400

        # 验证项目权限
        project = Project.query.get(project_id)
        if not project:
            return jsonify({"code": 404, "msg": "项目不存在", "data": None}), 404
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        # 创建生成记录（初始状态为 pending）
        record = AiGenerateRecord(
            project_id=project_id,
            create_user=user_id,
            prompt=prompt,
            api_info={
                "api_url": api_url,
                "api_method": api_method,
                "api_params": data.get("api_params", {}),
            },
            generate_type="api_case",
            case_count=0,
            status="pending",
            generated_cases=None,
        )
        db.session.add(record)
        db.session.commit()

        # 调用 DeepSeek API 生成用例
        try:
            api_context = {
                "api_url": api_url,
                "api_method": api_method,
                "api_params": data.get("api_params", {}),
            }
            generated_cases = generate_cases(prompt, api_context)

            # 更新记录
            record.status = "success"
            record.case_count = len(generated_cases)
            record.generated_cases = generated_cases
            db.session.commit()

            return jsonify({
                "code": 200,
                "msg": f"成功生成 {len(generated_cases)} 条用例",
                "data": {
                    "record_id": record.id,
                    "case_count": len(generated_cases),
                    "cases": generated_cases,
                },
            }), 200

        except Exception as e:
            record.status = "failed"
            record.generated_cases = {"error": str(e)}
            db.session.commit()

            return jsonify({
                "code": 500,
                "msg": f"AI 生成失败: {str(e)}",
                "data": {"record_id": record.id, "cases": []},
            }), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"生成请求失败: {str(e)}", "data": None}), 500


@api_bp.route("/ai/import", methods=["POST"])
@jwt_required()
def import_cases():
    """
    将 AI 生成的用例导入到 ApiCase 表
    请求体: {
        "record_id": 123,
        "case_ids_to_import": [0, 1, 2]  # 用户选择要导入的用例索引
    }
    """
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求体不能为空", "data": None}), 400

        record_id = data.get("record_id")
        case_ids_to_import = data.get("case_ids_to_import", [])

        if not record_id:
            return jsonify({"code": 400, "msg": "生成记录ID不能为空", "data": None}), 400
        if not case_ids_to_import:
            return jsonify({"code": 400, "msg": "请选择要导入的用例", "data": None}), 400

        # 查询生成记录
        record = AiGenerateRecord.query.get(record_id)
        if not record:
            return jsonify({"code": 404, "msg": "生成记录不存在", "data": None}), 404

        # 验证权限
        project = Project.query.get(record.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权操作此项目", "data": None}), 403

        if record.status != "success" or not record.generated_cases:
            return jsonify({"code": 400, "msg": "该记录没有可导入的用例", "data": None}), 400

        # 导入选中的用例
        all_cases = record.generated_cases
        imported = []
        for idx in case_ids_to_import:
            if idx < 0 or idx >= len(all_cases):
                continue

            case_data = all_cases[idx]
            api_case = ApiCase(
                project_id=record.project_id,
                name=case_data.get("name", f"AI生成用例_{idx}"),
                method=case_data.get("method", "GET").upper(),
                url=case_data.get("url", ""),
                headers=case_data.get("headers", {"Content-Type": "application/json"}),
                params=case_data.get("params"),
                body=case_data.get("body"),
                body_type="json",
                assertions=case_data.get("assertions", [{"type": "status_code", "expected": 200}]),
                extract=case_data.get("extract"),
                create_user=user_id,
            )
            db.session.add(api_case)
            db.session.flush()
            imported.append(api_case.to_dict())

        db.session.commit()

        return jsonify({
            "code": 201,
            "msg": f"成功导入 {len(imported)} 条用例",
            "data": {"imported": imported},
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"导入失败: {str(e)}", "data": None}), 500


@api_bp.route("/ai/record", methods=["GET"])
@jwt_required()
def list_ai_records():
    """查询 AI 生成记录列表"""
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

        records = AiGenerateRecord.query.filter_by(project_id=project_id)\
            .order_by(AiGenerateRecord.create_time.desc()).all()

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": [r.to_dict() for r in records],
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取记录列表失败: {str(e)}", "data": None}), 500


@api_bp.route("/ai/record/<int:record_id>", methods=["GET"])
@jwt_required()
def get_ai_record(record_id):
    """查询 AI 生成记录详情"""
    try:
        user_id = int(get_jwt_identity())
        record = AiGenerateRecord.query.get(record_id)
        if not record:
            return jsonify({"code": 404, "msg": "记录不存在", "data": None}), 404

        project = Project.query.get(record.project_id)
        if project.owner_id != user_id:
            return jsonify({"code": 403, "msg": "无权查看此记录", "data": None}), 403

        return jsonify({
            "code": 200,
            "msg": "获取成功",
            "data": record.to_dict(),
        }), 200

    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取记录失败: {str(e)}", "data": None}), 500
