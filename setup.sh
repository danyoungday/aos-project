#!/bin/bash

sudo apt-get update && sudo apt-get upgrade -y

# Set up eval script
chmod +x eval.sh

# Compile probe
gcc -O2 -Wall probe.c -o probe

# Python setup
sudo apt-get install python3.10-venv -y
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt