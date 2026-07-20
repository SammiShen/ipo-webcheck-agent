from pathlib import Path
import re

from runners.common.output_manager import (
    archive_output_dir,
    create_batch_output_dir,
    write_records_to_excel,
)
from runners.common.result_model import SearchRecord
from runners.common.runner_utils import safe_filename
from runners.common.screenshot_manager import (
    capture_full_screen,
    capture_page_screenshot,
)


ZX_URL = "https://zxgk.court.gov.cn/zhixing/"
ZX_FALLBACK_URL = "https://zxgk.court.gov.cn/zhzxgk/"
ZX_SITE_NAME = "中国执行信息公开网"
ZX_MODULE_NAME = "综合查询被执行人"


def parse_company_items(text: str) -> list[dict[str, str]]:
    """
    支持以下输入格式：

    1. 只有公司名称，以逗号、中文逗号或换行分隔：

       公司A，公司B，公司C

    2. 公司名称 + 统一社会信用代码：

       公司A|统一社会信用代码A
       公司B|统一社会信用代码B

    也支持从 Excel 复制形成的制表符格式：

       公司A    统一社会信用代码A
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) > 1:
        raw_items = lines
    else:
        raw_items = [
            item.strip()
            for item in re.split(r"[，,]", text)
            if item.strip()
        ]

    items: list[dict[str, str]] = []

    for raw_item in raw_items:
        if "|" in raw_item:
            company_name, org_code = raw_item.split("|", 1)

        elif "\t" in raw_item:
            company_name, org_code = raw_item.split("\t", 1)

        else:
            company_name = raw_item
            org_code = ""

        company_name = company_name.strip()
        org_code = org_code.strip()

        if not company_name:
            continue

        items.append(
            {
                "company_name": company_name,
                "org_code": org_code,
            }
        )

    return items


async def get_visible_inputs(page) -> list:
    """
    获取当前页面中所有可见的 input 元素。
    """
    inputs = page.locator("input")
    input_count = await inputs.count()

    visible_inputs = []

    for index in range(input_count):
        input_element = inputs.nth(index)

        try:
            if await input_element.is_visible():
                visible_inputs.append(input_element)
        except Exception:
            continue

    return visible_inputs


async def fill_zx_basic_fields(
    page,
    company_name: str,
    org_code: str = "",
) -> tuple[bool, str]:
    """
    综合查询页通常包含：

    第 1 个可见输入框：被执行人姓名或名称；
    第 2 个可见输入框：身份证号码或组织机构代码；
    第 3 个可见输入框：验证码。
    """
    visible_inputs = await get_visible_inputs(page)

    if len(visible_inputs) < 3:
        return (
            False,
            f"页面中可见输入框数量不足，"
            f"当前只找到 {len(visible_inputs)} 个。",
        )

    company_input = visible_inputs[0]
    org_code_input = visible_inputs[1]
    captcha_input = visible_inputs[2]

    await company_input.click()
    await company_input.fill(company_name)

    await org_code_input.click()
    await org_code_input.fill(org_code or "")

    # 验证码仍由用户手动填写。
    await captcha_input.click()
    await captcha_input.fill("")

    return (
        True,
        "已填写公司名称和组织机构代码，"
        "并清空验证码输入框。",
    )


async def show_agent_tip(
    page,
    message: str,
) -> None:
    """
    在网页右下角显示操作提示。
    """
    await page.evaluate(
        """
        (msg) => {
            const id = "ipo-agent-tip";
            let element = document.getElementById(id);

            if (!element) {
                element = document.createElement("div");
                element.id = id;
                document.body.appendChild(element);
            }

            element.innerText = msg;

            element.style.cssText = `
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
        message,
    )


async def remove_agent_tip(page) -> None:
    """
    移除网页右下角的操作提示。
    """
    try:
        await page.evaluate(
            """
            () => {
                const element =
                    document.getElementById("ipo-agent-tip");

                if (element) {
                    element.remove();
                }
            }
            """
        )
    except Exception:
        # 页面可能已经刷新或跳转，移除失败不影响主流程。
        pass


async def install_query_click_listener(page) -> int:
    """
    监听文本严格等于“查询”或“搜索”的按钮。

    避免监听到“综合查询被执行人”等包含“查询”
    但并非真正操作按钮的元素。
    """
    button_count = await page.evaluate(
        """
        () => {
            window.__ipoAgentRealQueryClicked = 0;

            const candidates = Array.from(
                document.querySelectorAll(
                    "button, input[type='button'], " +
                    "input[type='submit'], a, div, span"
                )
            );

            let count = 0;

            for (const element of candidates) {
                const text = (
                    (
                        element.innerText ||
                        element.value ||
                        ""
                    ) + ""
                ).trim();

                const rect = element.getBoundingClientRect();

                const visible =
                    rect.width > 0 &&
                    rect.height > 0;

                const sizeReasonable =
                    rect.width <= 500 &&
                    rect.height <= 200;

                const isQueryButton =
                    text === "查询" ||
                    text === "搜索";

                if (
                    visible &&
                    sizeReasonable &&
                    isQueryButton
                ) {
                    count += 1;

                    /*
                    避免在同一个按钮上重复安装监听器。
                    页面刷新后，新按钮仍会重新安装。
                    */
                    if (
                        element.dataset
                            .ipoAgentListenerInstalled !== "1"
                    ) {
                        element.addEventListener(
                            "click",
                            () => {
                                window
                                    .__ipoAgentRealQueryClicked =
                                    Date.now();
                            },
                            true
                        );

                        element.dataset
                            .ipoAgentListenerInstalled = "1";
                    }
                }
            }

            return count;
        }
        """
    )

    return button_count


async def wait_for_query_click(
    page,
    timeout_ms: int = 120000,
) -> bool:
    """
    等待用户点击网页查询按钮。
    """
    try:
        await page.wait_for_function(
            """
            () =>
                window.__ipoAgentRealQueryClicked &&
                window.__ipoAgentRealQueryClicked > 0
            """,
            timeout=timeout_ms,
        )

        return True

    except Exception:
        return False


async def validate_zx_page(page) -> None:
    """
    确认当前连接的是中国执行信息公开网。
    """
    if "zxgk.court.gov.cn" not in page.url:
        raise RuntimeError(
            "当前连接的不是中国执行信息公开网页面。"
            f"当前页面地址为：{page.url}"
        )


async def save_current_zx_page(
    page,
    company_name: str = "执行信息公开网",
):
    """
    保存用户当前已经手动完成查询的页面。

    返回：
        ZIP 路径；
        Excel 路径；
        状态信息。
    """
    company_name = (
        company_name.strip()
        if company_name
        else "执行信息公开网"
    )

    safe_company_name = safe_filename(
        company_name or "执行信息公开网"
    )

    output_dir = create_batch_output_dir(
        f"{safe_company_name}_执行信息公开网截图"
    )

    screenshot_path = (
        output_dir
        / f"001_执行信息公开网_{safe_company_name}.png"
    )

    await page.bring_to_front()
    await page.wait_for_timeout(1000)

    record = SearchRecord(
        index=1,
        site_name=ZX_SITE_NAME,
        keyword=company_name,
        screenshot_file=screenshot_path.name,
        extra_fields={
            "检索模块": ZX_MODULE_NAME,
            "组织机构代码/统一社会信用代码": "",
            "备注": "用户已手动完成查询，系统仅截图留痕。",
        },
    )

    try:
        capture_full_screen(screenshot_path)

        record.mark_success(
            page_title=await page.title(),
            url=page.url,
        )

    except Exception as exc:
        record.mark_failed(exc)

        try:
            await capture_page_screenshot(
                page=page,
                path=screenshot_path,
                full_page=True,
            )
        except Exception:
            record.screenshot_file = ""

    excel_path = write_records_to_excel(
        records=[record],
        excel_path=(
            output_dir
            / "执行信息公开网截图记录.xlsx"
        ),
    )

    zip_path = archive_output_dir(output_dir)

    message = (
        f"状态：{record.status}\n"
        f"保存目录：{output_dir}"
    )

    if record.error_message:
        message += (
            f"\n失败原因：{record.error_message}"
        )

    return zip_path, excel_path, message


async def search_single_company_human_assisted(
    page,
    company_name: str,
    org_code: str,
    index: int,
    total: int,
    output_dir: Path,
    wait_seconds: int,
    screenshot_delay_seconds: int,
) -> tuple[SearchRecord, str]:
    """
    半自动检索一家企业：

    1. 自动填写企业名称和统一社会信用代码；
    2. 用户填写验证码；
    3. 用户点击网页查询按钮；
    4. Agent 检测到点击后等待并截图。
    """
    safe_company_name = safe_filename(company_name)

    screenshot_path = (
        output_dir
        / f"{index:03d}_{safe_company_name}_执行信息公开网.png"
    )

    record = SearchRecord(
        index=index,
        site_name=ZX_SITE_NAME,
        keyword=company_name,
        screenshot_file=screenshot_path.name,
        extra_fields={
            "检索模块": ZX_MODULE_NAME,
            "组织机构代码/统一社会信用代码": org_code,
            "备注": "",
        },
    )

    try:
        await page.bring_to_front()
        await page.wait_for_timeout(800)

        filled, fill_message = await fill_zx_basic_fields(
            page=page,
            company_name=company_name,
            org_code=org_code,
        )

        # 原代码虽然取得了 filled，但没有判断。
        # 现在若输入框不足，会明确进入失败记录。
        if not filled:
            raise RuntimeError(fill_message)

        button_count = await install_query_click_listener(page)

        if button_count == 0:
            raise RuntimeError(
                "没有找到真正的网页查询按钮。"
                "请确认当前页面是执行信息公开网查询页。"
            )

        tip_message = (
            "IPO网核Agent：执行信息公开网半自动检索\n\n"
            f"当前进度：第 {index} / {total} 家\n"
            f"当前公司：{company_name}\n\n"
            "请在页面中：\n"
            "1. 检查或补全组织机构代码/统一社会信用代码；\n"
            "2. 输入验证码；\n"
            "3. 点击网页上的红色「查询」按钮。\n\n"
            f"点击查询后，我会等待 "
            f"{screenshot_delay_seconds} 秒自动截图，"
            "然后进入下一家公司。"
        )

        await show_agent_tip(
            page=page,
            message=tip_message,
        )

        clicked = await wait_for_query_click(
            page=page,
            timeout_ms=wait_seconds * 1000,
        )

        if not clicked:
            raise RuntimeError(
                f"等待第 {index} 家公司的查询操作超时。"
                "已记录失败，并将继续处理下一家公司。"
            )

        await page.wait_for_timeout(
            screenshot_delay_seconds * 1000
        )

        capture_full_screen(screenshot_path)

        record.set_extra(
            备注=(
                f"{fill_message}"
                f"已检测到用户点击查询，等待 "
                f"{screenshot_delay_seconds} 秒后截图。"
            )
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

        record.set_extra(
            备注=(
                f"检索失败："
                f"{type(exc).__name__}: {exc}"
            )
        )

        status_text = (
            f"【{index}/{total}】"
            f"{company_name}：失败 - {exc}"
        )

        # 失败时保留网页现场，方便后续判断原因。
        try:
            await capture_page_screenshot(
                page=page,
                path=screenshot_path,
                full_page=True,
            )

        except Exception as screenshot_error:
            record.screenshot_file = ""

            print(
                "执行信息公开网失败现场截图保存失败："
                f"{screenshot_error}"
            )

    finally:
        await remove_agent_tip(page)

    return record, status_text


async def run_zx_human_batch_with_page(
    page,
    company_names_text: str,
    wait_seconds: int = 120,
    screenshot_delay_seconds: int = 3,
):
    """
    中国执行信息公开网半自动批量检索入口。

    程序自动填写公司名称和统一社会信用代码；
    用户手动输入验证码并点击查询；
    程序检测点击后自动截图并处理下一家公司。
    """
    items = parse_company_items(company_names_text)

    if not items:
        return (
            None,
            None,
            "请输入至少一个公司名称。",
        )

    await page.bring_to_front()
    await page.wait_for_timeout(500)

    await validate_zx_page(page)

    output_dir = create_batch_output_dir(
        "执行信息公开网半自动批量检索"
    )

    records: list[SearchRecord] = []
    statuses: list[str] = []

    total = len(items)

    for index, item in enumerate(
        items,
        start=1,
    ):
        record, status_text = (
            await search_single_company_human_assisted(
                page=page,
                company_name=item["company_name"],
                org_code=item["org_code"],
                index=index,
                total=total,
                output_dir=output_dir,
                wait_seconds=wait_seconds,
                screenshot_delay_seconds=(
                    screenshot_delay_seconds
                ),
            )
        )

        records.append(record)
        statuses.append(status_text)

    excel_path = write_records_to_excel(
        records=records,
        excel_path=(
            output_dir
            / "执行信息公开网半自动批量检索记录.xlsx"
        ),
    )

    zip_path = archive_output_dir(output_dir)

    success_count = sum(
        record.status == "成功"
        for record in records
    )

    failed_count = len(records) - success_count

    message = (
        "执行信息公开网半自动批量检索完成。\n"
        f"共处理：{len(records)} 家公司\n"
        f"成功：{success_count} 家\n"
        f"失败：{failed_count} 家\n"
        f"保存目录：{output_dir}\n"
        f"压缩包：{zip_path}\n\n"
        + "\n".join(statuses)
    )

    return zip_path, excel_path, message