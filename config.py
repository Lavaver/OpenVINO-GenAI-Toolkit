import os

MODEL_PATH = os.getenv("MODEL_PATH", "C:\\Users\\dev_nvme0n1p1\\AIs\\Qwen3-8B-OpenVINO-Int8")
DEVICE = os.getenv("DEVICE", "AUTO")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 32768))
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
TOP_P = float(os.getenv("TOP_P", 0.9))
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))