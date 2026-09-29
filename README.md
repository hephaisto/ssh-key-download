# ssh-key-download

This is a small module to simplify checking of SSH host keys managed with `OpenTofu` + `cloud-init`.

## Rationale

Usually, SSH host keys are generated on the server and there is no way for clients to verify the host keys when the server has been regenerated.
Many users fall back to trust-on-first-use, which opens up the whole infrastructure to attack by MITM attack between the TF controller and the cloud provider.
While this may be an acceptable risk when the controller runs on the same infrastructure as the managed infrastructure, it is unacceptable otherwise.

## Alternative solutions

### Persisting the private key between teardowns
It is possible to save the host keys on a mounted volume, which introduces the following problems:
* Exposes secrets in the mounted volume
* Does not solve trust-on-first-use when the server is generated for the first time

### Saving the private key in the IaC controller
The private key can be saved in the IaC config repository, which intruduces the following problems:
* The private key can be extracted by having read access to the IaC repository or the cache

### Certificate authority
It is possible to use complex setups where the newly generated server enrolls with a CA, which introduces the following problems:
* Requires separate CA server
* Requires initial secret for enrollment (hen/egg problem)

## Solution

* This script generates an OTP value for each server
* The OTP gets injected by `cloud-init` into the server
* The server calculates a `HMAC(OTP, pubkey)` and puts the values in the SSH banner
    * Neither `HMAC` nor `pubkey` needs to be protected against disclosure
* After provisioning, OpenTofu connects to the server and downloads `HMAC` and `pubkey` to a temporary location
* OpenTofu validates that the HMAC is valid and generates a `known_hosts` file

### Remaining security pitfalls

The OTP value is still sensitive against extraction.
However, an attacker needs to extract the OTP value from the cache AND perform an MITM attack between the IaC controller and the infrastructure during provisioning.
In contrast to saving the private key itself, an attacker cannot immediately use the OTP value to impersonate the SSH remote server.

The IaC runner should protect its cache value against extractions in order to mitigate this.
If the cache cannot be protected, the servers can be provisioned with `regenerate=true`, which will generate a new OTP value on every run, at the cost of re-provisioning every single server each time.
Even without protection of the cache, using this mechanism provides an additional level of security, especially if the network between the IaC runner and the infrastructure is considered hostile.

### Usability drawbacks

* The generated `known_hosts` file must be copied manually to the machines connecting via SSH.
* Reading the SSH keys is only possible after the hosts are completely up. This extends the time until completion of the run significantly, especially if the servers perform complex tasks during cloud-init.

## Dependencies
### Host system
* `python3`
* `openssh client`

### Providers
* `hashicorp/external` (declared in checker)

## Usage

```hcl
# generate the cloud-init snippets
module "test1" {
  source = "./ssh-key-download/generate-banner"
}

# generate cloud-init config
data "cloudinit_config" "example_config_1" {
  gzip = false
  base64_encode = false

  part {
    content_type = "text/cloud-config"
    content = yamlencode({
      write_files = concat([
        module.test1.write_files,
        # other files
        ]
      )
      runcmd = concat(
        module.test1.runcmd,
        # other commands
      )
    })
  }
}

# declare MYSERVER
# with user_data = data.cloudinit_config.example_config_1.rendered
# make the server available at test.example.com

module "ssh_checker_test1" {
  source = "./ssh-key-download/checker"
  server_instance = MYSERVER.id
  domain = "test.example.com"
  otp = module.test1.otp
}

output "known_hosts" {
  value = join("", [
    module.test1.known_hosts
  ])
}
```

You can then extract a `known_hosts` file suitable by use with `openssh` with:
```bash
tofu output -raw known_hosts
```
