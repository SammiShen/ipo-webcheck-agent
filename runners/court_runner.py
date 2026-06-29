from pathlib import Path
from datetime import datetime
import re
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime

COURT_URL = "https://wenshu.court.gov.cn/"


def safe_filename(name: str):
    return re.sub(r'[\\/:*?"<>|]', "_", name)


async def run_court_search_with_page(page, company_name: str):
    company_name = company_name.strip()
    safe_company_name = safe_filename(company_name)

    time_str = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path("../output") / f"{safe_company_name}_裁判文书网_{time_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = output_dir / f"001_中国裁判文书网_{safe_company_name}.png"
    excel_path = output_dir / "裁判文书网检索记录.xlsx"

    record = {
        "检索网站": "中国裁判文书网",
        "检索关键词": company_name,
        "截图文件": "",
        "网页标题": "",
        "URL": "",
        "检索时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "状态": "成功",
        "失败原因": "",
    }

    try:
        await page.bring_to_front()

        # 每次检索前回首页，避免关键词叠加
        await page.goto(COURT_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        search_box = page.locator("input:visible").first
        await search_box.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        await page.keyboard.type(company_name, delay=50)

        search_button = page.locator("text=搜索").first
        await search_button.click()

        await page.wait_for_timeout(8000)

        await page.screenshot(path=str(screenshot_path), full_page=True)

        record["截图文件"] = screenshot_path.name
        record["网页标题"] = await page.title()
        record["URL"] = page.url

    except Exception as e:
        record["状态"] = "失败"
        record["失败原因"] = str(e)

        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            record["截图文件"] = screenshot_path.name
        except Exception:
            pass

    pd.DataFrame([record]).to_excel(excel_path, index=False)

    return (
        str(screenshot_path) if screenshot_path.exists() else None,
        str(excel_path) if excel_path.exists() else None,
        f"状态：{record['状态']}\n保存目录：{output_dir}"
        + (f"\n失败原因：{record['失败原因']}" if record["失败原因"] else "")
    )



async def run_court_search_batch_with_page(page, company_names_text: str):
    company_names = [
        name.strip()
        for name in company_names_text.replace("，", ",").split(",")
        if name.strip()
    ]

    if not company_names:
        return None, None, "请输入至少一个公司名称。"

    time_str = datetime.now().strftime("%Y%m%d_%H%M")
    batch_dir = Path("../output") / f"裁判文书网批量检索_{time_str}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    all_records = []
    statuses = []

    for idx, company_name in enumerate(company_names, start=1):
        safe_company_name = safe_filename(company_name)
        screenshot_path = batch_dir / f"{idx:03d}_中国裁判文书网_{safe_company_name}.png"

        record = {
            "序号": idx,
            "检索网站": "中国裁判文书网",
            "检索关键词": company_name,
            "截图文件": screenshot_path.name,
            "网页标题": "",
            "URL": "",
            "检索时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "成功",
            "失败原因": "",
        }

        try:
            await page.bring_to_front()

            await page.goto(
                COURT_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.wait_for_timeout(3000)

            search_box = page.locator("input:visible").first
            await search_box.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            await page.keyboard.type(company_name, delay=50)

            search_button = page.locator("text=搜索").first
            await search_button.click()

            await page.wait_for_timeout(8000)

            await page.screenshot(
                path=str(screenshot_path),
                full_page=True
            )

            record["网页标题"] = await page.title()
            record["URL"] = page.url

            statuses.append(f"【{idx}/{len(company_names)}】{company_name}：成功")

        except Exception as e:
            record["状态"] = "失败"
            record["失败原因"] = str(e)

            try:
                await page.screenshot(
                    path=str(screenshot_path),
                    full_page=True
                )
            except Exception:
                record["截图文件"] = ""

            statuses.append(f"【{idx}/{len(company_names)}】{company_name}：失败 - {e}")

        all_records.append(record)

    excel_path = batch_dir / "裁判文书网批量检索记录.xlsx"
    pd.DataFrame(all_records).to_excel(excel_path, index=False)

    zip_path = shutil.make_archive(
        base_name=str(batch_dir),
        format="zip",
        root_dir=str(batch_dir)
    )

    status_text = (
        f"批量检索完成。\n"
        f"保存目录：{batch_dir}\n"
        f"压缩包：{zip_path}\n\n"
        + "\n".join(statuses)
    )

    return zip_path, excel_path, status_text