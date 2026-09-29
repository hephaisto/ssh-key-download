variable "regenerate" {
  type = bool
  default = false
  description = "Regenerate OTP values on each run. This will regenerate the depending server on every run, too."
}

output "runcmd" {
  value = [
    "/usr/local/write-banner.sh ${random_password.otp.result}",
  ]
}

output "otp" {
  value = random_password.otp.result
}

resource "random_password" "otp" {
  length = 20
  lower = false
  upper = false
  numeric = false
  special = true
  override_special = "0123456789ABCDEF"
  keepers = {
    run = var.regenerate ? timestamp() : "const"
  }
}

output "write_files" {
  value = [
    {
      path = "/usr/local/write-banner.sh"
      owner = "root:root"
      permissions = "0740"
      content = <<-EOF
				#!/bin/bash

				bannerfile="/etc/ssh/banner"

				key=$1
				rm -f "$bannerfile"
				for f in /etc/ssh/*.pub; do
					content=($(cat $f))
					algo=$${content[0]}
					pubascii=$${content[1]}
					hmac=$(echo $pubascii | base64 --decode | openssl mac -digest SHA256 -macopt hexkey:$${key} -in - HMAC)
					echo "$algo=$hmac" >> $bannerfile
				done
				echo "Banner $bannerfile" > "/etc/ssh/sshd_config.d/60-banner.conf"
				systemctl reload ssh
      EOF
    },
	]
}


