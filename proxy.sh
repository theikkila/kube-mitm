#!/usr/bin/env bash

i=45455
for p in $PORTS
do
    mitmweb --listen-host 0.0.0.0 -k --listen-port=$p --no-web-open-browser --web-iface 0.0.0.0 --web-port $i --mode reverse:$SERVICE:$p &
    # call your procedure/other scripts here below
    echo "$i -> $SERVICE:$p"
    i=$((i+1))
done
wait