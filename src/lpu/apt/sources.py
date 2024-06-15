import logging
import os
import re

import requests

from lpu.apt.common import update_apt_cache
from lpu.common import load_yaml, get_codename, get_dpkg_architecture
from lpu.gpg import get_secret_key_ids, gpg_show_keys, gpg_dearmor

apt_base_dir = "/etc/apt"
apt_sources_list_file = f"{apt_base_dir}/sources.list"
apt_gpg_key_base_dir = f"{apt_base_dir}/trusted.gpg.d"
apt_sources_list_dir = f"{apt_base_dir}/sources.list.d"


def install_apt_key(key_url, name):
    os.makedirs(apt_gpg_key_base_dir, exist_ok=True)
    key_filename = os.path.join(apt_gpg_key_base_dir, f"{name}.gpg")

    key_content = requests.get(key_url).content
    upstream_secret_keys = set(get_secret_key_ids(gpg_show_keys(content=key_content)))
    if os.path.isfile(key_filename):
        file_secret_keys = set(get_secret_key_ids(gpg_show_keys(filename=key_filename)))
        if not upstream_secret_keys - file_secret_keys:
            logging.info(f"Keys from {key_url} already present in {key_filename}. Skipping.")
            return

    gpg_dearmor(key_content, key_filename)


source_entry_regex = re.compile(
    r"^"
    r"(?P<type>deb(-src)?)\s+"
    r"(\[\s*(?P<options>[^]]+)\s*]\s+)?"
    r"(?P<uri>\S+)\s+"
    r"(?P<suite>\S+)\s+"
    r"(?P<components>.+?)"
    r"(\s*#.*)?$")

sources_list_filename_regex = re.compile(r"^[A-Za-z0-9_.-]+\.list$")


def parse_source_entry(line):
    match = source_entry_regex.match(line)
    if not match:
        return None
    result = match.groupdict()
    if result["options"] is not None:
        result["options"] = {
            k: v.split(",") if "," in v else v
            for k, v in
            (
                o.split("=", maxsplit=2)
                for o in
                result["options"].split()
            )
        }
    result["components"] = result["components"].split()
    return result


def format_source_entry(entry):
    if entry.get("options"):
        options = "[" + " ".join(
            f"{k}={','.join(v) if isinstance(v, (list, tuple)) else v}" for k, v in entry['options'].items()) + "] "
    else:
        options = ""
    return f"{entry['type']} {options}{entry['uri']} {entry['suite']} {' '.join(entry['components'])}"


def read_sources_file(filename):
    with open(filename, "r") as fp:
        return list(filter(None, map(parse_source_entry, fp)))


def source_match(new_source, existing_source):
    for k, v in new_source.items():
        if k not in {'uri', 'type', 'options', 'components', 'suite'}:
            continue
        if existing_source.get(k) is None:
            return False
        ev = existing_source[k]
        if k == "components":
            if set(v) - set(ev):
                return False
        if k == "options":
            for ok, ov in v.items():
                if ok not in ev:
                    return False
                if set(ov) - set(ev[ok]):
                    return False
    return True


def install_apt_source(name, source):
    for f in [
                 os.path.join(apt_sources_list_dir, f)
                 for f in
                 os.listdir(apt_sources_list_dir)
                 if sources_list_filename_regex.match(f)
             ] + [apt_sources_list_file]:
        if os.path.isfile(f):
            for s in read_sources_file(f):
                if source_match(source, s):
                    logging.info(f"Source '{format_source_entry(s)}' found in file {f}. Skipping.")
                    return False

    os.makedirs(apt_sources_list_dir, exist_ok=True)

    with open(os.path.join(apt_sources_list_dir, f"{name}.list"), "a") as fp:
        fp.write(f"\n{format_source_entry(source)}\n")

    return True


def install_apt_sources(sources):
    repositories = load_yaml(sources)
    if repositories:
        changed = False
        for n, r in repositories.items():
            r.setdefault("type", "deb")
            r.setdefault("options", {"arch": get_dpkg_architecture()["DEB_HOST_ARCH"]})
            r.setdefault("suite", get_codename())
            r.setdefault("components", ["main"])

            if r.get('key_url'):
                install_apt_key(r['key_url'], n)

            changed = install_apt_source(n, r) or changed
        if changed:
            update_apt_cache()
