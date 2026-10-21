import requests
import subprocess
import sys
import os
import hashlib
import re
from pathlib import Path

BASENAME = os.path.basename(__file__)
USAGE = (
    "Usage:\n"
    f"  python {BASENAME} jdk <version>\n"
    f"  python {BASENAME} paper <version|latest|update> [path]\n"
    "\n"
    "Examples:\n"
    f"  python {BASENAME} jdk 17\n"
    f"  python {BASENAME} paper 26.1.2\n"
    f"  python {BASENAME} paper latest\n"
    f"  python {BASENAME} paper 26.1.2 C:\\path\\to\\save\n"
    f"  python {BASENAME} paper update C:\\path\\to\\existing\\paper.jar"
)

if len(sys.argv) < 3 or len(sys.argv) > 4 or sys.argv[1] not in ("jdk", "paper"):
    print(USAGE)
    sys.exit(1)

HEADERS = {"User-Agent": "MC-ServerTool/1.0.0"}
PAPER_URL = "https://fill.papermc.io/v3"
ASSETS_URL = "https://api.adoptium.net/v3/assets/latest/{version}/hotspot"
MC_URL = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
TIMEOUT = 30 # seconds

PATTERN = re.compile(r"^paper-([\d.]+)-(\d+)\.jar$")

MSI_OK = (0, 3010) # 0 = success, 3010 = success but a reboot is required

def get_file_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def get_MC_latest_version() -> str:
    with requests.get(
    MC_URL, headers=HEADERS, timeout=TIMEOUT
    ) as response:
        if response.status_code != 200:
            print(f"Failed to fetch Minecraft version (HTTP status: {response.status_code}).")
            sys.exit(1)
    data = response.json()
    return data["latest"]["release"]
    
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

def get_installed_paper_version():
    if len(sys.argv) < 4:
        print("A path is required for update mode.")
        sys.exit(1)

    path = Path(sys.argv[3])
    if path.is_file():
        candidates = [path]
    elif path.is_dir():
        candidates = [p for p in path.iterdir() if p.is_file()]
    else:
        print(f"The specified path '{path}' does not exist.")
        sys.exit(1)

    results = []
    for file_path in candidates:
        match = PATTERN.match(file_path.name)
        if match:
            results.append({
                "file_path": str(file_path),
                "version": match.group(1),
                "build": int(match.group(2)),
            })

    if not results:
        return None
    return max(
        results,
        key=lambda r: (tuple(map(int, r["version"].split("."))), r["build"]),
    )
    

def download_paper(build: dict, build_number: int | None, download_key: str = "server:default"):
    p = Path(sys.argv[3]) if len(sys.argv) == 4 else None
    if p and p.is_file():
        p = p.parent
    path = str(p) if p else None
    if path:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            print(f"Cannot use path '{path}': {e}")
            sys.exit(1)
    download_info = build["downloads"][download_key]
    latest_build_number = build["id"]
    if build_number is not None:
        if int(build_number) >= latest_build_number:
            print(f"The latest build is already installed.")
            sys.exit(1)
        elif int(build_number) < latest_build_number:
            print(f"Updating from build {build_number} to {latest_build_number}.")
    url = download_info["url"]
    if path:
        file_name = os.path.basename(download_info["name"])
        output_path = os.path.join(path, file_name)
    else:
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
    abs_path = os.path.abspath(output_path)
    print(f"Paper has been downloaded as {abs_path}")

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
        installer = assets[0].get("binary", {}).get("installer")
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

            abs_path = os.path.abspath(output_path)
            result = subprocess.run(["msiexec", "/i", abs_path], check=False)
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
        installed = None
        build_number = None

        if sys.argv[2] == "latest":
            version = get_MC_latest_version()
            print(f"Latest Minecraft release: {version}")
        elif sys.argv[2] == "update":
            installed = get_installed_paper_version()
            if installed is None:
                print("Could not determine the installed Paper version from the provided path.")
                sys.exit(1)
            version = installed["version"]
            build_number = installed["build"]
        else:
            version = sys.argv[2]

        build = get_latest_version(version)
        download_paper(build, build_number)

        if installed is not None:
            os.remove(installed["file_path"])

if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        print(f"Network error: {e}")
        sys.exit(1)