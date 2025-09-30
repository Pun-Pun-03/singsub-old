import requests
import logging
import json
import sys
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SUB_URL = "https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs.txt"

def parse_trojan(url, tag):
    try:
        parsed = urlparse(url)
        return {
            "type": "trojan",
            "tag": tag,
            "server": parsed.hostname,
            "server_port": parsed.port,
            "password": parsed.username,
            "tls": {"enabled": True, "server_name": parsed.hostname}
        }
    except Exception as e:
        logger.error(f"Parse Trojan failed: {e}")
        return None

def parse_vless(url, tag):
    try:
        parsed = urlparse(url)
        return {
            "type": "vless",
            "tag": tag,
            "server": parsed.hostname,
            "server_port": parsed.port,
            "uuid": parsed.username,
            "tls": {"enabled": True, "server_name": parsed.hostname}
        }
    except Exception as e:
        logger.error(f"Parse VLESS failed: {e}")
        return None

def main():
    try:
        resp = requests.get(SUB_URL, timeout=10)
        resp.raise_for_status()
        lines = [l.strip() for l in resp.text.splitlines() if l.strip()]
    except Exception as e:
        logger.error(f"Failed to fetch sub: {e}")
        sys.exit(1)

    outbounds = []
    for idx, line in enumerate(lines, 1):
        if line.startswith("trojan://"):
            ob = parse_trojan(line, f"Server-{idx}")
        elif line.startswith("vless://"):
            ob = parse_vless(line, f"Server-{idx}")
        else:
            ob = None
        if ob:
            outbounds.append(ob)
        if len(outbounds) >= 14:
            break

    if not outbounds:
        logger.error("No valid vless/trojan servers found")
        sys.exit(1)

    with open("base_config.json", "r", encoding="utf-8") as f:
        base_config = json.load(f)

    new_tags = [o["tag"] for o in outbounds]
    updated_outbounds = []
    for ob in base_config["outbounds"]:
        if ob["type"] == "urltest" and ob["tag"] == "Best-Ping":
            ob["outbounds"] = new_tags
            updated_outbounds.append(ob)
        elif ob["type"] == "selector" and ob["tag"] == "proxy":
            ob["outbounds"] = ["Best-Ping"] + new_tags
            updated_outbounds.append(ob)
        elif ob["type"] in ("direct", "block"):
            updated_outbounds.append(ob)

    base_config["outbounds"] = outbounds + updated_outbounds

    with open("main", "w", encoding="utf-8") as f:
        json.dump(base_config, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(outbounds)} vless/trojan servers into main")

if __name__ == "__main__":
    main()
