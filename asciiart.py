# 导入需要的模块
import sys
import json
import os
from rich.console import Console
from rich.text import Text
from i18n import localize

# 初始化Console对象
console = Console()

def get_version():
    """从 build.json 文件读取版本信息"""
    build_json_path = os.path.join(os.path.dirname(__file__), "build.json")
    try:
        with open(build_json_path, 'r', encoding='utf-8') as f:
            build_info = json.load(f)
            return build_info.get('version', '0.2.0-20260225')
    except Exception:
        return localize('version.unavailable')

def print_ascii_art():
    """
    Welcome to OpenVINO GenAI Toolkit!
    """

    # 原始ASCII艺术字符串（仅包含$和空格）
    ascii_art_raw = """
        $$$$$$$$$$$                                    $$$$     $$$ $$$ $$$$$$    $$$$   $$$$$$$$$$$$
     $$$$$$$$$$$$$$                                    $$$     $$$$ $$$ $$$$$$    $$$$  $$$$$$$$$$$$$$   
    $$$oooooo  $$$$$ $$$$$$$$$     $$$$$$$   $$$$$$$$  $$$$    $$$  $$$ $$$$$$$   $$$$ $$$$$ oooo $$$$$  
    $$$ ooooooo  $$$ $$$$$$$$$$$ $$$$$$$$$$  $$$$$$$$$$ $$$$  $$$$  $$$ $$$ $$$$  $$$$ $$$$ ooooooo $$$$ 
    $$$ ooooooo  $$$ $$$$  $$$$$ $$$$$$$$$$$ $$$$   $$$ $$$$ $$$$   $$$ $$$  $$$$$$$$$ $$$  ooooooo $$$$ 
    $$$$ oooooo $$$$ $$$     $$$ $$$$$$$$$$$ $$$    $$$  $$$$$$$    $$$ $$$   $$$$$$$$ $$$$ ooooooo $$$  
    $$$$$$    $$$$$  $$$$   $$$$ $$$$$  $$$$ $$$    $$$   $$$$$$    $$$ $$$    $$$$$$$  $$$$$    $$$$$$  
      $$$$$$$$$$$$   $$$$$$$$$$$  $$$$$$$$$  $$$    $$$   $$$$$     $$$ $$$      $$$$$   $$$$$$$$$$$$$   
         $$$$$$      $$$$$$$$$     $$$$$$    $$$    $$$    $$$      $$$ $$$       $$$$      $$$$$$$      
                     $$$                                                                                
                     $$$                                                                                
    """

    # 创建Text对象用于构建带样式的文本
    colored_art = Text()

    # 遍历每个字符，给o添加样式，空格保持默认
    for char in ascii_art_raw:
        if char == 'o':
            colored_art.append(char, style="magenta")
        else:
            # 空格/换行保持默认样式
            colored_art.append(char)

    # 输出带$符号的ASCII艺术
    console.print(colored_art)

    version = get_version()
    console.print(localize('asciiart.welcome', toolkit=f"[magenta]{localize('asciiart.title')}[/magenta]", version=f"[bright_cyan]{version}[/bright_cyan]", python_version=f"[bright_cyan]{sys.version}[/bright_cyan]"))