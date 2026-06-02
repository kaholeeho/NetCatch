import json as json_lib
from datetime import datetime, timezone
from app import db
from app.models import TestSuite, TestTask, ApiCase, Environment
from app.utils.http_client import execute_case
from app.celery_app import celery


def _truncate_body(body, max_len=500):
    """将响应体截断为可读预览（JSON 格式化后截断，普通字符串直接截断）"""
    if body is None:
        return None
    try:
        if isinstance(body, (dict, list)):
            text = json_lib.dumps(body, ensure_ascii=False, indent=2)
        else:
            text = str(body)
    except Exception:
        text = str(body)
    if len(text) > max_len:
        text = text[:max_len] + "\n... (truncated)"
    return text


def _extract_error_from_body(response_body):
    """从响应体中提取业务错误信息，如 msg / message / error / error_msg / detail 等字段"""
    if not isinstance(response_body, dict):
        return None
    for key in ("msg", "message", "error", "error_msg", "detail"):
        val = response_body.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _execute_suite_cases(task_id, suite_id, environment_id=None):
    """执行测试集合的核心逻辑（同步调用）"""
    suite = TestSuite.query.get(suite_id)
    if not suite:
        return {"error": "测试集合不存在"}

    task_record = TestTask.query.get(task_id)
    if not task_record:
        return {"error": "任务记录不存在"}

    task_record.status = "running"
    task_record.start_time = datetime.now(timezone.utc)
    db.session.commit()

    # 获取环境变量
    env_vars = {}
    if environment_id:
        env = Environment.query.get(environment_id)
        if env and env.project_id == suite.project_id:
            env_vars = env.variables or {}

    # 获取所有用例
    case_ids = suite.case_ids or []
    cases = ApiCase.query.filter(ApiCase.id.in_(case_ids)).all()
    cases_dict = {c.id: c for c in cases}

    # 按 case_ids 顺序执行
    details = []
    passed_count = 0
    failed_count = 0
    total_time = 0
    log_lines = []

    for idx, case_id in enumerate(case_ids):
        case = cases_dict.get(case_id)
        if not case:
            log_lines.append(f"[{idx + 1}] Case {case_id}: 用例不存在，跳过")
            details.append({
                "case_id": case_id,
                "name": f"未知用例 (id={case_id})",
                "passed": False,
                "status_code": None,
                "response_time": 0,
                "assert_results": [],
                "response_body_preview": None,
                "error": "用例不存在",
            })
            failed_count += 1
            continue

        log_lines.append(f"[{idx + 1}] 开始执行: {case.name} ({case.method} {case.url})")

        try:
            result = execute_case(case.to_dict(), env_vars)
            case_passed = result["success"]
            response_time = result["response_time_ms"]
            total_time += response_time

            # 构建详情：包含状态码 + 完整断言结果 + 响应体预览
            detail = {
                "case_id": case.id,
                "name": case.name,
                "method": case.method,
                "url": case.url,
                "passed": case_passed,
                "status_code": result["status_code"],
                "response_time": response_time,
                "assert_results": result["assert_results"] or [],
                "response_body_preview": _truncate_body(result.get("response_body")),
            }

            # --- 填充 error 字段：优先级 响应体msg > 运行时错误 > 断言失败 ---
            error_msg = None
            has_runtime_error = bool(result.get("error"))

            # 1) 从响应体提取业务错误信息（如 {"msg":"用户名已存在"}）
            if not case_passed:
                error_msg = _extract_error_from_body(result.get("response_body"))

            # 2) 运行时错误（超时/连接失败等）
            if not error_msg and has_runtime_error:
                error_msg = result["error"]

            # 3) 从断言失败中拼接
            if not error_msg and not case_passed:
                error_parts = []
                for ar in result["assert_results"]:
                    if not ar.get("passed", False):
                        error_parts.append(
                            f"{ar.get('assertion', '未知断言')}"
                            f" (期望={ar.get('expected')}, 实际={ar.get('actual')})"
                        )
                if error_parts:
                    error_msg = "; ".join(error_parts)
                else:
                    error_msg = "断言失败"

            # --- 汇总结果 ---
            # 最终 pass 状态：assertions 全过 且 无运行时错误
            final_passed = case_passed and not has_runtime_error

            if final_passed:
                passed_count += 1
                log_lines.append(f"  -> PASSED ({response_time}ms)")
            else:
                detail["passed"] = False
                detail["error"] = error_msg or "未知错误"
                failed_count += 1
                log_lines.append(f"  -> FAILED: {error_msg or '未知错误'}")

            details.append(detail)

        except Exception as e:
            log_lines.append(f"  -> EXCEPTION: {str(e)}")
            details.append({
                "case_id": case.id,
                "name": case.name,
                "method": case.method,
                "url": case.url,
                "passed": False,
                "status_code": None,
                "response_time": 0,
                "assert_results": [],
                "response_body_preview": None,
                "error": f"执行异常: {str(e)}",
            })
            failed_count += 1

    # 汇总结果
    result_data = {
        "total": len(case_ids),
        "passed": passed_count,
        "failed": failed_count,
        "total_time_ms": total_time,
        "details": details,
    }

    task_record.status = "success" if failed_count == 0 else "failed"
    task_record.result = result_data
    task_record.log = "\n".join(log_lines)
    task_record.end_time = datetime.now(timezone.utc)
    db.session.commit()

    return result_data


def run_suite_task_sync(task_id, suite_id, environment_id=None):
    """同步执行测试集合（Celery 不可用时的回退方案）"""
    from app import create_app
    app = create_app()
    with app.app_context():
        return _execute_suite_cases(task_id, suite_id, environment_id)


@celery.task(bind=True, name="run_suite_task")
def run_suite_task(self, suite_id, environment_id=None):
    """Celery 异步任务：执行测试集合中的所有用例"""
    from app import create_app
    app = create_app()
    with app.app_context():
        # 查找最新的 pending 任务
        task_record = TestTask.query.filter_by(
            suite_id=suite_id,
            status="pending",
        ).order_by(TestTask.id.desc()).first()

        if not task_record:
            return {"error": "没有找到待执行的任务"}

        return _execute_suite_cases(task_record.id, suite_id, environment_id)


# ==================== Web 测试脚本异步任务 ====================


def _execute_web_script_core(task_id, variables=None):
    """执行 Web 脚本的核心逻辑（同步调用）"""
    from app.models import WebScript, WebTestTask
    from app.utils.web_runner import run_web_script

    task_record = WebTestTask.query.get(task_id)
    if not task_record:
        return {"error": "任务记录不存在"}

    script = WebScript.query.get(task_record.script_id)
    if not script:
        task_record.status = "failed"
        task_record.log = "脚本不存在"
        db.session.commit()
        return {"error": "脚本不存在"}

    task_record.status = "running"
    task_record.start_time = datetime.now(timezone.utc)
    db.session.commit()

    try:
        result = run_web_script(script.to_dict(), variables or {})

        task_record.status = "success" if result["success"] else "failed"
        task_record.result = result
        task_record.log = _format_web_log(result)
        task_record.end_time = datetime.now(timezone.utc)
        db.session.commit()

        return result

    except Exception as e:
        task_record.status = "failed"
        task_record.result = {"error": str(e)}
        task_record.log = f"执行异常: {str(e)}"
        task_record.end_time = datetime.now(timezone.utc)
        db.session.commit()
        return {"error": str(e)}


def _format_web_log(result):
    """格式化 Web 执行为日志文本"""
    lines = []
    steps = result.get("steps", [])
    for s in steps:
        status = "PASS" if s["success"] else "FAIL"
        action = s.get("action", "unknown")
        error = s.get("error", "")
        line = f"  [{status}] {action}"
        if error:
            line += f" - {error}"
        lines.append(line)

    total = len(steps)
    passed = sum(1 for s in steps if s["success"])
    failed = total - passed
    lines.insert(0, f"总计: {total}, 通过: {passed}, 失败: {failed}")
    lines.insert(0, f"Web 脚本执行完成 ({(result.get('total_time_ms', 0))}ms)")
    return "\n".join(lines)


def run_web_script_task_sync(task_id, variables=None):
    """同步执行 Web 脚本（Celery 不可用时的回退方案）"""
    from app import create_app
    app = create_app()
    with app.app_context():
        return _execute_web_script_core(task_id, variables)


@celery.task(bind=True, name="run_web_script_task")
def run_web_script_task(self, task_id, variables=None):
    """Celery 异步任务：执行 Web 测试脚本"""
    from app import create_app
    app = create_app()
    with app.app_context():
        return _execute_web_script_core(task_id, variables)
