import re
import subprocess

gpg_field_names = [
    "record_type", "validity", "key_length", "key_algorithm", "key_id", "creation_date",
    "expiration_date", "certificate", "owner_trust", "user_id", "signature_class", "key_capabilities",
    "issuer_certificate_fingerprint", "flag", "serial_number", "hash_algorithm", "curve_name",
    "compliance_flags", "last_update", "origin", "comment"
]


def gpg_parse_key_list(lines):
    return [dict(zip(gpg_field_names, line.split(":"))) for line in lines]


def gpg_show_keys(filename=None, content=None):
    assert not (filename is not None and content is not None)
    args = [
        "gpg",
        "--show-keys",
        "--with-colons",
    ]
    if filename is not None:
        args.append(filename)
    p = subprocess.run(args, capture_output=True, input=content)
    return gpg_parse_key_list(p.stdout.decode().splitlines())


def gpg_list_keys(key_id=None, secret=False):
    args = [
        "gpg",
        "--list-secret-keys" if secret else "--list-keys",
        "--with-colons"
    ]
    if key_id is not None:
        args.append(key_id)
    p = None
    try:
        p = subprocess.run(args, capture_output=True)
    except subprocess.CalledProcessError as e:
        if e.returncode:
            if e.returncode == 2 and \
                    key_id is not None and \
                    e.stderr.splitlines()[0] == "gpg: error reading key: No secret key":
                return []
        else:
            raise
    assert p is not None
    return gpg_parse_key_list(p.stdout.decode().splitlines())


def get_secret_key_ids(key_list):
    return [k["key_id"] for k in key_list if k["record_type"] == "sec"]


def gpg_gen_key(**key_meta):
    assert 'Passphrase' in key_meta
    gpg_batch = "\n".join(f"{k}: {v}" for k, v in key_meta.items())
    gpg_batch += "\n"
    gpg_batch += "\n".join(["%no-ask-passphrase", "%no-protection", "%commit"])
    gpg_batch += "\n"
    gen_key_output = subprocess.check_output([
        "gpg",
        "--gen-key",
        "--batch"],
        input=gpg_batch.encode(),
        stderr=subprocess.STDOUT).decode()
    return re.search("gpg: key ([0-9A-F]+) marked as ultimately trusted", gen_key_output).group(1)


def gpg_export_secret_key(key_id, output_file):
    subprocess.check_output([
        "gpg",
        "--export-secret-keys",
        "--armor",
        "-o", output_file,
        key_id
    ], stderr=subprocess.DEVNULL)


def gpg_import(key_file):
    return subprocess.check_output([
        "gpg",
        "--import",
        key_file
    ], stderr=subprocess.DEVNULL)


def gpg_export_key(key_id, output_file):
    subprocess.check_output([
        "gpg",
        "--export",
        "--armor",
        "--yes",
        "--output", output_file,
        key_id
    ], stderr=subprocess.DEVNULL)


def gpg_sign(key_id, key_passphrase, input_file, output_file, detached=False):
    subprocess.check_output([
        "gpg",
        "--sign",
        "--detach-sign" if detached else "--clearsign",
        "--armor",
        "--yes",
        "--default-key", key_id,
        "--passphrase", key_passphrase,
        "-o", output_file,
        input_file
    ], stderr=subprocess.DEVNULL)


def gpg_dearmor(key_content, output_filename=None, overwrite=True):
    args = [
        "gpg",
        "--no-tty",
        "--batch",
        "--dearmor"
    ]
    if overwrite:
        args.append("--yes")
    if output_filename is not None:
        args.extend(["-o", output_filename])
    p = subprocess.run(args, input=key_content, capture_output=True)
    if output_filename is None:
        return p.stdout
