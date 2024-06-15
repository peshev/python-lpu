import hashlib
import logging
import os

from lpu.apt.common import cache
from lpu.common import file_digest


def get_latest_version(package):
    return sorted(cache[package].versions)[-1]


def get_package_with_dependencies(package):
    result = set()

    def _normalize_name(p):
        return p[:-len(":any")] if p.endswith(":any") else p

    def _recurse_dependencies(p):
        p = _normalize_name(p)
        if p in result:
            return
        result.add(p)
        for dependency in get_latest_version(p).dependencies:
            if hasattr(dependency, 'or_dependencies') and dependency.or_dependencies:
                ods = [od for od in dependency.or_dependencies if _normalize_name(od.name) in cache]
                if not ods:
                    raise Exception(f"Dependency not found in cache: {dependency}")
                for od in ods:
                    _recurse_dependencies(od.name)
            elif len(dependency) == 1:
                _recurse_dependencies(dependency[0].name)
            else:
                raise Exception(f"Can't process dependency: {dependency}")

    _recurse_dependencies(package)
    return result


def download_package(package, dest_dir):
    version = get_latest_version(package)
    filename = os.path.basename(version.filename)
    filepath = os.path.join(dest_dir, filename)
    if os.path.isfile(filepath):
        with open(filepath, "rb") as fp:
            # noinspection PyTypeChecker
            sha256hash = file_digest(fp, hashlib.sha256).hexdigest()
        if sha256hash == version.sha256:
            logging.info(f"Package {filename} already exists, skipping.")
            return
    version.fetch_binary(dest_dir)


def download_packages_with_dependencies(packages, dest_dir):
    packages = [pd for p in packages for pd in get_package_with_dependencies(p)]
    for package in set(packages):
        download_package(package, dest_dir)

