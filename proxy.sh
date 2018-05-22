#!/usr/bin/env bash

mitmweb --listen-host 0.0.0.0 --listen-port=$PORT --no-web-open-browser --web-iface 0.0.0.0 --web-port 45455 --mode reverse:$SERVICE
