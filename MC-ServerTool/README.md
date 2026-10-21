# MC-ServerTool

A small command-line tool for setting up a Minecraft server on Windows.

## Features

- Download and run the Eclipse Temurin JDK installer (Windows x64)
- Download a stable PaperMC server jar for a given version
- Verify the SHA-256 checksum of every download
- Update the installed PaperMC server jar to the newest build of the same Minecraft version

## Requirements

- Windows (the JDK installer is run with `msiexec`)
- Python 3.10 or higher
- Dependencies: `pip install -r requirements.txt`

## Usage

```
python ServerTool.py jdk <version>
python ServerTool.py paper <version|latest|update> [path]
```

Examples:

```
python ServerTool.py jdk 17
python ServerTool.py paper 26.1.2
python ServerTool.py paper 26.1.2 C:\\path\\to\\save
python ServerTool.py paper update C:\\path\\to\\existing\\paper.jar
```

## Notes

- The JDK installer opens a setup window. The downloaded `.msi` is deleted afterwards.
- The Paper jar is saved in the current directory.
- It downloads software from third-party services (Eclipse Temurin via the Adoptium API, and PaperMC). Those downloads are distributed under their own licenses, and this project is not affiliated with Adoptium, PaperMC, or Mojang.