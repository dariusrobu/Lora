#!/bin/sh
set -eu

domain="gui/$(id -u)"
launchctl kickstart -k "$domain/com.lora.v2.bot"
launchctl kickstart -k "$domain/com.lora.v2.worker"

printf 'Lora v2 Telegram bot and delivery worker restarted.\n'
