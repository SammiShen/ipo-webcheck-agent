from utils.llm_summary import llm_summary


def generate_report(
    start_time,
    end_time,
    court_message,
    zx_message,
    cac_message="",
    miit_message="",
):
    """
    生成IPO网核Agent运行报告
    """

    duration = end_time - start_time

    report = []

    report.append("=" * 50)
    report.append("IPO网核Agent执行报告")
    report.append("=" * 50)
    report.append("")

    report.append(f"开始时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"结束时间：{end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"总耗时：{duration}")
    report.append("")

    report.append("-" * 50)
    report.append("【裁判文书网】")
    report.append(court_message or "本次未执行裁判文书网任务。")
    report.append("")

    report.append("-" * 50)
    report.append("【执行信息公开网】")
    report.append(zx_message or "本次未执行执行信息公开网任务。")
    report.append("")

    report.append("-" * 50)
    report.append("【国家网信办】")
    report.append(cac_message or "本次未执行国家网信办任务。")
    report.append("")

    report.append("-" * 50)
    report.append("【工信部统一检索平台】")
    report.append(miit_message or "本次未执行工信部任务。")
    report.append("")

    try:
        summary = llm_summary(
            court_message=court_message or "",
            zx_message=zx_message or "",
            cac_message=cac_message or "",
            miit_message=miit_message or "",
        )
    except Exception as e:
        summary = f"AI运行总结生成失败：{type(e).__name__}: {e}"

    report.append("-" * 50)
    report.append("【AI运行总结】")
    report.append(summary)
    report.append("")

    return "\n".join(report)