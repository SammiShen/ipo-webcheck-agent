from datetime import datetime
from pathlib import Path
import shutil
from collections.abc import Iterable

import pandas as pd

from runners.common.result_model import SearchRecord


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "output"


def create_batch_output_dir(task_name: str) -> Path:
    """
    创建批量检索输出目录。

    示例：
    output/国家网信办批量检索_20260713_231530
    """
    time_text = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = OUTPUT_ROOT / f"{task_name}_{time_text}"
    output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


def write_records_to_excel(
    records: Iterable[SearchRecord],
    excel_path: str | Path,
) -> Path:
    """
    将统一检索记录写入 Excel。
    """
    output_path = Path(excel_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    record_rows = [record.to_dict() for record in records]

    dataframe = pd.DataFrame(record_rows)
    dataframe.to_excel(output_path, index=False)

    return output_path


def archive_output_dir(output_dir: str | Path) -> str:
    """
    将输出目录压缩为 ZIP。

    ZIP 会保存在输出目录旁边。
    """
    directory = Path(output_dir)

    zip_path = shutil.make_archive(
        base_name=str(directory),
        format="zip",
        root_dir=str(directory),
    )

    return zip_path