from pathlib import Path
from datetime import datetime
import re
import shutil
import pandas as pd
from PIL import ImageGrab

CAC_URL = "https://www.cac.gov.cn/"


def safe_filename(name: str):
    return re.sub(r'[\\/:*?"<>|]', "_", name)[:80]


def capture_full_screen(path):
    img = ImageGrab.grab(all_screens=True)
    img.save(str(path))

async def restore_browser_window(page, width=1440, height=900):
    try:
        session = await page.context.new_cdp_session(page)
        info = await session.send("Browser.getWindowForTarget")
        window_id = info["windowId"]

        await session.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {
                "windowState": "normal",
                "width": width,
                "height": height,
                "left": 50,
                "top": 30,
            }
        })
    except Exception as e:
        print("恢复窗口大小失败：", e)

async def run_cac_search_batch_with_page(context, page, keywords_text: str):
    keywords = [
        x.strip()
        for x in re.split(r"[，,\n]", keywords_text)
        if x.strip()
    ]

    if not keywords:
        return None, None, "请输入检索关键词。"

    time_str = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path("../output") / f"国家网信办批量检索_{time_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    statuses = []

    for idx, keyword in enumerate(keywords, start=1):
        safe_keyword = safe_filename(keyword)
        screenshot_path = output_dir / f"{idx:03d}_国家网信办_{safe_keyword}.png"

        record = {
            "序号": idx,
            "检索网站": "国家互联网信息办公室",
            "检索关键词": keyword,
            "截图文件": screenshot_path.name,
            "网页标题": "",
            "URL": "",
            "检索时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "状态": "成功",
            "失败原因": "",
        }

        try:
            await page.bring_to_front()
            await page.goto(CAC_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)

            search_box = page.locator("input[type='text'], input").first
            await search_box.click()
            await search_box.fill(keyword)

            # 点击搜索后会新开页面，所以要监听新 page
            async with context.expect_page() as new_page_info:
                await page.keyboard.press("Enter")

            result_page = await new_page_info.value
            await result_page.wait_for_load_state("domcontentloaded", timeout=60000)
            await result_page.wait_for_timeout(3000)
            await result_page.bring_to_front()
            await restore_browser_window(result_page)
            await result_page.wait_for_timeout(1000)

            capture_full_screen(screenshot_path)

            record["网页标题"] = await result_page.title()
            record["URL"] = result_page.url

            statuses.append(f"【{idx}/{len(keywords)}】{keyword}：成功")

            await result_page.close()

        except Exception as e:
            record["状态"] = "失败"
            record["失败原因"] = str(e)
            statuses.append(f"【{idx}/{len(keywords)}】{keyword}：失败 - {e}")

            try:
                capture_full_screen(screenshot_path)
            except Exception:
                record["截图文件"] = ""

        records.append(record)

    excel_path = output_dir / "国家网信办批量检索记录.xlsx"
    pd.DataFrame(records).to_excel(excel_path, index=False)

    zip_path = shutil.make_archive(
        base_name=str(output_dir),
        format="zip",
        root_dir=str(output_dir)
    )

    return zip_path, excel_path, (
        f"国家网信办批量检索完成。\n保存目录：{output_dir}\n压缩包：{zip_path}\n\n"
        + "\n".join(statuses)
    )