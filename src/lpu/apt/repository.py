#!/usr/bin/env python3
import datetime
import hashlib
import logging
import os.path
import string
import subprocess

# noinspection PyUnresolvedReferences
import apt.cache  # TODO: Figure out whether we have python3-apt, if not, call apt install using subprocess

import secrets
from lpu.apt.packages import download_packages_with_dependencies
from lpu.common import hash_files, walk_files, Config, load_yaml, load_text_lines, single, get_codename, \
    get_dpkg_architecture
from lpu.gpg import gpg_sign, gpg_show_keys, get_secret_key_ids, gpg_import, gpg_list_keys, gpg_gen_key, \
    gpg_export_secret_key, gpg_export_key

logging.basicConfig(level=logging.DEBUG)

logging.getLogger("urllib3").setLevel(logging.WARNING)


# region dpt/dpkg functions
def generate_packages_file(root_dir, architecture_dir, package_files_dir):
    try:
        subprocess.check_output(f"dpkg-scanpackages --multiversion {os.path.relpath(package_files_dir, root_dir)} | "
                                f"tee {os.path.relpath(architecture_dir, root_dir)}/Packages | "
                                f"gzip -9c > {os.path.relpath(architecture_dir, root_dir)}/Packages.gz",
                                stderr=subprocess.STDOUT,
                                shell=True,
                                cwd=root_dir)
    except subprocess.CalledProcessError as e:
        print(e, e.stdout)


release_hashes = {
    "MD5Sum": hashlib.md5,
    "SHA1": hashlib.sha1,
    "SHA256": hashlib.sha256
}


def generate_release_file(dist_dir, component, architecture, component_dir, **release_meta):
    lines = [
        *[f"{k}: {v}" for k, v in release_meta.items()],
        f"Component: {component}",
        f"Codename: {get_codename()}",
        f'Architectures: {architecture}',
        f'Date: {datetime.datetime.now().astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")}'
    ]
    for name, digest in release_hashes.items():
        lines.append(f"{name}:")
        for hexdigest, size, f in hash_files(walk_files(component_dir), digest):
            f = os.path.relpath(f, dist_dir)
            if f in {"Release", "Release.gpg", "InRelease"}:
                continue
            lines.append(f" {hexdigest} {size:16} {f}")
    with open(os.path.join(dist_dir, "Release"), "w") as fp:
        fp.write("\n".join(lines) + "\n")


# endregion

# region repository signing
def generate_password(length, alphabet=string.ascii_letters + string.digits):
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def sign_release_file(repo_dir, key_id, key_passphrase):
    gpg_sign(key_id, key_passphrase,
             os.path.join(repo_dir, "Release"), os.path.join(repo_dir, "Release.gpg"),
             detached=True)
    gpg_sign(key_id, key_passphrase,
             os.path.join(repo_dir, "Release"), os.path.join(repo_dir, "InRelease"))


# endregion
def generate_key(config):
    # Should never happen, if argpase did its job
    assert not (config.is_present('passphrase_file') and config.is_present('passphrase'))
    if config.is_present('passphrase'):
        passphrase = config['passphrase']
    else:
        if config.is_present('passphrase_file') and os.path.isfile(config['passphrase_file']):
            with open(config['passphrase_file'], "r") as fp:
                passphrase = fp.read().rstrip("\n")
        else:
            passphrase = generate_password(20)
            os.makedirs(os.path.dirname(config['passphrase_file']), exist_ok=True)
            with open(config['passphrase_file'], "w") as fp:
                fp.write(passphrase)

    key_file_exists = config['key_file'] and os.path.isfile(config['key_file'])
    if config.is_present('key_id'):
        key_id_exists = config['key_id'] in get_secret_key_ids(gpg_list_keys(secret=True))
        if not key_id_exists:
            if key_file_exists:
                if config['key_id'] not in get_secret_key_ids(gpg_show_keys(config['key_file'])):
                    raise Exception(f"Key {config['key_id']} was fount neither in the keyring, "
                                    f"nor in the existing file {config['key_file']}.")
                gpg_import(config['key_file'])
            else:
                raise Exception(
                    f"Key {config['key_id']} not found in keyring, and no key file specified to import from.")
        key_id = config['key_id']
    elif key_file_exists:
        try:
            key_id = single(get_secret_key_ids(gpg_show_keys(config['key_file'])))
        except ValueError:
            raise Exception(f"The file {config['key_file']} contains more than one secret key, and no key id is "
                            f"specified")
        gpg_import(config['key_file'])
    else:
        os.makedirs(os.path.dirname(config['key_file']), exist_ok=True)
        key_id = gpg_gen_key(**load_yaml(config['key_metadata']), Passphrase=passphrase)
        gpg_export_secret_key(key_id, config['key_file'])

    return key_id, passphrase


def build_repository(config):
    output_dir: str = config['output_dir']
    dist_dir = os.path.join(output_dir, "dists", get_codename())
    component = config['component']
    component_dir = os.path.join(dist_dir, component)
    architecture = get_dpkg_architecture()["DEB_HOST_ARCH"]
    architecture_dir = os.path.join(component_dir, f"binary-{architecture}")
    package_files_dir = os.path.join(dist_dir, "pool", component, architecture)

    os.makedirs(dist_dir, exist_ok=True)
    os.makedirs(component_dir, exist_ok=True)
    os.makedirs(architecture_dir, exist_ok=True)
    os.makedirs(package_files_dir, exist_ok=True)

    packages = set(p for pa in config['packages'] for p in load_text_lines(pa))
    download_packages_with_dependencies(packages, package_files_dir)

    generate_packages_file(output_dir, architecture_dir, package_files_dir)

    release_metadata = load_yaml(config['release_metadata'])

    generate_release_file(dist_dir, component, architecture, component_dir, **release_metadata)

    key_id, passphrase = generate_key(config)

    sign_release_file(dist_dir, key_id, passphrase)

    gpg_export_key(key_id, os.path.join(output_dir, config['public_key_export']))

