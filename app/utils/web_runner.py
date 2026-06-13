import re
import time
import base64
from datetime import datetime

from app.utils.data_factory import _resolve_data_functions


def substitute_vars(value, variables):
    if isinstance(value, str):
        def replace_var(m):
            var_name = m.group(1)
            return str(variables.get(var_name, m.group(0)))
        result = re.sub(r"\{\{(\w+)\}\}", replace_var, value)
        return _resolve_data_functions(result)
    elif isinstance(value, dict):
        return {k: substitute_vars(v, variables) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_vars(v, variables) for v in value]
    return value


def execute_step(page, step):
    action = step.get("action", "")
    result = {"action": action, "success": True, "error": None, "screenshot": None}

    try:
        if action == "goto":
            url = step.get("url", "")
            wait_until=step.get('wait_until','domcontentloaded')
            page.goto(url, timeout=step.get("timeout", 30000), wait_until=wait_until)
            result["title"] = page.title()
            result["url"] = page.url

        elif action == "click":
            selector = step.get("selector", "")
            timeout = step.get("timeout", 10000)
            page.click(selector, timeout=timeout)

        elif action == "fill":
            selector = step.get("selector", "")
            value = step.get("value", "")
            page.fill(selector, value)

        elif action == "select":
            selector = step.get("selector", "")
            value = step.get("value", "")
            page.select_option(selector, value)

        elif action == "hover":
            selector = step.get("selector", "")
            timeout = step.get("timeout", 10000)
            page.hover(selector, timeout=timeout)

        elif action == "wait_for_selector":
            selector = step.get("selector", "")
            timeout = step.get("timeout", 10000)
            page.wait_for_selector(selector, timeout=timeout)

        elif action == "assert_text":
            selector = step.get("selector", "")
            expected = step.get("expected", "")
            timeout = step.get("timeout", 5000)
            text = page.text_content(selector, timeout=timeout)
            if text is None:
                raise AssertionError(f"元素 {selector} 不存在")
            if expected not in text:
                raise AssertionError(
                    f"文本断言失败: 期望包含 '{expected}', 实际为 '{text}'"
                )

        elif action == "assert_title":
            expected = step.get("expected", "")
            title = page.title()
            if expected not in title:
                raise AssertionError(
                    f"标题断言失败: 期望包含 '{expected}', 实际为 '{title}'"
                )

        elif action == "assert_url":
            expected = step.get("expected", "")
            url = page.url
            if expected not in url:
                raise AssertionError(
                    f"URL 断言失败: 期望包含 '{expected}', 实际为 '{url}'"
                )

        elif action == "screenshot":
            screenshot_bytes = page.screenshot(full_page=True)
            result["screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")
            result["screenshot_size"] = len(screenshot_bytes)

        elif action == "execute_script":
            script = step.get("script", "")
            result["script_result"] = page.evaluate(script)

        elif action == "sleep":
            duration = int(step.get("value", 1))
            time.sleep(duration)

        else:
            raise ValueError(f"不支持的动作: {action}")

        result["success"] = True

    except Exception as e:
        try:
            screenshot_bytes = page.screenshot(full_page=False)
            result["screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")
        except Exception:
            pass
        result["success"] = False
        result["error"] = f"{action} 执行失败: {str(e)}"

    return result


def run_web_script(script, variables=None):
    script_vars = dict(script.get("variables") or {})
    if variables:
        script_vars.update(variables)

    steps = script.get("steps", [])
    if not steps:
        return {"success": False, "error": "脚本没有步骤", "steps": [], "total_time_ms": 0}

    start_time = time.time()
    results = []
    all_passed = True

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            try:
                for idx, step in enumerate(steps):
                    step_resolved = substitute_vars(step, script_vars)
                    step_result = execute_step(page, step_resolved)
                    step_result["index"] = idx
                    results.append(step_result)

                    if not step_result["success"]:
                        all_passed = False
                        if step.get("stop_on_fail", False):
                            break

                elapsed_ms = int((time.time() - start_time) * 1000)

                return {
                    "success": all_passed,
                    "steps": results,
                    "total_time_ms": elapsed_ms,
                    "final_url": page.url,
                    "final_title": page.title(),
                }

            finally:
                context.close()
                browser.close()

    except ImportError:
        return {
            "success": False,
            "error": "Playwright 未安装，请运行: playwright install chromium",
            "steps": [],
            "total_time_ms": 0,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "error": str(e),
            "steps": results,
            "total_time_ms": elapsed_ms,
        }
