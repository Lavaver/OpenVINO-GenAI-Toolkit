import os
import json
import locale
from typing import Dict, Optional

class I18nManager:
    def __init__(self, default_locale: str = "en"):
        self.default_locale = default_locale
        self.locales_dir = os.path.join(os.path.dirname(__file__), "locales")
        self.translations: Dict[str, Dict[str, str]] = {}
        # 先创建 locales 目录并加载翻译文件
        self._load_translations()
        # 然后检测系统语言
        self.current_locale = self._detect_system_locale()
    
    def _detect_system_locale(self) -> str:
        """检测系统语言"""
        try:
            # 获取系统语言
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                # 首先尝试使用完整的语言代码（如 zh_CN）
                if system_locale in self.translations:
                    return system_locale
                # 然后尝试使用语言代码的前缀（如 zh）
                lang_code = system_locale.split('_')[0]
                if lang_code in self.translations:
                    return lang_code
        except Exception:
            pass
        return self.default_locale
    
    def _load_translations(self):
        """加载所有语言的翻译文件"""
        if not os.path.exists(self.locales_dir):
            os.makedirs(self.locales_dir)
        
        # 加载默认语言文件
        self._load_locale(self.default_locale)
        
        # 加载其他语言文件
        for filename in os.listdir(self.locales_dir):
            if filename.endswith(".json"):
                locale = filename[:-5]  # 移除 .json 后缀
                if locale != self.default_locale:
                    self._load_locale(locale)
    
    def _load_locale(self, locale: str):
        """加载指定语言的翻译文件"""
        file_path = os.path.join(self.locales_dir, f"{locale}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.translations[locale] = json.load(f)
            except Exception as e:
                print(f"Error loading translation file for {locale}: {e}")
                self.translations[locale] = {}
        else:
            # 如果文件不存在，创建一个空的翻译文件
            self.translations[locale] = {}
            self._save_locale(locale)
    
    def _save_locale(self, locale: str):
        """保存指定语言的翻译文件"""
        file_path = os.path.join(self.locales_dir, f"{locale}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.translations[locale], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving translation file for {locale}: {e}")
    
    def set_locale(self, locale: str):
        """设置当前语言"""
        if locale not in self.translations:
            self._load_locale(locale)
        self.current_locale = locale
    
    def get(self, key: str, **kwargs) -> str:
        """获取翻译文本"""
        # 首先在当前语言中查找
        if self.current_locale in self.translations and key in self.translations[self.current_locale]:
            text = self.translations[self.current_locale][key]
        # 如果当前语言中没有，在默认语言中查找
        elif self.default_locale in self.translations and key in self.translations[self.default_locale]:
            text = self.translations[self.default_locale][key]
        # 如果都没有，返回键本身
        else:
            text = key
        
        # 替换占位符
        if kwargs:
            text = text.format(**kwargs)
        
        return text
    
    def add_translation(self, key: str, translation: str, locale: Optional[str] = None):
        """添加翻译"""
        if locale is None:
            locale = self.current_locale
        
        if locale not in self.translations:
            self.translations[locale] = {}
        
        self.translations[locale][key] = translation
        self._save_locale(locale)

# 创建全局 i18n 实例
i18n = I18nManager()

# 便捷函数
def _(key: str, **kwargs) -> str:
    return i18n.get(key, **kwargs)