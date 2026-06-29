from pathlib import Path
from datetime import datetime
import re
import shutil
import pandas as pd
from PIL import ImageGrab


ZX_URL = "https://zxgk.court.gov.cn/zhzxgk/"


def safe_filename(name: str):
    name = name or "未命名"
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name[:80]

def capture_full_screen(screenshot_path: Path):
    """
    截取整个电脑屏幕，包括任务栏和右下角时间。
    """
    img = ImageGrab.grab(all_screens=True)
    img.save(str(screenshot_path))

def parse_company_items(text: str):
    """
    支持两种输入：

    1. 只有公司名：
       公司A，公司B，公司C

    2. 公司名 + 组织机构代码/统一社会信用代码：
       公司A|统一社会信用代码A
       公司B|统一社会信用代码B
       公司C|统一社会信用代码C
    """
    if not text:
        return []

    text = text.strip()
    items = []

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if len(lines) > 1:
        raw_items = lines
    else:
        raw_items = [x.strip() for x in re.split(r"[，,]", text) if x.strip()]

    for raw in raw_items:
        if "|" in raw:
            company_name, org_code = raw.split("|", 1)
            items.append({
                "company_name": company_name.strip(),
                "org_code": org_code.strip(),
            })
        elif "\t" in raw:
            company_name, org_code = raw.split("\t", 1)
            items.append({
                "company_name": company_name.strip(),
                "org_code": org_code.strip(),
            })
        else:
            items.append({
                "company_name": raw.strip(),
                "org_code": "",
            })

    return items


async def get_visible_inputs(page):
    inputs = page.locator("input")
    count = await inputs.count()

    visible_inputs = []

    for i in range(count):
        item = inputs.nth(i)
        try:
            if await item.is_visible():
                visible_inputs.append(item)
        except Exception:
            continue

    return visible_inputs


async def fill_zx_basic_fields(page, company_name: str, org_code: str = ""):
    """
    执行信息公开网综合查询页一般是：
    第 1 个可见 input：被执行人姓名/名称
    第 2 个可见 input：身份证号码/组织机构代码
    第 3 个可见 input：验证码
    """
    visible_inputs = await get_visible_inputs(page)

    if len(visible_inputs) < 3:
        return False, f"页面中可见输入框数量不足，当前只找到 {len(visible_inputs)} 个。"

    await visible_inputs[0].click()
    await visible_inputs[0].fill(company_name)

    await visible_inputs[1].click()
    await visible_inputs[1].fill(org_code or "")

    # 清空验证码框，等用户手动输入
    await visible_inputs[2].click()
    await visible_inputs[2].fill("")

    return True, "已填写公司名称和组织机构代码，已清空验证码框。"


async def show_agent_tip(page, message: str):
    await page.evaluate(
        """
        (msg) => {
            const id = "ipo-agent-tip";
            let el = document.getElementById(id);

            if (!el) {
                el = document.createElement("div");
                el.id = id;
                document.body.appendChild(el);
            }

            el.innerText = msg;
            el.style.cssText = `
                position: fixed;
                right: 24px;
                bottom: 24px;
                z-index: 999999;
                background: rgba(0, 0, 0, 0.82);
                color: white;
                padding: 14px 18px;
                border-radius: 10px;
                font-size: 16px;
                line-height: 1.6;
                max-width: 420px;
                white-space: pre-line;
                box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            `;
        }
        """,
        message
    )


async def remove_agent_tip(page):
    try:
        await page.evaluate(
            """
            () => {
                const el = document.getElementById("ipo-agent-tip");
                if (el) {
                    el.remove();
                }
            }
            """
        )
    except Exception:
        pass


async def install_query_click_listener(page):
    """
    只监听真正的“查询”按钮。
    不再监听包含“查询”二字的父元素，避免点击输入框/验证码时误触发。
    """
    button_count = await page.evaluate(
        """
        () => {
            window.__ipoAgentRealQueryClicked = 0;

            const candidates = Array.from(
                document.querySelectorAll(
                    "button, input[type='button'], input[type='submit'], a, div, span"
                )
            );

            let count = 0;

            for (const el of candidates) {
                const text = ((el.innerText || el.value || "") + "").trim();
                const rect = el.getBoundingClientRect();

                const visible = rect.width > 0 && rect.height > 0;
                const sizeReasonable = rect.width <= 500 && rect.height <= 200;

                // 关键：必须严格等于“查询”或“搜索”，不能是“综合查询被执行人”
                if (
                    visible &&
                    sizeReasonable &&
                    (text === "查询" || text === "搜索")
                ) {
                    count += 1;

                    el.addEventListener(
                        "click",
                        () => {
                            window.__ipoAgentRealQueryClicked = Date.now();
                        },
                        true
                    );
                }
            }

            return count;
        }
        """
    )

    return button_count


async def wait_for_query_click(page, timeout_ms: int = 120000):
    try:
        await page.wait_for_function(
            "() => window.__ipoAgentRealQueryClicked && window.__ipoAgentRealQueryClicked > 0",
            timeout=timeout_ms
        )
        return True
    except Exception:
        return False


async def save_current_zx_page(page, company_name: str = "执行信息公开网"):
    time_str = datetime.now().strftime("%Y%m%d_%H%M")
    safe_company = safe_filename(company_name or "执行信息公开网")

    output_dir = Path("../output") / f"{safe_company}_执行信息公开网截图_{time_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = output_dir / f"001_执行信息公开网_{safe_company}.png"
    excel_path = output_dir / "执行信息公开网截图记录.xlsx"

    await page.bring_to_front()
    await page.wait_for_timeout(1000)

    capture_full_screen(screenshot_path)

    record = {
        "检索网站": "中国执行信息公开网",
        "检索关键词": company_name,
        "页面地址": page.url,
        "截图时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "截图路径": str(screenshot_path),
        "备注": "用户已手动完成查询，系统仅截图留痕。",
    }

    df = pd.DataFrame([record])
    df.to_excel(excel_path, index=False)

    zip_path_str = shutil.make_archive(
        base_name=str(output_dir),
        format="zip",
        root_dir=str(output_dir)
    )

    zip_path = Path(zip_path_str)

    return zip_path, excel_path, "已保存当前执行信息公开网页面截图。"


async def run_zx_human_batch_with_page(
    page,
    company_names_text: str,
    wait_seconds: int = 120,
    screenshot_delay_seconds: int = 3,
):
    """
    执行信息公开网半自动批量检索：

    程序自动填写公司名/组织机构代码；
    用户手动填写验证码并点击网页查询按钮；
    程序检测到点击查询后等待 3 秒并截图；
    然后进入下一家公司。
    """
    items = parse_company_items(company_names_text)
    await page.bring_to_front()
    await page.wait_for_timeout(500)

    if "zxgk.court.gov.cn" not in page.url:
        raise RuntimeError(f"当前连接的不是执行信息公开网页面，当前页面地址为：{page.url}")
    time_str = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path("../output") / f"执行信息公开网半自动批量检索_{time_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []

    total = len(items)

    for index, item in enumerate(items, start=1):
        company_name = item["company_name"]
        org_code = item["org_code"]

        safe_company = safe_filename(company_name)
        screenshot_path = output_dir / f"{index:03d}_{safe_company}_执行信息公开网.png"

        record = {
            "检索网站": "中国执行信息公开网",
            "检索模块": "综合查询被执行人",
            "序号": index,
            "检索关键词": company_name,
            "组织机构代码/统一社会信用代码": org_code,
            "页面地址": page.url,
            "截图时间": "",
            "截图路径": str(screenshot_path),
            "备注": "",
        }

        try:
            await page.bring_to_front()
            await page.wait_for_timeout(800)

            filled, fill_msg = await fill_zx_basic_fields(
                page=page,
                company_name=company_name,
                org_code=org_code,
            )

            button_count = await install_query_click_listener(page)

            if button_count == 0:
                await remove_agent_tip(page)
                raise RuntimeError(
                    "没有找到真正的网页查询按钮。请确认当前页面是执行信息公开网查询页。"
                )

            tip = (
                f"IPO网核Agent：执行信息公开网半自动检索\n\n"
                f"当前进度：第 {index} / {total} 家\n"
                f"当前公司：{company_name}\n\n"
                f"请在页面中：\n"
                f"1. 补全组织机构代码/统一社会信用代码；\n"
                f"2. 输入验证码；\n"
                f"3. 点击网页上的红色「查询」按钮。\n\n"
                f"点击查询后，我会等待 {screenshot_delay_seconds} 秒自动截图，并进入下一家公司。"
            )

            await show_agent_tip(page, tip)

            clicked = await wait_for_query_click(
                page,
                timeout_ms=wait_seconds * 1000
            )

            await remove_agent_tip(page)

            if not clicked:
                await remove_agent_tip(page)
                raise RuntimeError(
                    f"第 {index} 家公司等待用户点击网页查询按钮超时，已停止批量检索。"
                )

            await page.wait_for_timeout(screenshot_delay_seconds * 1000)

            capture_full_screen(screenshot_path)

            record["备注"] = f"{fill_msg} 已检测到用户点击查询，等待 {screenshot_delay_seconds} 秒后截图。"

            record["截图时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        except Exception as e:
            record["备注"] = f"检索失败：{type(e).__name__}: {e}"

            try:
                await remove_agent_tip(page)
                await page.screenshot(
                    path=str(screenshot_path),
                    full_page=True
                )
                record["截图时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        records.append(record)

    excel_path = output_dir / "执行信息公开网半自动批量检索记录.xlsx"

    df = pd.DataFrame(records)
    df.to_excel(excel_path, index=False)

    zip_path_str = shutil.make_archive(
        base_name=str(output_dir),
        format="zip",
        root_dir=str(output_dir)
    )

    zip_path = Path(zip_path_str)

    message = f"执行信息公开网半自动批量检索完成，共处理 {len(items)} 家公司。"

    return zip_path, excel_path, message