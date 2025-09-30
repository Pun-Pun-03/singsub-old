import requests
import logging
import json
import sys

# اگر کتابخانه نصب نبود، خطا می‌دهیم تا کاربر نصب کند
try:
from singbox_converter import Converter  # نام پکیج طبق مستندات: PySingBoxConverter
except Exception as e:
    print("PySingBoxConverter نصب نشده. لطفاً اجرا کنید: pip install PySingBoxConverter")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SUB_URL = "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs.txt"
BASE_FILE = "base_config.json"
OUT_FILE = "Project_Singbox.json"
MAX_SERVERS = 14

def fetch_subscription(url: str) -> str:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.error(f"Failed to fetch subscription: {e}")
        sys.exit(1)

def convert_to_singbox_outbounds(sub_text: str):
    """
    از PySingBoxConverter برای تبدیل همه‌ی لینک‌ها به ساختار sing-box استفاده می‌کنیم.
    خروجی شامل اوتباند‌هاست؛ آن‌ها را فیلتر می‌کنیم تا فقط vless/trojan باقی بمانند.
    """
    try:
        conv = Converter()
        # بیشتر کانورترها یک متد برای تبدیل کل متن ساب دارند و خروجی JSON ساختار sing-box می‌دهند.
        # اینجا فرض می‌کنیم خروجی شامل کلید 'outbounds' باشد.
        converted = conv.convert(sub_text, target="singbox")  # خروجی dict
        outbounds = converted.get("outbounds", [])
        return outbounds
    except Exception as e:
        logger.error(f"Converter failed: {e}")
        sys.exit(1)

def filter_vless_trojan(outbounds):
    """
    فقط vless و trojan را نگه می‌داریم، تا سقف MAX_SERVERS.
    اگر تگ ندارد، با Server-1…Server-N پر می‌کنیم.
    """
    filtered = []
    n = 1
    for ob in outbounds:
        t = ob.get("type", "").lower()
        if t not in ("vless", "trojan"):
            continue
        # اطمینان از وجود فیلدهای ضروری
        server = ob.get("server")
        port = ob.get("server_port")
        if not server or not port:
            continue
        # برچسب
        tag = ob.get("tag")
        if not tag:
            tag = f"Server-{n}"
            ob["tag"] = tag
        # پاکسازی‌های سبک: حذف فیلدهای ناشناخته یا ناسازگار ضروری نیست مگر مشکل ایجاد کند.
        filtered.append(ob)
        n += 1
        if len(filtered) >= MAX_SERVERS:
            break
    return filtered

def update_base_outbounds(base_config, new_servers):
    """
    - outbounds جدید را در ابتدای لیست قرار می‌دهیم.
    - urltest با تگ Best-Ping فقط لیست تگ‌های سرورهای جدید را داشته باشد.
    - selector با تگ proxy با Best-Ping شروع شود و سپس تگ‌های جدید.
    - direct و block حفظ می‌شوند.
    - سایر اوتباندهای قدیمی (سرورهای قبلی) حذف می‌شوند.
    """
    new_tags = [o["tag"] for o in new_servers]
    updated = []

    for ob in base_config.get("outbounds", []):
        typ = ob.get("type")
        tag = ob.get("tag")
        if typ == "urltest" and tag == "Best-Ping":
            ob["outbounds"] = new_tags
            updated.append(ob)
        elif typ == "selector" and tag == "proxy":
            ob["outbounds"] = ["Best-Ping"] + new_tags
            updated.append(ob)
        elif typ in ("direct", "block"):
            updated.append(ob)
        else:
            # حذف سرورهای قدیمی
            continue

    base_config["outbounds"] = new_servers + updated
    return base_config

def main():
    sub_text = fetch_subscription(SUB_URL)
    converted_outbounds = convert_to_singbox_outbounds(sub_text)
    servers = filter_vless_trojan(converted_outbounds)

    if not servers:
        logger.error("No valid vless/trojan servers after conversion")
        sys.exit(1)

    # بارگذاری base و جایگزینی فقط outbounds با قواعد خواسته‌شده
    try:
        with open(BASE_FILE, "r", encoding="utf-8") as f:
            base_config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load base_config.json: {e}")
        sys.exit(1)

    final_config = update_base_outbounds(base_config, servers)

    try:
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final_config, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(servers)} servers into {OUT_FILE}")
    except Exception as e:
        logger.error(f"Failed to write {OUT_FILE}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
