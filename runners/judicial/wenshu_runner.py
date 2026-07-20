from pathlib import Path

from runners.common.output_manager import (
    archive_output_dir,
    create_batch_output_dir,
    write_records_to_excel,
)
from runners.common.result_model import SearchRecord
from runners.common.runner_utils import (
    parse_keywords,
    safe_filename,
)
from runners.common.screenshot_manager import (
    capture_page_screenshot,
)


COURT_URL = "https://wenshu.court.gov.cn/"
COURT_SITE_NAME = "中国裁判文书网"


async def perform_court_search(
    page,
    company_name: str,
) -> None:
    """
    在中国裁判文书网执行一次检索。

    该函数只负责网页操作，不负责：
    - 创建文件夹；
    - 截图命名；
    - Excel；
    - ZIP；
    - 状态记录。
    """
    await page.bring_to_front()

    # 每次检索都重新回到首页，
    # 避免上一次关键词或搜索状态影响本次检索。
    await page.goto(
        COURT_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    await page.wait_for_timeout(3000)

    search_box = page.locator("input:visible").first

    await search_box.click()

    # 直接清空输入框，比在 Mac 上使用 Control+A 更稳定。
    await search_box.fill("")

    # 保留逐字输入效果，避免部分网站无法响应瞬间填充。
    await search_box.type(
        company_name,
        delay=50,
    )

    search_button = page.locator("text=搜索").first

    await search_button.click()

    # 暂时保留原来的等待时间。
    # 后续确认页面结构稳定后，再改成等待具体结果元素。
    await page.wait_for_timeout(8000)


async def search_single_company(
    page,
    company_name: str,
    index: int,
    total: int,
    output_dir: Path,
) -> tuple[SearchRecord, Path, str]:
    """
    检索一个公司，并生成截图及结构化记录。

    该函数会同时被：
    - 单次检索；
    - 批量检索

    共同调用，避免重复两套网页操作代码。
    """
    safe_company_name = safe_filename(company_name)

    screenshot_path = (
        output_dir
        / f"{index:03d}_中国裁判文书网_{safe_company_name}.png"
    )

    record = SearchRecord(
        index=index,
        site_name=COURT_SITE_NAME,
        keyword=company_name,
        screenshot_file=screenshot_path.name,
    )

    try:
        await perform_court_search(
            page=page,
            company_name=company_name,
        )

        await capture_page_screenshot(
            page=page,
            path=screenshot_path,
            full_page=True,
        )

        record.mark_success(
            page_title=await page.title(),
            url=page.url,
        )

        status_text = (
            f"【{index}/{total}】"
            f"{company_name}：成功"
        )

    except Exception as exc:
        record.mark_failed(exc)

        status_text = (
            f"【{index}/{total}】"
            f"{company_name}：失败 - {exc}"
        )

        # 即使检索失败，也尽量保存当前网页，
        # 方便判断是登录失效、验证码、网页异常还是网络错误。
        try:
            await capture_page_screenshot(
                page=page,
                path=screenshot_path,
                full_page=True,
            )

        except Exception as screenshot_error:
            record.screenshot_file = ""

            print(
                "裁判文书网失败现场截图保存失败："
                f"{screenshot_error}"
            )

    return record, screenshot_path, status_text


async def run_court_search_with_page(
    page,
    company_name: str,
):
    """
    中国裁判文书网单个公司检索入口。

    保留原函数名称和返回值结构，
    避免影响 app.py 和 Gradio。
    """
    company_name = company_name.strip()

    if not company_name:
        return None, None, "请输入公司名称。"

    safe_company_name = safe_filename(company_name)

    output_dir = create_batch_output_dir(
        f"{safe_company_name}_裁判文书网"
    )

    record, screenshot_path, _ = await search_single_company(
        page=page,
        company_name=company_name,
        index=1,
        total=1,
        output_dir=output_dir,
    )

    excel_path = write_records_to_excel(
        records=[record],
        excel_path=output_dir / "裁判文书网检索记录.xlsx",
    )

    message = (
        f"状态：{record.status}\n"
        f"保存目录：{output_dir}"
    )

    if record.error_message:
        message += (
            f"\n失败原因：{record.error_message}"
        )

    return (
        str(screenshot_path)
        if screenshot_path.exists()
        else None,
        str(excel_path)
        if excel_path.exists()
        else None,
        message,
    )


async def run_court_search_batch_with_page(
    page,
    company_names_text: str,
):
    """
    中国裁判文书网批量检索入口。

    支持：
    - 中文逗号；
    - 英文逗号；
    - 换行。
    """
    company_names = parse_keywords(
        company_names_text
    )

    if not company_names:
        return None, None, "请输入至少一个公司名称。"

    batch_dir = create_batch_output_dir(
        "裁判文书网批量检索"
    )

    records: list[SearchRecord] = []
    statuses: list[str] = []

    for index, company_name in enumerate(
        company_names,
        start=1,
    ):
        record, _, status_text = await search_single_company(
            page=page,
            company_name=company_name,
            index=index,
            total=len(company_names),
            output_dir=batch_dir,
        )

        records.append(record)
        statuses.append(status_text)

    excel_path = write_records_to_excel(
        records=records,
        excel_path=(
            batch_dir
            / "裁判文书网批量检索记录.xlsx"
        ),
    )

    zip_path = archive_output_dir(
        batch_dir
    )

    status_text = (
        "批量检索完成。\n"
        f"保存目录：{batch_dir}\n"
        f"压缩包：{zip_path}\n\n"
        + "\n".join(statuses)
    )

    return (
        zip_path,
        excel_path,
        status_text,
    )