import requests
import logging
import socket
import base64
import json
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def extract_ss_details(ss_url):
    """Extract cipher, password, server, and port from ss:// URL."""
    try:
        ss_part = ss_url.split("#")[0].replace("ss://", "")
        creds, server_info = ss_part.split("@")
        decoded_creds = base64.b64decode(creds + "==").decode("utf-8")
        cipher, password = decoded_creds.split(":")
        server, port = server_info.split(":")
        port = port.split("/")[0]
        return cipher, password, server, int(port)
    except Exception as e:
        logger.error(f"Error parsing SS URL {ss_url}: {str(e)}")
        return None

def resolve_ips(hostname):
    """Resolve hostname to a list of unique IP addresses."""
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ips = list(set(info[4][0] for info in addr_info))
        return ips
    except Exception as e:
        logger.warning(f"Failed to resolve {hostname}: {str(e)}. Using hostname instead.")
        return [hostname]

def fetch_config(url, server_number):
    """Fetch config and extract details."""
    https_url = url.replace("ssconf://", "https://")
    try:
        response = requests.get(https_url, timeout=10)
        response.raise_for_status()
        content = response.text.strip()
        if content.startswith("ss://"):
            content = f"{content}#Server-{server_number}"
            details = extract_ss_details(content)
            if details:
                cipher, password, hostname, port = details
                return {
                    "name": f"Server-{server_number}",
                    "cipher": cipher,
                    "password": password,
                    "hostname": hostname,
                    "port": port
                }
        return None
    except Exception as e:
        logger.error(f"Error fetching {https_url}: {str(e)}")
        return None

def main():
    urls = [
        "ssconf://ainita.s3.eu-north-1.amazonaws.com/AinitaServer-1.csv",
        "ssconf://ainita.s3.eu-north-1.amazonaws.com/AinitaServer-2.csv",
        "ssconf://ainita.s3.eu-north-1.amazonaws.com/AinitaServer-3.csv",
        "ssconf://ainita.s3.eu-north-1.amazonaws.com/AinitaServer-4.csv"
    ]

    configs = []
    for index, url in enumerate(urls, 1):
        cfg = fetch_config(url, index)
        if cfg:
            configs.append(cfg)

    if not configs:
        logger.error("No configs fetched!")
        sys.exit(1)

    # Resolve IPs
    ip_to_config = {}
    for cfg in configs:
        for ip in resolve_ips(cfg["hostname"]):
            ip_to_config[ip] = {
                "cipher": cfg["cipher"],
                "password": cfg["password"],
                "port": cfg["port"]
            }

    # Build outbounds
    outbounds = []
    for idx, (ip, details) in enumerate(ip_to_config.items(), 1):
        outbounds.append({
            "type": "shadowsocks",
            "tag": f"Server-{idx}",
            "server": ip,
            "server_port": details["port"],
            "method": details["cipher"],
            "password": details["password"]
        })

    if not outbounds:
        logger.error("No IPs resolved, fallback to hostnames")
        for idx, cfg in enumerate(configs, 1):
            outbounds.append({
                "type": "shadowsocks",
                "tag": f"Server-{idx}",
                "server": cfg["hostname"],
                "server_port": cfg["port"],
                "method": cfg["cipher"],
                "password": cfg["password"]
            })

    # Add selector
    outbounds.append({
        "type": "selector",
        "tag": "Auto",
        "outbounds": [o["tag"] for o in outbounds if o["type"] == "shadowsocks"]
    })

    # Load base config
    try:
        with open("base_config.json", "r", encoding="utf-8") as f:
            base_config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load base_config.json: {str(e)}")
        sys.exit(1)

    # Replace outbounds
    base_config["outbounds"] = outbounds

    # Save final config
    try:
        with open("main", "w", encoding="utf-8") as f:
            json.dump(base_config, f, indent=2, ensure_ascii=False)
        logger.info(f"Final config written with {len(outbounds)-1} servers + selector")
    except Exception as e:
        logger.error(f"Error writing final config: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
