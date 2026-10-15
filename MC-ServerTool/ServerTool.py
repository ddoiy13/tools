import requests
import subprocess
import sys
import os
import hashlib

BASENAME = os.path.basename(__file__)
USAGE = (
    "Usage:\n"
    f"  python {BASENAME} <jdk|paper> <version>\n"
    "\n"
    "Examples:\n"
    f"  python {BASENAME} jdk 17\n"
    f"  python {BASENAME} paper 26.1.2"
)

if len(sys.argv) < 3 or sys.argv[1] not in ("jdk", "paper"):
    print(USAGE)
    sys.exit(1)

HEADERS = {"User-Agent": "MC-ServerTool/1.0.0"}
PAPER_URL = "https://fill.papermc.io/v3"
ASSETS_URL = "https://api.adoptium.net/v3/assets/latest/{version}/hotspot"
TIMEOUT = 30 # seconds

MSI_OK = (0, 3010) # 0 = success, 3010 = success but a reboot is required

def get_file_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def get_latest_version(version: str) -> dict:
    with requests.get(
        f"{PAPER_URL}/projects/paper/versions/{version}/builds",
        headers=HEADERS,
        timeout=TIMEOUT
    ) as response:
        if response.status_code != 200:
            print(f"Failed to fetch Paper builds (HTTP status: {response.status_code}).")
            sys.exit(1)
    data = response.json()
    for build in data:
        if build.get("channel") == "STABLE":
            return build
    print(f"No stable Paper build found for version {version}.")
    sys.exit(1)

def download_paper(build: dict, download_key: str = "server:default"):
    download_info = build["downloads"][download_key]
    url = download_info["url"]
    output_path = os.path.basename(download_info["name"])
    sha256 = download_info["checksums"]["sha256"].lower()

    print("Downloading Paper...")
    with requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT) as response:
        if response.status_code != 200:
            print(f"Failed to download Paper (HTTP status: {response.status_code}).")
            sys.exit(1)
        try:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)              
                        
        except BaseException:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise
    if get_file_sha256(output_path) != sha256:
        print("Checksum mismatch! The downloaded file is deleted.")
        os.remove(output_path)
        sys.exit(1)
    print(f"Paper has been downloaded as {output_path}")

def main():
    if sys.argv[1] == "jdk":
        version = sys.argv[2]
        output_path = f"jdk-{version}.msi"

        with requests.get(
            ASSETS_URL.format(version=version),
            params={"architecture": "x64", "image_type": "jdk", "os": "windows"},
            headers=HEADERS,
            timeout=TIMEOUT,
        ) as response:
            if response.status_code != 200:
                print(f"Failed to fetch JDK info (HTTP status: {response.status_code}).")
                sys.exit(1)
            assets = response.json()
        if not assets:
            print(f"No JDK {version} installer found.")
            sys.exit(1)
        installer = assets[0]["binary"]["installer"]
        if installer is None:
            print(f"No JDK {version} installer (.msi) found.")
            sys.exit(1)

        try:
            print("Downloading JDK installer...")
            with requests.get(
                installer["link"], headers=HEADERS, stream=True, timeout=TIMEOUT
            ) as response:
                if response.status_code != 200:
                    print(f"Failed to download JDK (HTTP status: {response.status_code}).")
                    sys.exit(1)
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            if get_file_sha256(output_path) != installer["checksum"].lower():
                print("Checksum mismatch! The downloaded file is deleted.")
                sys.exit(1)

            result = subprocess.run(["msiexec", "/i", output_path], check=False)
            if result.returncode not in MSI_OK:
                print(f"The JDK installer did not complete (exit code: {result.returncode}).")
                sys.exit(1)
            elif result.returncode == 3010:
                print("The JDK installer completed successfully, but a reboot is required.")
            print("JDK installer finished.")
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    elif sys.argv[1] == "paper":
        version = sys.argv[2]
        build = get_latest_version(version)

        download_paper(build)

if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        print(f"Network error: {e}")
        sys.exit(1)