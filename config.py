import os

from dotenv import load_dotenv

load_dotenv()

QWEN_API_KEY = os.getenv("QWEN_API_KEY")

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

MODEL = "qwen-plus"