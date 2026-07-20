from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def current_time_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class SearchRecord:
    """
    单次网站检索记录。

    extra_fields 用于保存某个网站独有的字段，例如：
    - 检索模块
    - 统一社会信用代码
    - 备注
    """

    index: int
    site_name: str
    keyword: str
    screenshot_file: str = ""
    page_title: str = ""
    url: str = ""
    checked_at: str = field(default_factory=current_time_text)
    status: str = "成功"
    error_message: str = ""
    extra_fields: dict[str, Any] = field(default_factory=dict)

    def mark_success(
        self,
        *,
        page_title: str = "",
        url: str = "",
    ) -> None:
        self.status = "成功"
        self.page_title = page_title
        self.url = url
        self.error_message = ""
        self.checked_at = current_time_text()

    def mark_failed(self, error: Exception | str) -> None:
        self.status = "失败"
        self.error_message = str(error)
        self.checked_at = current_time_text()

    def set_extra(self, **fields: Any) -> None:
        self.extra_fields.update(fields)

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "序号": self.index,
            "检索网站": self.site_name,
            "检索关键词": self.keyword,
        }

        # 网站专属字段放在关键词之后。
        row.update(self.extra_fields)

        row.update(
            {
                "截图文件": self.screenshot_file,
                "网页标题": self.page_title,
                "URL": self.url,
                "检索时间": self.checked_at,
                "状态": self.status,
                "失败原因": self.error_message,
            }
        )

        return row