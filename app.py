import gradio as gr
from pathlib import Path
from playwright.async_api import async_playwright
import subprocess
import asyncio
import urllib.request
import os
from runners.court_runner import run_court_search_batch_with_page
from runners.zx_runner import ZX_URL, save_current_zx_page, run_zx_human_batch_with_page
from datetime import datetime
from utils.report_generator import generate_report
from runners.cac_runner import CAC_URL, run_cac_search_batch_with_page
from runners.miit_runner import MIIT_URL, run_miit_search_batch_with_page

COURT_URL = "https://wenshu.court.gov.cn/"

COURT_PROFILE_DIR = "court_profile"
ZX_PROFILE_DIR = "zx_profile"

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_DEBUG_PROFILE_DIR = r"D:\chrome_debug_profile"
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

_chrome_process = None

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

def is_cdp_ready():
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False

async def wait_for_cdp_ready(timeout_seconds=10):
    for _ in range(timeout_seconds * 2):
        if is_cdp_ready():
            return True
        await asyncio.sleep(0.5)
    return False

async def open_zx_browser():
    global _pw, _zx_browser, _zx_context, _zx_page, _chrome_process

    if _pw is None:
        _pw = await async_playwright().start()

    os.makedirs(CHROME_DEBUG_PROFILE_DIR, exist_ok=True)

    # 如果 9222 端口还没启动，就由 Gradio 自动启动 Chrome
    if not is_cdp_ready():
        try:
            _chrome_process = subprocess.Popen(
                [
                    CHROME_EXE,
                    f"--remote-debugging-port={CDP_PORT}",
                    f"--user-data-dir={CHROME_DEBUG_PROFILE_DIR}",
                    "--new-window",
                    ZX_URL,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return f"启动 Chrome 失败：{type(e).__name__}: {e}"

        ready = await wait_for_cdp_ready(timeout_seconds=10)

        if not ready:
            return (
                "Chrome 已尝试启动，但 9222 调试端口没有成功打开。\n"
                "请检查 Chrome 是否成功弹出，或者 9222 端口是否被占用。"
            )

    try:
        _zx_browser = await _pw.chromium.connect_over_cdp(CDP_URL)
    except Exception as e:
        return f"连接 Chrome 失败：{type(e).__name__}: {e}"

    if not _zx_browser.contexts:
        return "已连接 Chrome，但没有找到浏览器上下文。"

    _zx_context = _zx_browser.contexts[0]

    # 关键：不要随便取最后一个 tab，要找到真正的执行网 tab
    target_page = None

    for p in _zx_context.pages:
        try:
            if "zxgk.court.gov.cn" in p.url:
                target_page = p
                break
        except Exception:
            continue

    # 如果没找到执行网页面，就新开一个
    if target_page is None:
        target_page = await _zx_context.new_page()
        try:
            await target_page.goto(ZX_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

    _zx_page = target_page
    await _zx_page.bring_to_front()

    if "zxgk.court.gov.cn" not in _zx_page.url:
        return (
            "已连接 Chrome，但当前没有成功进入执行信息公开网页面。\n"
            f"当前页面地址：{_zx_page.url}\n"
            f"请在弹出的 Chrome 中手动打开：{ZX_URL}\n"
            "打开后再点击「打开执行信息公开网」重新连接。"
        )

    return (
        "已自动启动并连接 Chrome。\n"
        f"当前连接页面：{_zx_page.url}\n"
        "可以点击「开始执行网半自动批量检索」。"
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

#生成报告
async def generate_agent_report():
    global _task_start_time, _last_court_message, _last_zx_message

    if _task_start_time is None:
        return None, "还没有执行过检索任务，无法生成报告。"

    end_time = datetime.now()

    report_text = generate_report(
        start_time=_task_start_time,
        end_time=end_time,
        court_message=_last_court_message,
        zx_message=_last_zx_message,
        cac_message=_last_cac_message,
        miit_message=_last_miit_message,
    )

    report_dir = Path("output") / "agent_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"IPO网核Agent执行报告_{end_time.strftime('%Y%m%d_%H%M%S')}.txt"
    report_path.write_text(report_text, encoding="utf-8")

    return to_gradio_file(report_path), report_text


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

    with gr.Tab("Agent执行报告"):
        gr.Markdown("## AI辅助生成Agent执行报告")

        report_btn = gr.Button("生成Agent执行报告")

        report_file = gr.File(label="Agent执行报告 TXT")
        report_preview = gr.Textbox(label="报告预览", lines=18)

        report_btn.click(
            fn=generate_agent_report,
            inputs=[],
            outputs=[report_file, report_preview],
        )

demo.launch(share=True)