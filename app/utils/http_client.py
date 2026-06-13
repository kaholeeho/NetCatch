import re
import json
import time
import requests
from jsonpath_ng import parse as jsonpath_parse

from app.utils.data_factory import _resolve_data_functions


def replace_variables(data, env_vars: dict):
    if env_vars is None:
        env_vars = {}

    if isinstance(data, str):
        def replacer(match):
            var_name = match.group(1)
            return str(env_vars.get(var_name, match.group(0)))
        result = re.sub(r"\{\{(\w+)\}\}", replacer, data)
        return _resolve_data_functions(result)

    elif isinstance(data, dict):
        return {k: replace_variables(v, env_vars) for k, v in data.items()}

    elif isinstance(data, list):
        return [replace_variables(item, env_vars) for item in data]

    return data


def execute_assertion(assertion: dict, status_code: int, response_body) -> dict:
    assert_type = assertion.get("type", "")
    expected = assertion.get("expected")
    actual = None
    passed = False
    desc = ""

    try:
        if assert_type == "status_code":
            actual = status_code
            expected = int(expected) if expected is not None else expected
            passed = (status_code == expected)
            desc = f"状态码 == {expected}"

        elif assert_type == "jsonpath":
            path = assertion.get("path", "$")
            try:
                body = response_body if isinstance(response_body, dict) else json.loads(response_body)
            except (json.JSONDecodeError, TypeError):
                body = {}
            matches = jsonpath_parse(path).find(body)
            actual = [m.value for m in matches] if matches else None
            if isinstance(actual, list) and len(actual) == 1:
                actual = actual[0]
            passed = (actual == expected)
            desc = f"JSONPath '{path}' == {expected}"

        elif assert_type == "contains":
            body_str = str(response_body) if response_body else ""
            actual = str(expected) in body_str
            passed = actual
            desc = f"包含 '{expected}'"

        elif assert_type == "regex":
            pattern = str(expected)
            body_str = str(response_body) if response_body else ""
            actual = bool(re.search(pattern, body_str))
            passed = actual
            desc = f"正则匹配 '{pattern}'"

        else:
            desc = f"未知断言类型: {assert_type}"
            passed = False

    except Exception as e:
        desc = f"断言执行异常: {str(e)}"
        passed = False

    return {
        "assertion": desc,
        "passed": passed,
        "actual": actual,
        "expected": expected,
    }


def execute_case(case: dict, env_vars: dict = None) -> dict:
    if env_vars is None:
        env_vars = {}

    result = {
        "success": False,
        "status_code": None,
        "response_body": None,
        "response_headers": None,
        "response_time_ms": 0,
        "assert_results": [],
        "error": None,
    }

    try:
        method = replace_variables(case.get("method", "GET"), env_vars).upper()
        url = replace_variables(case.get("url", ""), env_vars)
        headers = replace_variables(case.get("headers") or {}, env_vars)
        params = replace_variables(case.get("params") or {}, env_vars)
        body = replace_variables(case.get("body"), env_vars)
        body_type = case.get("body_type", "json")
        assertions = case.get("assertions") or []

        if url and not url.startswith(("http://", "https://")):
            raise ValueError(
                f"URL 缺少协议头 (http/https): {url}"
            )

        request_kwargs = {
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "timeout": 30,
        }

        if body is not None:
            if body_type == "json":
                request_kwargs["json"] = body
            elif body_type == "form":
                request_kwargs["data"] = body
            elif body_type == "text":
                request_kwargs["data"] = str(body)
            else:
                request_kwargs["json"] = body

        start_time = time.time()
        response = requests.request(**request_kwargs)
        elapsed_ms = int((time.time() - start_time) * 1000)

        result["status_code"] = response.status_code
        result["response_time_ms"] = elapsed_ms
        result["response_headers"] = dict(response.headers)

        try:
            result["response_body"] = response.json()
        except (json.JSONDecodeError, ValueError):
            result["response_body"] = response.text

        all_passed = True
        for assertion in assertions:
            assert_result = execute_assertion(
                assertion,
                response.status_code,
                result["response_body"],
            )
            result["assert_results"].append(assert_result)
            if not assert_result["passed"]:
                all_passed = False

        result["success"] = all_passed

    except requests.exceptions.Timeout:
        result["error"] = "请求超时"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"连接失败: {str(e)}"
    except Exception as e:
        result["error"] = f"执行异常: {str(e)}"

    return result
