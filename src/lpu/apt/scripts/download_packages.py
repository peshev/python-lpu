import argparse
import os

from lpu.apt.common import update_apt_cache, install_dependencies
from lpu.apt.packages import download_packages_with_dependencies
from lpu.apt.sources import install_apt_sources
from lpu.common import Config, load_text_lines

config_defaults = {
    "output_dir": ".",
}
yaml_help = (
    "If the argument is -, it is read from stdin, if the argument starts with @, it is treated as path to a "
    "file, otherwise it is treated as a YAML/JSON string,"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config",
                        help="Configuration for this script. " + yaml_help)
    parser.add_argument("-o", "--output-dir",
                        help="Directory to output the downloaded packages to")
    parser.add_argument("--no-install-dependencies",
                        action="store_true",
                        help="Do not install packages with dependencies required for the execution of this script")
    parser.add_argument("--repositories",
                        help="Repositories to be added to apt before resolving target packages. " + yaml_help)
    parser.add_argument("packages",
                        help="The packages to download. Arguments starting with @ will be treated as "
                             "paths to files containing lists of packages",
                        nargs="*")
    config = Config(parser.parse_args(), config_defaults)
    if not config.is_present("packages"):
        print("No packages specified to download")

    update_apt_cache()

    install_dependencies(config["no_install_dependencies"])

    install_apt_sources(config.get("repositories"))

    output_dir = config["output_dir"]
    os.makedirs(output_dir, exist_ok=True)
    packages = set(p for pa in config['packages'] for p in load_text_lines(pa))
    download_packages_with_dependencies(packages, output_dir)


if __name__ == '__main__':
    main()
