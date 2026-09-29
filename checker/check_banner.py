import base64
import datetime
import json
import subprocess
import sys
import tempfile
import time

def read_input():
    return json.loads(sys.stdin.read())

def download_key_and_banner(domain: str, ssh_user: str, timeout: int):
    end = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    while True:
        with tempfile.NamedTemporaryFile("r") as f:
            try:
                p = subprocess.run([
                    "ssh", 
                    "-o", "PubkeyAuthentication=no", # immediately fail
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", f"UserKnownHostsFile={f.name}",
                    "-o", "HashKnownHosts=false",
                    f"{ssh_user}@{domain}",
                    ], text=True, stderr=subprocess.PIPE)
                known_hosts = [l.strip() for l in f.readlines()]
                banner = [line.strip() for line in p.stderr.split("\n") if "=" in line]
                if len(banner) == 0:
                    raise RuntimeError("no banner received")
            except (RuntimeError, subprocess.CalledProcessError):
                if datetime.datetime.now() > end:
                    raise RuntimeError("Timeout exceeded while connecting to server") from None
                time.sleep(5.0)
                continue
        return known_hosts, banner

def parse_hosts(expected_host: str, host_lines: list[str]):
   for host_line in host_lines:
       try:
           host_name, host_algorithm, host_pubkey = host_line.split()
           if host_name == expected_host:
               yield host_algorithm, host_pubkey
       except ValueError:
           pass

def parse_banner(banner_lines: list[str]) -> dict[str, str]:
    result = {}
    for line in banner_lines:
        try:
            algo, hmac = line.split("=")
        except ValueError:
            pass
        result[algo] = hmac
    return result


def calculate_hmac(pubkey: str, hmac_hex: str):
    pubkey_bytes = base64.b64decode(pubkey)
    p = subprocess.run(["openssl", "mac", "-digest", "SHA256", "-macopt", f"hexkey:{hmac_hex}", "-in", "-", "HMAC"], input=pubkey_bytes, check=True, stdout=subprocess.PIPE)
    return p.stdout.decode().strip()

def evaluate(domain: str, ssh_user: str, otp: str, timeout: int):
    known_hosts, banner = download_key_and_banner(domain, ssh_user, timeout)
    advertised_hmacs = parse_banner(banner)

    result = ""
    
    for host_algorithm, host_pubkey in parse_hosts(domain, known_hosts):
        expected_hmac = calculate_hmac(host_pubkey, otp)
        try:
            actual_hmac = advertised_hmacs[host_algorithm]
        except KeyError:
            # we silently ignore entries which are not advertised
            continue

        result += f"{domain} {host_algorithm} {host_pubkey}\n"

    return {"known_hosts": result}

def write_result(data: dict):
    print(json.dumps(data))

def main():
    try:
        args = read_input()
        write_result(evaluate(domain=args["domain"], ssh_user=args["ssh_user"], otp=args["otp"], timeout=int(args["timeout"])))
    except Exception as e:
        print(str(e), file=sys.stderr)
        raise

if __name__ == "__main__":
    main()
