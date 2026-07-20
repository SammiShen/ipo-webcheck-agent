"""
兼容旧的执行信息公开网导入路径。

真正的 runner 已迁移至：
runners.judicial.zhixing_runner
"""

from runners.judicial.zhixing_runner import (
    ZX_URL,
    run_zx_human_batch_with_page,
    save_current_zx_page,
)

__all__ = [
    "ZX_URL",
    "run_zx_human_batch_with_page",
    "save_current_zx_page",
]