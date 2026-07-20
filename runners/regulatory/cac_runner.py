from pathlib import Path

from runners.common.browser_manager import restore_browser_window
from runners.common.output_manager import (
    archive_output_dir,
    create_batch_output_dir,
    write_records_to_excel,
)
from runners.common.result_model import SearchRecord
from runners.common.runner_utils import parse_keywords, safe_filename
from runners.common.screenshot_manager import capture_full_screen


CAC_URL = "https://www.cac.gov.cn/"
CAC_SITE_NAME = "国家互联网信息办公室"


async def search_single_keyword(
    context,
    page,
    keyword: str,
    index: int,
    total: int,
    output_dir: Path,
) -> tuple[SearchRecord, str]:
    """
    在国家网信办网站检索单个关键词。

    返回：
        SearchRecord：结构化检索记录；
        str：用于界面显示的进度信息。
    """
    safe_keyword = safe_filename(keyword)

    screenshot_path = (
        output_dir
        / f"{index:03d}_国家网信办_{safe_keyword}.png"
    )

    record = SearchRecord(
        index=index,
        site_name=CAC_SITE_NAME,
        keyword=keyword,
        screenshot_file=screenshot_path.name,
    )

    result_page = None

    try:
        # 每个关键词开始前重新进入首页，
        # 避免上一次检索状态干扰下一次。
        await page.bring_to_front()

        await page.goto(
            CAC_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        await page.wait_for_timeout(2000)

        search_box = page.locator(
            "input[type='text'], input"
        ).first

        await search_box.click()
        await search_box.fill(keyword)

        # 国家网信办点击搜索后会打开新页面。
        async with context.expect_page(timeout=60000) as new_page_info:
            await page.keyboard.press("Enter")

        result_page = await new_page_info.value

        await result_page.wait_for_load_state(
            "domcontentloaded",
            timeout=60000,
        )

        await result_page.wait_for_timeout(3000)
        await result_page.bring_to_front()

        await restore_browser_window(result_page)
        await result_page.wait_for_timeout(1000)

        capture_full_screen(screenshot_path)

        record.mark_success(
            page_title=await result_page.title(),
            url=result_page.url,
        )

        status_text = (
            f"【{index}/{total}】{keyword}：成功"
        )

    except Exception as exc:
        record.mark_failed(exc)

        status_text = (
            f"【{index}/{total}】{keyword}：失败 - {exc}"
        )

        # 即使检索失败，也尝试保留现场截图，
        # 方便后续判断是验证码、页面异常还是网络问题。
        try:
            capture_full_screen(screenshot_path)
        except Exception as screenshot_error:
            record.screenshot_file = ""

            print(
                f"失败现场截图保存失败：{screenshot_error}"
            )

    finally:
        # 结果页面无论成功还是失败，都尽量关闭，
        # 避免批量查询后残留大量标签页。
        if result_page is not None:
            try:
                if not result_page.is_closed():
                    await result_page.close()
            except Exception as close_error:
                print(f"关闭结果页面失败：{close_error}")

    return record, status_text


async def run_cac_search_batch_with_page(
    context,
    page,
    keywords_text: str,
):
    """
    国家网信办批量检索入口。

    保留原函数名称和返回值结构，
    避免影响 app.py 与 Gradio 界面。
    """
    keywords = parse_keywords(keywords_text)

    if not keywords:
        return None, None, "请输入检索关键词。"

    output_dir = create_batch_output_dir(
        "国家网信办批量检索"
    )

    records: list[SearchRecord] = []
    statuses: list[str] = []

    for index, keyword in enumerate(keywords, start=1):
        record, status_text = await search_single_keyword(
            context=context,
            page=page,
            keyword=keyword,
            index=index,
            total=len(keywords),
            output_dir=output_dir,
        )

        records.append(record)
        statuses.append(status_text)

    excel_path = write_records_to_excel(
        records=records,
        excel_path=output_dir / "国家网信办批量检索记录.xlsx",
    )

    zip_path = archive_output_dir(output_dir)

    message = (
        "国家网信办批量检索完成。\n"
        f"保存目录：{output_dir}\n"
        f"压缩包：{zip_path}\n\n"
        + "\n".join(statuses)
    )

    return zip_path, excel_path, message