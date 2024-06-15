import argparse

from lpu.apt.common import update_apt_cache, install_dependencies
from lpu.apt.repository import build_repository
from lpu.apt.sources import install_apt_sources
from lpu.common import Config

config_defaults = {
    "output_dir": "repo",
    "public_key_export": "gpg",
    "release_metadata": {
        "Origin": "Offline Repo",
        "Label": "offline Repo",
        "Components": "main",
        "Description": "Offline Repo",
    },
    "component": "main",
    "passphrase_file": "secrets/passphrase",
    "key_file": 'secrets/gpg-secret-key',
    "key_metadata": {
        "Key-Type": "RSA",
        "Key-Length": "4096",
        "Subkey-Type": "ELG-E",
        "Subkey-Length": "1024",
        "Name-Real": "Offline Repo Signing Key",
        # "Name-Comment": "asd",
        # "Name-Email": "asd@asd.com",
        "Expire-Date": "0",
    }
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
                        help="Directory to output the repository files to")
    parser.add_argument("--component",
                        help=f"The repository component (default is '{config_defaults['component']}')")
    parser.add_argument("--key-id",
                        help="The identifier of the gpg secret key that will be used to sign the repository metadata "
                             "files")
    parser.add_argument("--key-file",
                        help="A path to an exported gpg secret key that will be used to sign the repository. "
                             "metadata files If a new key is generated, it will be exported to this file")
    parser.add_argument("--key-metadata",
                        help="Metadata to be used in key generation. " + yaml_help)
    parser.add_argument("--release-metadata",
                        help="Metadata to be used for the repository Release file. " + yaml_help)
    passphrase_group = parser.add_mutually_exclusive_group()
    passphrase_group.add_argument("--passphrase",
                                  help="Passphrase for the signing key")
    passphrase_group.add_argument("--passphrase-file",
                                  help="Path to a file containing the passphrase for the signing key")
    parser.add_argument("--public-key-export",
                        help="Filename use when exporting the signing public key to the repository output directory", )
    parser.add_argument("--no-install-dependencies",
                        action="store_true",
                        help="Do not install packages with dependencies required for the execution of this script")
    parser.add_argument("--repositories",
                        help="Repositories to be added to apt before resolving target packages. " + yaml_help)
    parser.add_argument("packages",
                        help="The packages to include in the repository. Arguments starting with @ will be treated as "
                             "paths to files containing lists of packages",
                        nargs="*")
    config = Config(parser.parse_args(), config_defaults)
    if not config.is_present("packages"):
        print("No packages specified to build a repository for")

    update_apt_cache()

    install_dependencies(config["no_install_dependencies"])

    install_apt_sources(config.get("repositories"))

    build_repository(config)


if __name__ == '__main__':
    main()
