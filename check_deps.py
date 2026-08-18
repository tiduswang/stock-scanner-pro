# -*- coding: utf-8 -*-
"""检查依赖是否安装"""
import sys

deps = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "akshare": "akshare",
    "pandas": "pandas",
    "numpy": "numpy",
    "pypinyin": "pypinyin",
    "httpx": "httpx",
    "dotenv": "python-dotenv",
    "loguru": "loguru",
    "cachetools": "cachetools",
    "pydantic_settings": "pydantic-settings",
    "bs4": "beautifulsoup4",
    "lxml": "lxml",
    "ollama": "ollama",
}

ok = []
missing = []
for mod, pkg in deps.items():
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "?")
        ok.append(f"  ✓ {pkg} ({ver})")
    except ImportError:
        missing.append(pkg)

print("=" * 50)
print(f"已安装: {len(ok)}/{len(deps)}")
print("\n".join(ok))
if missing:
    print(f"\n缺失: {len(missing)} 个")
    print("  " + ", ".join(missing))
    print(f"\n请运行: pip install {' '.join(missing)}")
    sys.exit(1)
else:
    print("\n全部依赖已就绪 ✅")
    sys.exit(0)
