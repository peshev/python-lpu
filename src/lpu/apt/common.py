import logging
import subprocess

import apt.cache

cache = apt.cache.Cache()


def update_apt_cache():
    subprocess.check_output(["apt", "update"], stderr=subprocess.STDOUT)
    cache.open()


package_dependencies = {
    "dpkg-dev",
    "dpkg-dev",
    "lsb-release",
    "gpg",
}


def install_dependencies(check_only):
    missing_dependencies = set()
    needs_commit = False
    for pd_name in package_dependencies:
        pd = cache.get(pd_name)
        if pd is None:
            logging.error(f"Package {pd_name} not found in APT cache")
        else:
            if not pd.is_installed:
                if check_only:
                    missing_dependencies.add(pd)
                else:
                    needs_commit = True
                    logging.info(f"Installing package {pd_name} ...")
                    pd.mark_install()
    if missing_dependencies:
        raise Exception(f"The following packages required for the execution of this script are missing: "
                        f"{','.join(missing_dependencies)}")
    elif needs_commit:
        cache.commit()
