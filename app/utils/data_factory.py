"""
数据工厂模块
提供 {{$uuid}}、{{$random.email}} 等数据工厂函数，在运行时生成动态测试数据。
"""
import re
import uuid
import random
import string
from datetime import datetime


# ---------- 底层单字符串解析 ----------

# 匹配模式: {{$uuid}}, {{$random.email}}, {{$random.string(8)}}, {{$random.number(1,100)}}
_FACTORY_PATTERN = re.compile(r"\{\{\$([\w.]+(?:\([^)]*\))?)\}\}")


def _resolve_data_functions(value: str) -> str:
    """在单条字符串中替换 {{$函数}} 数据工厂占位符"""
    if not isinstance(value, str):
        return value

    def replacer(match):
        expr = match.group(1)  # "uuid", "random.email", "random.string(8)"
        return _execute_function(expr)

    return _FACTORY_PATTERN.sub(replacer, value)


# ---------- 递归版本（字典/列表/字符串） ----------

def resolve_data_function(data):
    """递归替换数据结构中所有字符串的 {{$函数}} 数据工厂占位符

    支持递归处理 dict / list / str，与 replace_variables 签名对齐。
    """
    if isinstance(data, str):
        return _resolve_data_functions(data)
    if isinstance(data, dict):
        return {k: resolve_data_function(v) for k, v in data.items()}
    if isinstance(data, list):
        return [resolve_data_function(item) for item in data]
    return data


# ---------- 函数执行引擎 ----------

def _execute_function(expr: str) -> str:
    """执行单个数据工厂表达式，返回生成的字符串值"""

    # 解析参数: func_name 或 func_name(arg1,arg2,...)
    if '(' in expr and expr.endswith(')'):
        paren_idx = expr.index('(')
        name = expr[:paren_idx]
        args_str = expr[paren_idx + 1:-1]
        args = [a.strip() for a in args_str.split(',') if a.strip()]
    else:
        name = expr
        args = []

    # ----- 基础函数 -----
    if name == 'uuid':
        return str(uuid.uuid4())

    if name == 'timestamp':
        return str(int(datetime.now().timestamp()))

    if name == 'datetime':
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ----- 随机数据函数 -----
    if name == 'random.email':
        _chars = string.ascii_lowercase + string.digits
        local_part = ''.join(random.choices(_chars, k=8))
        domains = ['test.com', 'example.com', 'mail.com', 'demo.org', 'api-test.com']
        return f"{local_part}@{random.choice(domains)}"

    if name == 'random.phone':
        second = random.choice(['3', '5', '7', '8', '9'])
        rest = ''.join(str(random.randint(0, 9)) for _ in range(9))
        return f"1{second}{rest}"

    if name == 'random.name':
        names = ['张三', '李四', '王五', '赵六', 'Alice', 'Bob', 'Charlie',
                 'David', 'Emma', 'Frank', 'Grace', 'Henry']
        return random.choice(names)

    if name == 'random.address':
        cities = ['北京市朝阳区', '上海市浦东新区', '广州市天河区',
                  '深圳市南山区', '杭州市西湖区', '成都市高新区']
        streets = ['中山路', '人民路', '建设路', '解放路', '科技路', '创新路']
        return f"{random.choice(cities)}{random.choice(streets)}{random.randint(1, 999)}号"

    if name == 'random.string':
        length = int(args[0]) if args else 8
        if length < 1:
            length = 1
        if length > 1024:
            length = 1024
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    if name == 'random.number':
        a = int(args[0]) if len(args) > 0 else 0
        b = int(args[1]) if len(args) > 1 else 100
        if a > b:
            a, b = b, a
        return str(random.randint(a, b))

    # 未识别的函数 — 保留原样
    return "$" + expr
