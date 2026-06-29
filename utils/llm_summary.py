from openai import OpenAI

from config import BASE_URL, MODEL, QWEN_API_KEY

client = OpenAI(
    api_key=QWEN_API_KEY,
    base_url=BASE_URL,
)


def llm_summary(court_message="", zx_message="", cac_message="", miit_message=""):
    """
    调用Qwen生成Agent运行总结
    """

    prompt = f"""
你是IPO网核Agent的运行报告助手。

下面是本次Agent运行日志。

【裁判文书网】
{court_message}

【执行信息公开网】
{zx_message}

【国家网信办】
{cac_message}

【工信部统一检索平台】
{miit_message}

请根据运行日志生成一段运行总结。

要求：

1. 不发表法律意见；
2. 不分析企业风险；
3. 不推测任何事实；
4. 不编造不存在的数据；
5. 只总结：
   - 本次运行是否顺利；
   - 哪些网站完成；
   - 哪些网站失败（如有）；
   - 是否建议重新执行。

语言专业、客观、简洁，不超过120字。
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "你是一名严谨的Agent运行报告助手。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"AI运行总结生成失败：{type(e).__name__}: {e}"