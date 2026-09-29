terraform {
  required_providers {
    external = {
      source = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}

variable "server_instance" {
	type = string
  description = "ID of the server resource. Used for dependency management."
}

variable "otp" {
	type = string
  description = "OTP output field of the associated generate-banner module."
}

variable "domain" {
	type = string
  description = "The ssh alias or FQDN under which the server is reachable via SSH."
}

variable "ssh_user" {
  type = string
  default = "root"
  description = "The user under which to attempt to login."
}

variable "timeout" {
  type = number
  default = 5*60
  description = "Timeout for the SSH connection in seconds. Connecting to the SSH server directly after boot is not sufficient, the relevant data is only available after cloud-init has completed."
}


data "external" "known_hosts" {
	depends_on = [var.server_instance]
  program = ["python3", "${path.module}/check_banner.py"]
	query = {
		domain = var.domain
		otp = var.otp
		ssh_user = var.ssh_user
		timeout = var.timeout
	}
}

output "known_hosts" {
	value = data.external.known_hosts.result.known_hosts
}
