import os
import configparser
import time
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from i18n import localize

# 读取配置文件
def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'usrconfig.conf')
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
    return config

config = load_config()

# 配置优先级：配置文件 > 默认值
def get_config(section, key, default=None, type=str):
    # 检查配置文件
    if config.has_section(section) and config.has_option(section, key):
        value = config.get(section, key)
    else:
        return default
    
    # 类型转换
    if type == int:
        return int(value)
    elif type == float:
        return float(value)
    elif type == bool:
        return value.lower() == "true"
    return value

# 生成配置文件
def generate_config(args=None):
    # 提取参数值
    model_path = args.model_path if args and args.model_path else "ExampleModel"
    device = args.device if args and args.device else "AUTO"
    port = args.port if args and args.port else 8000
    debug = str(args.debug).lower() if args else "false"
    api_key = args.key if args and args.key else ""
    auto_generate_key = str(args.genkey).lower() if args else "false"
    date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    # 构建配置内容
    config_content = """# {config_header_title}
# {config_header_description}
# {config_header_note}
# {config_header_comment}
# {config_header_regenerate}
# {config_header_comment_note}
# ======================
# {config_header_generated}
# ======================

# {config_section_model}
# {config_model_path}
# model_path = {model_path}

# {config_model_device}
# device = {device}

# {config_model_max_tokens}
# max_tokens = 32768

# {config_model_temperature}
# temperature = 0.7

# {config_model_top_p}
# top_p = 0.9

# {config_section_server}
# {config_server_host}
# host = 127.0.0.1

# {config_server_port}
# port = {port}

# {config_server_debug}
# debug = {debug}

# {config_server_log_level}
# log_level = INFO

# {config_server_timeout}
# timeout = 300

# {config_section_api}
# {config_api_key}
# api_key = {api_key}

# {config_api_auto_generate_key}
# auto_generate_key = {auto_generate_key}
""".format(
        config_header_title=localize('config.header.title'),
        config_header_description=localize('config.header.description'),
        config_header_note=localize('config.header.note'),
        config_header_comment=localize('config.header.comment'),
        config_header_regenerate=localize('config.header.regenerate'),
        config_header_comment_note=localize('config.header.comment_note'),
        config_header_generated=localize('config.header.generated', date=date),
        config_section_model=localize('config.section.model'),
        config_model_path=localize('config.model.path'),
        config_model_device=localize('config.model.device'),
        config_model_max_tokens=localize('config.model.max_tokens'),
        config_model_temperature=localize('config.model.temperature'),
        config_model_top_p=localize('config.model.top_p'),
        config_section_server=localize('config.section.server'),
        config_server_host=localize('config.server.host'),
        config_server_port=localize('config.server.port'),
        config_server_debug=localize('config.server.debug'),
        config_server_log_level=localize('config.server.log_level'),
        config_server_timeout=localize('config.server.timeout'),
        config_section_api=localize('config.section.api'),
        config_api_key=localize('config.api.key'),
        config_api_auto_generate_key=localize('config.api.auto_generate_key'),
        model_path=model_path,
        device=device,
        port=port,
        debug=debug,
        api_key=api_key,
        auto_generate_key=auto_generate_key
    )
    
    # 写入配置文件
    config_path = os.path.join(os.path.dirname(__file__), 'usrconfig.conf')
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    return config_path

# 模型配置
MODEL_PATH = get_config('model', 'model_path', "ExampleModel")
DEVICE = get_config('model', 'device', "AUTO")
MAX_TOKENS = get_config('model', 'max_tokens', 32768, int)
TEMPERATURE = get_config('model', 'temperature', 0.7, float)
TOP_P = get_config('model', 'top_p', 0.9, float)

# 服务器配置
HOST = get_config('server', 'host', "127.0.0.1")
PORT = get_config('server', 'port', 8000, int)

# API密钥配置
API_KEY = get_config('api', 'api_key')
AUTO_GENERATE_KEY = get_config('api', 'auto_generate_key', False, bool)

# 新增配置项
DEBUG = get_config('server', 'debug', False, bool)
LOG_LEVEL = get_config('server', 'log_level', 'INFO')
TIMEOUT = get_config('server', 'timeout', 300, int)