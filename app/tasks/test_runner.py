import json as json_lib
from datetime import datetime, timezone
from app import db
from app.models import TestSuite, TestTask, ApiCase, Environment
from app.utils.http_client import execute_case
from app.celery_app import celery


def _truncate_body(body, max_len=500):
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
    if not isinstance(response_body, dict):
        return None
    for key in ("msg", "message", "error", "error_msg", "detail"):
        val = response_body.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _execute_suite_cases(task_id, suite_id, environment_id=None):
    suite = TestSuite.query.get(suite_id)
    if not suite:
        return {"error": "测试集合不存在"}

    task_record = TestTask.query.get(task_id)
    if not task_record:
        return {"error": "任务记录不存在"}

    task_record.status = "running"
    task_record.start_time = datetime.now(timezone.utc)
    db.session.commit()

    env_vars = {}
    if environment_id:
        env = Environment.query.get(environment_id)
        if env and env.project_id == suite.project_id:
            env_vars = env.variables or {}

    case_ids = suite.case_ids or []
    cases = ApiCase.query.filter(ApiCase.id.in_(case_ids)).all()
    cases_dict = {c.id: c for c in cases}

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

            error_msg = None
            has_runtime_error = bool(result.get("error"))

            if not case_passed:
                error_msg = _extract_error_from_body(result.get("response_body"))

            if not error_msg and has_runtime_error:
                error_msg = result["error"]

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
    from app import create_app
    app = create_app()
    with app.app_context():
        return _execute_suite_cases(task_id, suite_id, environment_id)


@celery.task(bind=True, name="run_suite_task")
def run_suite_task(self, suite_id, environment_id=None):
    from app import create_app
    app = create_app()
    with app.app_context():
        task_record = TestTask.query.filter_by(
            suite_id=suite_id,
            status="pending",
        ).order_by(TestTask.id.desc()).first()

        if not task_record:
            return {"error": "没有找到待执行的任务"}

        return _execute_suite_cases(task_record.id, suite_id, environment_id)



def _execute_web_script_core(task_id, variables=None):
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
    from app import create_app
    app = create_app()
    with app.app_context():
        return _execute_web_script_core(task_id, variables)


@celery.task(bind=True, name="run_web_script_task")
def run_web_script_task(self, task_id, variables=None):
    from app import create_app
    app = create_app()
    with app.app_context():
        return _execute_web_script_core(task_id, variables)
