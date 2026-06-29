from pathlib import Path
from datetime import datetime
import re
import shutil
import pandas as pd
from PIL import ImageGrab

MIIT_URL = "https://www.miit.gov.cn/search/index.html?websiteid=110000000000000&pg=&p=&tpl=&category=&jsflIndexSeleted=&q=1"


def safe_filename(name: str):
    return re.sub(r'[\\/:*?"<>|]', "_", name)[:80]


def capture_full_screen(path: Path):
    img = ImageGrab.grab(all_screens=True)
    img.save(str(path))


async def run_miit_search_batch_with_page(page, company_names_text: str):
    company_names = [
        x.strip()
        for x in re.split(r"[，,\n]", company_names_text)
        if x.strip()
    ]

    if not company_names:
        return None, None, "请输入公司名称。"

    time_str = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path("../output") / f"工信部批量检索_{time_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    statuses = []

    for idx, company_name in enumerate(company_names, start=1):
        safe_name = safe_filename(company_name)
        screenshot_path = output_dir / f"{idx:03d}_工信部_{safe_name}.png"

        record = {
            "序号": idx,
            "检索网站": "工业和信息化部统一检索平台",
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
            await page.goto(MIIT_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)

            await page.locator("#q").fill(company_name)

            await page.evaluate(
                """
                (keyword) => {
                    const q = document.querySelector("#q");
                    if (q) q.value = keyword;

                    const pq = document.querySelector("#pq");
                    if (!pq) throw new Error("未找到 #pq");

                    let el = pq;
                    for (let i = 0; i < 8 && el; i++) {
                        el.style.display = "block";
                        el.style.visibility = "visible";
                        el.style.opacity = "1";
                        el = el.parentElement;
                    }

                    pq.value = keyword;
                    pq.dispatchEvent(new Event("input", { bubbles: true }));
                    pq.dispatchEvent(new Event("change", { bubbles: true }));
                }
                """,
                company_name
            )

            # 用 JS 触发搜索按钮，比 Playwright click 更稳
            await page.evaluate("""
            () => {
                const btn = document.querySelector("#ipt_btn");
                if (!btn) throw new Error("未找到搜索按钮 #ipt_btn");
                btn.click();
            }
            """)

            await page.wait_for_timeout(6000)

            await page.bring_to_front()
            await page.wait_for_timeout(1000)
            capture_full_screen(screenshot_path)

            record["网页标题"] = await page.title()
            record["URL"] = page.url
            statuses.append(f"【{idx}/{len(company_names)}】{company_name}：成功")



        except Exception as e:
            record["状态"] = "失败"
            record["失败原因"] = str(e)
            statuses.append(f"【{idx}/{len(company_names)}】{company_name}：失败 - {e}")

            try:
                capture_full_screen(screenshot_path)
            except Exception:
                record["截图文件"] = ""

        records.append(record)

    excel_path = output_dir / "工信部批量检索记录.xlsx"
    pd.DataFrame(records).to_excel(excel_path, index=False)

    zip_path = shutil.make_archive(
        base_name=str(output_dir),
        format="zip",
        root_dir=str(output_dir)
    )

    return zip_path, excel_path, (
        f"工信部批量检索完成。\n保存目录：{output_dir}\n压缩包：{zip_path}\n\n"
        + "\n".join(statuses)
    )