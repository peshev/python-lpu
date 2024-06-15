import os
import subprocess
import sys
from typing import Dict

import yaml


def file_digest(fileobj, digest, /, *, _bufsize=2 ** 18):
    """Hash the contents of a file-like object. Returns a digest object.

    *fileobj* must be a file-like object opened for reading in binary mode.
    It accepts file objects from open(), io.BytesIO(), and SocketIO objects.
    The function may bypass Python's I/O and use the file descriptor *fileno*
    directly.

    *digest* must either be a hash algorithm name as a *str*, a hash
    constructor, or a callable that returns a hash object.
    """
    # On Linux we could use AF_ALG sockets and sendfile() to archive zero-copy
    # hashing with hardware acceleration.
    digestobj = digest()

    if hasattr(fileobj, "getbuffer"):
        # io.BytesIO object, use zero-copy buffer
        digestobj.update(fileobj.getbuffer())
        return digestobj

    # Only binary files implement readinto().
    if not (
            hasattr(fileobj, "readinto")
            and hasattr(fileobj, "readable")
            and fileobj.readable()
    ):
        raise ValueError(
            f"'{fileobj!r}' is not a file-like object in binary reading mode."
        )

    # binary file, socket.SocketIO object
    # Note: socket I/O uses different syscalls than file I/O.
    buf = bytearray(_bufsize)  # Reusable buffer to reduce allocations.
    view = memoryview(buf)
    while True:
        size = fileobj.readinto(buf)
        if size == 0:
            break  # EOF
        digestobj.update(view[:size])

    return digestobj


def single(lst, default=None):
    it = iter(lst)
    result = next(it, default)
    try:
        next(it)
    except StopIteration:
        return result
    raise ValueError()


def hash_files(files, digest):
    for f in files:
        with open(f, "rb") as fp:
            # noinspection PyTypeChecker
            yield file_digest(fp, digest).hexdigest(), os.path.getsize(f), f


def walk_files(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            yield os.path.join(root, f)


def load_content(s, str_load_fn, file_load_fn=None):
    if isinstance(s, str):
        if s == "-":
            if file_load_fn:
                return file_load_fn(sys.stdin)
            else:
                return str_load_fn(sys.stdin.read())
        elif s.startswith("@"):
            with open(s[1:], "r") as fp:
                if file_load_fn:
                    return file_load_fn(fp)
                else:
                    return str_load_fn(fp.read())
        else:
            return str_load_fn(s)
    else:
        return s


def load_yaml(s):
    return load_content(s, yaml.safe_load, yaml.safe_load)


def load_text_lines(s):
    return load_content(s, lambda x: x.splitlines())


def read_file_lines(filename):
    with open(filename) as fp:
        return [line.rstrip("\n") for line in fp.readlines()]


class Config(object):
    def __init__(self, argparse_args, defaults):
        self.args = {}
        self.defaults = defaults
        if argparse_args.config:
            config_args = load_yaml(argparse_args.config)
            assert isinstance(config_args, dict), config_args
            self.args.update(config_args)
        self.args.update({
            k: v
            for k, v in
            vars(argparse_args).items()
            if v is not None and v != [] and k not in ["config"]
        })

    def is_present(self, k):
        return k in self.args and self.args[k] is not None

    def get(self, k):
        return self.args[k] if self.is_present(k) else self.defaults.get(k)

    def __getitem__(self, item):
        return self.get(item)


def get_dpkg_architecture() -> Dict[str, str]:
    return {
        k: v
        for k, v in
        (
            line.split("=", maxsplit=1)
            for line in
            subprocess.check_output(["dpkg-architecture"], stderr=subprocess.DEVNULL).decode().splitlines()
        )
    }


def get_lsb_release() -> Dict[str, str]:
    return {
        k: v.strip()
        for k, v in
        (
            line.split(":", maxsplit=1)
            for line in
            subprocess.check_output(["lsb_release", "-a"], stderr=subprocess.DEVNULL).decode().splitlines()
        )
    }


def get_codename():
    return get_lsb_release()["Codename"]
