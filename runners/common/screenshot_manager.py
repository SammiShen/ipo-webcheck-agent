from pathlib import Path

from PIL import ImageGrab


def capture_full_screen(path: str | Path) -> Path:
    """
    截取所有显示器的完整屏幕，并保存到指定路径。
    """
    screenshot_path = Path(path)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    image = ImageGrab.grab(all_screens=True)
    image.save(str(screenshot_path))

    return screenshot_path

async def capture_page_screenshot(
    page,
    path: str | Path,
    full_page: bool = True,
) -> Path:
    """
    使用 Playwright 对网页进行截图。

    与 capture_full_screen 不同：
    - capture_full_screen：截取整个电脑屏幕；
    - capture_page_screenshot：截取网页内容。
    """
    screenshot_path = Path(path)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    await page.screenshot(
        path=str(screenshot_path),
        full_page=full_page,
    )

    return screenshot_path