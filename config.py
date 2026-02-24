import os

MODEL_PATH = os.getenv("MODEL_PATH", "C:\\Users\\dev_nvme0n1p1\\AIs\\Qwen3-8B-OpenVINO-Int8")
DEVICE = os.getenv("DEVICE", "AUTO")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 32768))
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
TOP_P = float(os.getenv("TOP_P", 0.9))
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))

# API密钥配置
API_KEY = os.getenv("API_KEY")  # 如果设置，则启用API密钥认证
AUTO_GENERATE_KEY = os.getenv("AUTO_GENERATE_KEY", "false").lower() == "true"  # 是否自动生成密钥