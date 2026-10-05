#!/usr/bin/python3

import json
import shutil
import subprocess
import sys
import tempfile
import yaml

from pathlib import Path

GIT_OPTIONS = ["--depth=1", "--recurse-submodules"]

DOTNET_VERSION = "10"
TOOLS_DIR = Path(__file__).parent

PROJECT_DIR = TOOLS_DIR.parent
assert Path(PROJECT_DIR, "com.spacestation14.Launcher.yaml").is_file()

SOURCES_DIR = Path(PROJECT_DIR, "sources")
SOURCES_DIR.mkdir(parents=True, exist_ok=True)

FLATPAK_DOTNET_GENERATOR = Path(PROJECT_DIR, "flatpak-builder-tools/dotnet/flatpak-dotnet-generator.py")
if not FLATPAK_DOTNET_GENERATOR.is_file():
    sys.exit("{} not found. Run `git submodule update --init` first.".format(FLATPAK_DOTNET_GENERATOR))

if shutil.which("flatpak") is None:
    sys.exit("flatpak is not installed, but the dotnet generator needs it.")

def generate_sources(project_file, output_file, freedesktop_version):
    subprocess.run([
        FLATPAK_DOTNET_GENERATOR,
        "--dotnet",
        DOTNET_VERSION,
        "--freedesktop",
        freedesktop_version,
        output_file,
        project_file
    ], check=True)

    with output_file.open("r") as file:
        if not json.load(file):
            sys.exit("{} is empty. Is org.freedesktop.Sdk.Extension.dotnet{}//{} installed?".format(
                output_file.name, DOTNET_VERSION, freedesktop_version
            ))

def main():
    with Path(PROJECT_DIR, "com.spacestation14.Launcher.yaml").open("r") as file:
        manifest_data = yaml.safe_load(file)
        assert manifest_data

        assert manifest_data.get("runtime") == "org.freedesktop.Platform"
        freedesktop_version = manifest_data.get("runtime-version")
        assert freedesktop_version

        modules_list = manifest_data.get("modules", [])

        launcher_module = next(
            (
                module for module in modules_list
                if isinstance(module, dict) and module.get("name") == "space-station-14-launcher"
            ),
            None
        )
        assert launcher_module

        launcher_sources_list = launcher_module.get("sources", [])

        # We will assume the first source entry is the git repo
        launcher_source = next(
            (
                source for source in launcher_sources_list
                if isinstance(source, dict)
            ),
            None
        )
        assert launcher_source

        launcher_source_type = launcher_source.get("type")
        assert launcher_source_type == "git"

        launcher_source_url = launcher_source.get("url")
        assert launcher_source_url

        launcher_source_tag = (
            launcher_source.get("branch")
            or launcher_source.get("tag")
        )
        assert launcher_source_tag

    with tempfile.TemporaryDirectory(prefix=".update-nuget-sources-", dir=PROJECT_DIR) as work_dir:
        checkout_dir = Path(work_dir, "SS14.Launcher")

        try:
            subprocess.run([
                "git",
                "clone",
                launcher_source_url,
                checkout_dir.as_posix(),
                "--branch={}".format(launcher_source_tag),
                *GIT_OPTIONS
            ], check=True)
        except subprocess.CalledProcessError:
            sys.exit("Failed to clone {} at {}".format(launcher_source_url, launcher_source_tag))

        generate_sources(
            Path(checkout_dir, "SS14.Launcher/SS14.Launcher.csproj"),
            Path(SOURCES_DIR, "space-station-14-launcher-nuget-sources.json"),
            freedesktop_version
        )

        generate_sources(
            Path(checkout_dir, "SS14.Loader/SS14.Loader.csproj"),
            Path(SOURCES_DIR, "space-station-14-loader-nuget-sources.json"),
            freedesktop_version
        )

    print("\nUpdated nuget-sources files to {new}".format(
        new=launcher_source_tag
    ))

if __name__ == '__main__':
    main()
