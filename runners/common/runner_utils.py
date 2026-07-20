import re


def safe_filename(name: str, max_length: int = 80) -> str:
    """
    将字符串转换为适合用作文件名的格式。
    """
    cleaned_name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return cleaned_name[:max_length]


def parse_keywords(keywords_text: str) -> list[str]:
    """
    将逗号、中文逗号或换行分隔的文本转换为关键词列表。
    """
    return [
        item.strip()
        for item in re.split(r"[，,\n]", keywords_text)
        if item.strip()
    ]