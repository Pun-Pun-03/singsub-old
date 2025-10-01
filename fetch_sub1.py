import requests
import base64
import json
import re
import logging
from urllib.parse import urlparse, parse_qs, unquote

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUB_LINKS = ["https://raw.githubusercontent.com/V2RAYCONFIGSPOOL/V2RAY_SUB/refs/heads/main/v2ray_configs.txt"
             ]
BASE_CONFIG_PATH = "base_config.json"
OUTPUT_PATH = "main"

SUPPORTED_PROTOCOLS = ["vmess://", "vless://", "trojan://", "ssx://", "hysteria2x://", "hy2x://"]
VALID_TRANSPORT_TYPES = {
    "tcp", "ws", "grpc", "http", "h2", "quic", "tls", "xtls", "kcp", "domain", "reality"
}
PATH_SUPPORTED_TRANSPORTS = {"ws", "http"}
VALID_FLOW_VALUES = {"xtls-rprx-vision", "xtls-rprx-direct", ""}

def fetch_subscription(url):
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        content = res.text.strip()
        return decode_if_base64(content)
    except Exception as e:
        logger.error(f"Error fetching subscription: {e}")
        return ""

def decode_if_base64(text):
    try:
        if text.startswith("data:") and "base64," in text:
            text = text.split("base64,")[1]
        return base64.b64decode(text + "==").decode("utf-8")
    except Exception:
        return text

def extract_links(text):
    links = []
    for proto in SUPPORTED_PROTOCOLS:
        matches = re.findall(rf'({proto}[^\s]+)', text)
        links.extend(matches)
    return links

def create_transport_from_data(data):
    transport = {}
    net = data.get("net")
    if net and net in VALID_TRANSPORT_TYPES and net != "tcp":
        transport["type"] = net
        if net in PATH_SUPPORTED_TRANSPORTS and data.get("path"):
            transport["path"] = data["path"]
        if data.get("host"):
            transport["headers"] = {"Host": data["host"]}
    elif net and net not in VALID_TRANSPORT_TYPES:
        logger.warning(f"Ignoring unknown transport type: {net}")
    return transport

def create_transport_from_params(params):
    transport = {}
    type_ = params.get("type", ["tcp"])[0]
    if type_ in VALID_TRANSPORT_TYPES and type_ != "tcp":
        transport["type"] = type_
        if type_ in PATH_SUPPORTED_TRANSPORTS and params.get("path"):
            transport["path"] = params["path"][0]
        if params.get("host"):
            transport["headers"] = {"Host": params["host"][0]}
    elif type_ and type_ not in VALID_TRANSPORT_TYPES:
        logger.warning(f"Ignoring unknown transport type: {type_}")
    return transport

def convert_vmess(link):
    try:
        raw = link.replace("vmess://", "")
        decoded = base64.b64decode(raw + "==").decode("utf-8")
        data = json.loads(decoded)
        outbound = {
            "type": "vmess",
            "tag": data.get("ps", "vmess"),
            "server": data["add"],
            "server_port": int(data["port"]),
            "uuid": data["id"],
            "security": data.get("scy", "auto"),
            "alter_id": int(data.get("aid", 0)),
        }
        transport = create_transport_from_data(data)
        if transport:
            outbound["transport"] = transport
        return outbound
    except Exception as e:
        logger.warning(f"Error converting vmess: {e}")
        return None

def convert_vless(link):
    try:
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        flow = params.get("flow", [""])[0]
        if flow not in VALID_FLOW_VALUES:
            logger.warning(f"Ignoring unsupported flow: {flow}")
            flow = ""
        outbound = {
            "type": "vless",
            "tag": parsed.fragment or "vless",
            "server": parsed.hostname,
            "server_port": int(parsed.port),
            "uuid": parsed.username,
            "flow": flow
        }
        transport = create_transport_from_params(params)
        if transport:
            outbound["transport"] = transport
        return outbound
    except Exception as e:
        logger.warning(f"Error converting vless: {e}")
        return None

def convert_trojan(link):
    try:
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        outbound = {
            "type": "trojan",
            "tag": parsed.fragment or "trojan",
            "server": parsed.hostname,
            "server_port": int(parsed.port),
            "password": parsed.username
        }
        transport = create_transport_from_params(params)
        if transport:
            outbound["transport"] = transport
        return outbound
    except Exception as e:
        logger.warning(f"Error converting trojan: {e}")
        return None

def convert_ss(link):
    try:
        raw = link.replace("ss://", "")
        if "#" in raw:
            raw, tag = raw.split("#", 1)
        else:
            tag = "shadowsocks"
        if "@" in raw:
            method_pass, server_port = raw.split("@")
            method, password = method_pass.split(":")
            server, port = server_port.split(":")
        else:
            decoded = base64.b64decode(raw + "==").decode("utf-8")
            method, password, server, port = re.split("[:@]", decoded)
        return {
            "type": "shadowsocks",
            "tag": unquote(tag),
            "server": server,
            "server_port": int(port),
            "method": method,
            "password": password
        }
    except Exception as e:
        logger.warning(f"Error converting ss: {e}")
        return None

def convert_hysteria2(link):
    try:
        parsed = urlparse(link)
        params = parse_qs(parsed.query)
        outbound = {
            "type": "hysteria2",
            "tag": parsed.fragment or "hysteria2",
            "server": parsed.hostname,
            "server_port": int(parsed.port),
            "password": parsed.username,
            "up_mbps": 10,
            "down_mbps": 50
        }
        return outbound
    except Exception as e:
        logger.warning(f"Error converting hysteria2: {e}")
        return None

def convert_link(link):
    if link.startswith("vmess://"):
        return convert_vmess(link)
    elif link.startswith("vless://"):
        return convert_vless(link)
    elif link.startswith("trojan://"):
        return convert_trojan(link)
    elif link.startswith("ss://"):
        return convert_ss(link)
    elif link.startswith("hysteria2://") or link.startswith("hy2://"):
        return convert_hysteria2(link)
    else:
        return None

def remove_duplicate_tags(outbounds):
    seen = set()
    unique = []
    for ob in outbounds:
        if ob["tag"] not in seen:
            seen.add(ob["tag"])
            unique.append(ob)
        else:
            logger.warning(f"Skipping duplicate tag: {ob['tag']}")
    return unique

def build_config(outbounds):
    try:
        outbounds = remove_duplicate_tags(outbounds)
        new_tags = [ob["tag"] for ob in outbounds]

        with open(BASE_CONFIG_PATH, "r", encoding="utf-8") as f:
            base_config = json.load(f)

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

        updated_outbounds = outbounds + updated_outbounds
        base_config["outbounds"] = updated_outbounds

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(base_config, f, indent=2, ensure_ascii=False)

        logger.info(f"Config saved to: {OUTPUT_PATH}")
    except Exception as e:
        logger.error(f"Error building final config: {e}")

def main():
    outbounds = []
    for sub_url in SUB_LINKS:
        raw_text = fetch_subscription(sub_url)
        links = extract_links(raw_text)
        for link in links:
            outbound = convert_link(link)
            if outbound:
                outbounds.append(outbound)
    build_config(outbounds)


if __name__ == "__main__":
    main()
