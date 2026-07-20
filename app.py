import gradio as gr
from pathlib import Path
from playwright.async_api import async_playwright
import subprocess
import asyncio
import urllib.request
import os
from runners.judicial.wenshu_runner import (
    COURT_URL,
    run_court_search_with_page,
    run_court_search_batch_with_page,
)
from runners.judicial.zhixing_runner import (
    ZX_URL,
    ZX_FALLBACK_URL,
    run_zx_human_batch_with_page,
    save_current_zx_page,
)
from datetime import datetime
from runners.regulatory.cac_runner import (
    CAC_URL,
    run_cac_search_batch_with_page,
)
from runners.miit_runner import MIIT_URL, run_miit_search_batch_with_page

COURT_URL = "https://wenshu.court.gov.cn/"



PROJECT_ROOT = Path(__file__).resolve().parent
PROFILE_ROOT = PROJECT_ROOT / "browser_profiles"

COURT_PROFILE_DIR = PROFILE_ROOT / "court_profile"
ZX_PROFILE_DIR = PROFILE_ROOT / "zx_profile"
CHROME_DEBUG_PROFILE_DIR = PROFILE_ROOT / "chrome_debug_profile"



# 自动创建浏览器配置目录
for profile_dir in (
    COURT_PROFILE_DIR,
    ZX_PROFILE_DIR,
    CHROME_DEBUG_PROFILE_DIR,
):
    profile_dir.mkdir(parents=True, exist_ok=True)

_pw = None
_task_start_time = None
_last_court_message = ""
_last_zx_message = ""

_court_context = None
_court_page = None

_zx_context = None
_zx_page = None
_zx_browser = None
_zx_context = None
_zx_page = None

_cac_context = None
_cac_page = None
_last_cac_message = ""

_miit_context = None
_miit_page = None
_last_miit_message = ""

def to_gradio_file(value):
    if value is None:
        return None
    return str(Path(value).resolve())


# =========================
# 裁判文书网
# =========================
async def open_login_browser():
    global _pw, _court_context, _court_page

    if _court_context is not None and _court_page is not None:
        try:
            if not _court_page.is_closed():
                await _court_page.bring_to_front()
                return "裁判文书网浏览器已经打开，请直接登录或检索。"
        except Exception:
            pass

    if _pw is None:
        _pw = await async_playwright().start()

    try:
        _court_context = await _pw.chromium.launch_persistent_context(
            user_data_dir=COURT_PROFILE_DIR,
            headless=False,
            viewport={"width": 1440, "height": 1000},
            locale="zh-CN",
            ignore_https_errors=True,
        )

        _court_page = await _court_context.new_page()
        await _court_page.goto(
            COURT_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        return "已打开裁判文书网。请在弹出的浏览器中登录，登录后不要关闭浏览器，直接开始检索。"

    except Exception as e:
        return f"打开裁判文书网失败：{type(e).__name__}: {e}"

async def confirm_login():
    global _court_page

    if _court_page is None:
        return "请先点击「打开裁判文书网登录页面」。"

    try:
        if _court_page.is_closed():
            return "裁判文书网页面已经关闭，请重新打开登录页面。"
    except Exception:
        pass

    return "已确认。请不要关闭浏览器，直接输入公司名称检索。"


async def search_court_company(company_names_text):
    global _task_start_time, _last_court_message

    if _task_start_time is None:
        _task_start_time = datetime.now()

    global _court_page

    if not company_names_text or not company_names_text.strip():
        return None, None, "请输入公司名称。"

    if _court_page is None:
        return None, None, "请先点击「打开裁判文书网登录页面」，登录后再检索。"

    try:
        zip_path, excel_path, message = await run_court_search_batch_with_page(
            _court_page,
            company_names_text.strip()
        )

        _last_court_message = str(message)
        return (
            to_gradio_file(zip_path),
            to_gradio_file(excel_path),
            str(message)
        )

    except Exception as e:
        _last_court_message = f"裁判文书网检索失败：{type(e).__name__}: {e}"
        return None, None, f"裁判文书网检索失败：{type(e).__name__}: {e}"


# =========================
# 中国执行信息公开网
# =========================

async def open_zx_browser():
    global _pw
    global _zx_browser
    global _zx_context
    global _zx_page

    if _pw is None:
        _pw = await async_playwright().start()

    # 浏览器已经打开时直接复用，
    # 避免重复占用同一个持久化资料目录。
    if (
        _zx_page is not None
        and not _zx_page.is_closed()
    ):
        async def try_open_zx_url(page, url: str):
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.wait_for_timeout(5000)

            status = response.status if response else None

            try:
                body_text = await page.locator("body").inner_text(
                    timeout=5000
                )
            except Exception:
                body_text = ""

            return {
                "url": page.url,
                "status": status,
                "body_text": body_text.strip(),
            }

    primary_result = None
    fallback_result = None

    try:
        primary_result = await try_open_zx_url(
            target_page,
            ZX_URL,
        )
    except Exception as exc:
        print(f"打开被执行人查询页失败：{exc}")

    # 页面返回 403、其他错误状态，或者整个 body 为空时，
    # 再尝试综合查询入口。
    primary_failed = (
            primary_result is None
            or (
                    primary_result["status"] is not None
                    and primary_result["status"] >= 400
            )
            or not primary_result["body_text"]
    )

    if primary_failed:
        try:
            fallback_result = await try_open_zx_url(
                target_page,
                ZX_FALLBACK_URL,
            )
        except Exception as exc:
            print(f"打开执行网综合查询页失败：{exc}")

        fallback_failed = (
                fallback_result is None
                or (
                        fallback_result["status"] is not None
                        and fallback_result["status"] >= 400
                )
                or not fallback_result["body_text"]
        )

        if fallback_failed:
            primary_status = (
                primary_result["status"]
                if primary_result
                else "无响应"
            )

            fallback_status = (
                fallback_result["status"]
                if fallback_result
                else "无响应"
            )

            _zx_page = target_page

            return (
                "浏览器已经成功启动，但执行信息公开网页面未正常返回内容。\n"
                f"被执行人查询页状态：{primary_status}\n"
                f"综合查询页状态：{fallback_status}\n\n"
                "这通常是网站访问限制或当前网络环境导致的，"
                "不是 Chrome 启动失败。"
            )


async def capture_zx_page(company_names_text):
    global _zx_page

    if _zx_page is None:
        return None, None, "请先点击「打开执行信息公开网」。"

    company_name = "执行信息公开网"
    if company_names_text and company_names_text.strip():
        company_name = company_names_text.strip()

    try:
        zip_path, excel_path, message = await save_current_zx_page(
            _zx_page,
            company_name
        )

        return (
            to_gradio_file(zip_path),
            to_gradio_file(excel_path),
            str(message)
        )

    except Exception as e:
        return None, None, f"执行信息公开网页面截图失败：{type(e).__name__}: {e}"

async def run_zx_human_batch(company_names_text):
    global _zx_page, _task_start_time, _last_zx_message

    if _task_start_time is None:
        _task_start_time = datetime.now()

    if _zx_page is None:
        return None, None, "请先点击「打开执行信息公开网」。"

    if not company_names_text or not company_names_text.strip():
        return None, None, "请输入公司名称。"

    try:
        zip_path, excel_path, message = await run_zx_human_batch_with_page(
            _zx_page,
            company_names_text.strip(),
            wait_seconds=120,
            screenshot_delay_seconds=3,
        )

        _last_zx_message = str(message)
        return (
            to_gradio_file(zip_path),
            to_gradio_file(excel_path),
            str(message)
        )

    except Exception as e:
        _last_zx_message = f"执行信息公开网半自动批量检索失败：{type(e).__name__}: {e}"
        return None, None, f"执行信息公开网半自动批量检索失败：{type(e).__name__}: {e}"

#国家网信办
async def open_cac_browser():
    global _pw, _cac_context, _cac_page

    if _pw is None:
        _pw = await async_playwright().start()

    _cac_context = await _pw.chromium.launch_persistent_context(
        user_data_dir="cac_profile",
        headless=False,
        viewport={"width": 1440, "height": 1000},
        locale="zh-CN",
        ignore_https_errors=True,
    )

    _cac_page = await _cac_context.new_page()
    await _cac_page.goto(CAC_URL, wait_until="domcontentloaded", timeout=60000)

    return "已打开国家网信办网站，可以开始检索。"


async def search_cac_keywords(company_names_text):
    global _cac_context, _cac_page, _task_start_time, _last_cac_message

    if _task_start_time is None:
        _task_start_time = datetime.now()

    if _cac_page is None or _cac_context is None:
        return None, None, "请先点击「打开国家网信办」。"

    try:
        zip_path, excel_path, message = await run_cac_search_batch_with_page(
            _cac_context,
            _cac_page,
            company_names_text.strip()
        )

        _last_cac_message = str(message)

        return to_gradio_file(zip_path), to_gradio_file(excel_path), str(message)

    except Exception as e:
        _last_cac_message = f"国家网信办检索失败：{type(e).__name__}: {e}"
        return None, None, _last_cac_message

#工信部
async def open_miit_browser():
    global _pw, _miit_context, _miit_page

    if _pw is None:
        _pw = await async_playwright().start()

    _miit_context = await _pw.chromium.launch_persistent_context(
        user_data_dir="miit_profile",
        headless=False,
        viewport={"width": 1440, "height": 1000},
        locale="zh-CN",
        ignore_https_errors=True,
    )

    _miit_page = await _miit_context.new_page()
    await _miit_page.goto(MIIT_URL, wait_until="domcontentloaded", timeout=60000)

    return "已打开工信部统一检索平台，可以开始检索。"


async def search_miit_company(company_names_text):
    global _miit_page, _task_start_time, _last_miit_message

    if _task_start_time is None:
        _task_start_time = datetime.now()

    if _miit_page is None:
        return None, None, "请先点击「打开工信部」。"

    if not company_names_text or not company_names_text.strip():
        return None, None, "请输入公司名称。"

    try:
        zip_path, excel_path, message = await run_miit_search_batch_with_page(
            _miit_page,
            company_names_text.strip()
        )

        _last_miit_message = str(message)

        return (
            to_gradio_file(zip_path),
            to_gradio_file(excel_path),
            str(message)
        )

    except Exception as e:
        _last_miit_message = f"工信部检索失败：{type(e).__name__}: {e}"
        return None, None, _last_miit_message



# =========================
# Gradio 页面
# =========================

with gr.Blocks() as demo:
    gr.Markdown("# IPO网核Agent")

    company_input = gr.Textbox(
        label="公司名称",
        placeholder="请输入公司名称，多个公司用逗号分隔，例如：阿里巴巴集团，抖音集团",
        lines=3,
        interactive=True
    )

    clear_company_btn = gr.Button("清空公司名称")

    clear_company_btn.click(
        fn=lambda: "",
        inputs=[],
        outputs=company_input,
    )


    with gr.Tab("裁判文书网"):
        gr.Markdown("## 第一步：登录裁判文书网")

        open_login_btn = gr.Button("打开裁判文书网登录页面")
        confirm_login_btn = gr.Button("我已登录")
        login_status = gr.Textbox(label="登录状态")

        open_login_btn.click(
            fn=open_login_browser,
            inputs=[],
            outputs=login_status,
        )

        confirm_login_btn.click(
            fn=confirm_login,
            inputs=[],
            outputs=login_status,
        )

        gr.Markdown("## 第二步：检索裁判文书网")

        court_search_btn = gr.Button("开始检索裁判文书网")

        court_zip_file = gr.File(label="裁判文书网截图 ZIP")
        court_excel_file = gr.File(label="裁判文书网批量检索记录 Excel")
        court_status = gr.Textbox(label="裁判文书网运行状态")

        court_search_btn.click(
            fn=search_court_company,
            inputs=company_input,
            outputs=[court_zip_file, court_excel_file, court_status],
        )

    with gr.Tab("执行信息公开网"):
        gr.Markdown("## 执行信息公开网半自动批量检索 / 截图留痕")

        gr.Markdown(
            f"""
            执行信息公开网验证码较严格，当前采用人工验证码 + 自动截图留痕模式。

            半自动批量检索步骤：

            1. 点击「打开执行信息公开网」；
            2. 在弹出的 Chrome 浏览器地址栏手动输入：`{ZX_URL}`；
            3. 回到 Gradio，点击「开始执行网半自动批量检索」；
            4. 程序会自动填入当前公司名称；
            5. 你在网页中手动补充组织机构代码/统一社会信用代码、验证码；
            6. 你点击网页上的红色「查询」按钮；
            7. 程序检测到你点击查询后，会等待 3 秒自动截图，并进入下一家公司。

            如果只是单次人工查询，也可以手动查完后点击「我已完成执行网查询，截图留痕」。
            """
        )

        open_zx_btn = gr.Button("打开执行信息公开网")
        zx_status = gr.Textbox(label="执行信息公开网状态")

        open_zx_btn.click(
            fn=open_zx_browser,
            inputs=[],
            outputs=zx_status,
        )

        zx_zip_file = gr.File(label="执行信息公开网截图 ZIP")
        zx_excel_file = gr.File(label="执行信息公开网截图记录 Excel")
        zx_run_status = gr.Textbox(label="执行信息公开网运行状态")

        zx_batch_btn = gr.Button("开始执行网半自动批量检索")

        zx_batch_btn.click(
            fn=run_zx_human_batch,
            inputs=company_input,
            outputs=[zx_zip_file, zx_excel_file, zx_run_status],
        )

        zx_capture_btn = gr.Button("我已完成执行网查询，截图留痕")

        zx_capture_btn.click(
            fn=capture_zx_page,
            inputs=company_input,
            outputs=[zx_zip_file, zx_excel_file, zx_run_status],
        )

    with gr.Tab("国家网信办"):
        gr.Markdown("## 国家互联网信息办公室检索 / 截图留痕")

        open_cac_btn = gr.Button("打开国家网信办")
        cac_status = gr.Textbox(label="国家网信办状态")

        open_cac_btn.click(
            fn=open_cac_browser,
            inputs=[],
            outputs=cac_status,
        )

        cac_search_btn = gr.Button("开始检索国家网信办")

        cac_zip_file = gr.File(label="国家网信办截图 ZIP")
        cac_excel_file = gr.File(label="国家网信办检索记录 Excel")
        cac_run_status = gr.Textbox(label="国家网信办运行状态")

        cac_search_btn.click(
            fn=search_cac_keywords,
            inputs=company_input,
            outputs=[cac_zip_file, cac_excel_file, cac_run_status],
        )

    with gr.Tab("工信部"):
        gr.Markdown("## 工业和信息化部统一检索平台 / 截图留痕")

        open_miit_btn = gr.Button("打开工信部")
        miit_status = gr.Textbox(label="工信部状态")

        open_miit_btn.click(
            fn=open_miit_browser,
            inputs=[],
            outputs=miit_status,
        )

        miit_search_btn = gr.Button("开始检索工信部")

        miit_zip_file = gr.File(label="工信部截图 ZIP")
        miit_excel_file = gr.File(label="工信部检索记录 Excel")
        miit_run_status = gr.Textbox(label="工信部运行状态")

        miit_search_btn.click(
            fn=search_miit_company,
            inputs=company_input,
            outputs=[miit_zip_file, miit_excel_file, miit_run_status],
        )


demo.launch(share=True)