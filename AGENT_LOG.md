# AGENT_LOG

## 2026-08-09 20:30 · T2.1 / T2.2 · 项目骨架与 CLI 基础入口

触发的流程：

- 按 `PLAN.md` 进入实现阶段。
- 遵循 TDD：先写失败测试，再补最小实现。

关键上下文：

- 冷启动验证后已明确：
  - 构建后端：`setuptools`
  - 包名：`safecodeloop`
  - CLI 命令名：`safecodeloop`
  - 版本号来源：`src/safecodeloop/__init__.py` 的 `__version__`
  - 支持 `python -m safecodeloop.cli` 和 `python -m safecodeloop`

完成内容：

- 新增 `pyproject.toml`。
- 新增 `.gitignore`。
- 新增 `src/safecodeloop/__init__.py`。
- 新增 `src/safecodeloop/__main__.py`。
- 新增 `src/safecodeloop/cli.py`。
- 新增 `tests/test_smoke.py`。
- 新增 `tests/test_cli.py`。

TDD 记录：

- 第一次运行 `python -m pytest` 时，环境缺少 `pytest`，先安装 `pytest`。
- 安装后再次运行，得到预期红灯：`ModuleNotFoundError: No module named 'safecodeloop'`。
- 补充最小包结构和 CLI 后，测试仍有两项失败：`python -m safecodeloop.cli` 没有输出。
- 原因：`cli.py` 缺少 `if __name__ == "__main__"` 模块执行入口。
- 修复后运行 `python -m pytest`，结果：`4 passed in 0.35s`。

人工干预：

- 发现 `src/` 布局下，子进程执行 `python -m safecodeloop` 需要先安装项目。
- 执行 `python -m pip install -e .`，后续 CI/README 也应体现“先安装再测试/运行”的要求。

教训：

- 冷启动验证提出的 packaging/entry point 问题是有效的；如果没有提前修订，T2.1/T2.2 会出现实现口径不一致。
- CLI 模块入口需要同时支持函数调用和 `python -m` 执行，这是后续 release 可用性的基础。
