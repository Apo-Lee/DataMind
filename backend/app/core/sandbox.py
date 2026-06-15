"""Docker 沙箱 — 安全隔离执行 LLM 生成的 Python 代码"""
import json
import logging
import os
import shutil
import tempfile

from app.config import settings


def execute_in_sandbox(code: str, data_json: str) -> dict:
    """在 Docker 容器中执行代码，返回结果。

    Docker 不可用时回退到本地进程内执行（仅限已信任代码，不宜用于生产）。
    """
    import logging
    log = logging.getLogger(__name__)

    # 尝试 Docker
    try:
        import docker as _docker
        client = _docker.from_env()
        client.ping()  # 快速检测 Docker 可用性
        return _docker_execute(client, code, data_json)
    except Exception as e:
        log.warning(f"Docker sandbox unavailable, falling back to local: {e}")
        return _local_execute(code, data_json)


def _docker_execute(client, code: str, data_json: str) -> dict:
    container = None
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp(prefix="datamind_sandbox_")
        code_path = os.path.join(tmp_dir, "code.py")
        data_path = os.path.join(tmp_dir, "data.json")
        result_path = os.path.join(tmp_dir, "result.json")

        full_code = _build_full_code(code)
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(full_code)
        with open(data_path, "w", encoding="utf-8") as f:
            f.write(data_json)

        container = client.containers.run(
            image=settings.sandbox_image,
            command=["python", "/sandbox/code.py"],
            volumes={tmp_dir: {"bind": "/sandbox", "mode": "rw"}},
            mem_limit=settings.sandbox_memory_limit,
            nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
            network_mode="none",
            read_only=True,
            detach=True,
        )
        result = container.wait(timeout=settings.sandbox_timeout)
        if result["StatusCode"] != 0:
            logs = container.logs().decode("utf-8", errors="replace")
            return {"status": "error", "error": f"沙箱退出码 {result['StatusCode']}", "logs": logs}

        with open(result_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
        if tmp_dir:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


def _local_execute(code: str, data_json: str) -> dict:
    """本地进程内执行（回退方案）。数据量较大时注意内存。

    WARNING: 本地执行无沙箱隔离，仅限开发环境使用。
    生产环境必须配置 Docker 沙箱。
    """
    import pandas as pd
    import numpy as np
    import json as _json
    import traceback
    import re

    # WHY: 本地回退禁止危险操作，避免破坏宿主机环境
    _dangerous = [
        r'\bos\.', r'\bsys\.', r'\bsubprocess\b', r'\bexec\b', r'\beval\b',
        r'\bopen\s*\(', r'__import__', r'\bshutil\b', r'\bsocket\b',
        r'\brequests\b', r'\burllib\b', r'\bhttp', r'\bftp\b',
        r'\b__builtins__\b', r'\bglobals\s*\(', r'\blocals\s*\(', r'\bdir\s*\(',
    ]
    for pattern in _dangerous:
        if re.search(pattern, code, re.IGNORECASE):
            return {
                "status": "error",
                "error": f"本地沙箱禁止危险操作: {pattern}",
            }

    # 安全内置函数 — 禁用完整 __builtins__，仅注入分析所需
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
        "chr": chr, "dict": dict, "divmod": divmod, "enumerate": enumerate,
        "filter": filter, "float": float, "format": format, "frozenset": frozenset,
        "hex": hex, "int": int, "isinstance": isinstance,
        "issubclass": issubclass, "iter": iter, "len": len, "list": list,
        "map": map, "max": max, "min": min, "next": next, "oct": oct,
        "ord": ord, "pow": pow, "print": print, "range": range, "repr": repr,
        "reversed": reversed, "round": round, "set": set, "slice": slice,
        "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
        "zip": zip,
        "None": None, "True": True, "False": False,
    }
    g: dict = {"pd": pd, "np": np, "json": _json, "__builtins__": safe_builtins}
    try:
        data = _json.loads(data_json)
        df = pd.DataFrame(data)
        g["df"] = df

        # 使用受限的 exec 环境
        local_code = (
            "import json as _json, sys, traceback\n"
            "import pandas as pd\n"
            "import numpy as np\n"
            "try:\n"
        )
        for line in code.strip().split("\n"):
            local_code += "    " + line + "\n"
        local_code += (
            "\n    result = {'status': 'success', 'data': {}}\n"
            "    if 'result_df' in dir():\n"
            "        result['data']['table'] = result_df.to_dict('records')\n"
            "    if 'insight' in dir():\n"
            "        result['data']['insight'] = str(insight)\n"
            "    if 'charts' in dir():\n"
            "        result['data']['charts'] = charts\n"
            "except Exception as e:\n"
            "    result = {'status': 'error', 'error': str(e), 'traceback': traceback.format_exc()}\n"
        )
        exec(local_code, g)
        if "result" in g:
            return g["result"]
        return {"status": "error", "error": "exec 未产生 result"}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


def _build_full_code(code: str) -> str:
    """构建沙箱执行的完整代码。缩进必须严格一致。"""
    indented_code = "\n".join("    " + line for line in code.strip().split("\n"))
    return (
        "import json, sys, traceback\n"
        "import pandas as pd\n"
        "import numpy as np\n"
        "try:\n"
        "    data = json.loads(open('/sandbox/data.json' if sys.platform != 'win32' else 'data.json').read())\n"
        "    df = pd.DataFrame(data)\n"
        + indented_code + "\n"
        "    result = {'status': 'success', 'data': {}}\n"
        "    if 'result_df' in dir():\n"
        "        result['data']['table'] = result_df.to_dict('records')\n"
        "    if 'insight' in dir():\n"
        "        result['data']['insight'] = str(insight)\n"
        "    if 'charts' in dir():\n"
        "        result['data']['charts'] = charts\n"
        "except Exception as e:\n"
        "    result = {'status': 'error', 'error': str(e), 'traceback': traceback.format_exc()}\n"
        "open('/sandbox/result.json' if sys.platform != 'win32' else 'result.json', 'w').write(json.dumps(result, ensure_ascii=False, default=str))\n"
    )
