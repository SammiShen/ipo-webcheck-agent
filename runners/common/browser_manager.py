async def restore_browser_window(
    page,
    width: int = 1440,
    height: int = 900,
    left: int = 50,
    top: int = 30,
) -> bool:
    """
    通过 Chrome DevTools Protocol 恢复并调整浏览器窗口大小。

    返回：
        True：调整成功；
        False：调整失败，但不会中断网核流程。
    """
    try:
        session = await page.context.new_cdp_session(page)

        window_info = await session.send("Browser.getWindowForTarget")
        window_id = window_info["windowId"]

        await session.send(
            "Browser.setWindowBounds",
            {
                "windowId": window_id,
                "bounds": {
                    "windowState": "normal",
                    "width": width,
                    "height": height,
                    "left": left,
                    "top": top,
                },
            },
        )

        return True

    except Exception as exc:
        print(f"恢复窗口大小失败：{exc}")
        return False