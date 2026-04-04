import platform
import os
import uuid
from windows_toasts import Toast, WindowsToaster, ToastDisplayImage, ToastImagePosition, ToastImage

def sendToast(title, texts):
    if platform.system() != 'Windows':
        return

    # 手动生成兼容的AUMID（替代create_random_aumid）
    custom_aumid = f"OpenVINO.GenAI.Toolkit.{uuid.uuid4().hex[:8]}"
    toaster = WindowsToaster(custom_aumid)
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "favicon.ico")
        logo_image = ToastImage(icon_path)
        app_logo = ToastDisplayImage(
            image=logo_image,
            position=ToastImagePosition.AppLogo
        )
    except Exception as e:
        from i18n import localize
        print(localize('wintoast.image_load_failed', error=e))
        app_logo = None

    tst = Toast()
    tst.text_fields = [title, texts]
    tst.app_logo = app_logo

    toaster.show_toast(tst)

if __name__ == "__main__":
    sendToast("Model Load Success", "Qwen3-4B-int4-ov loaded on AUTO device")