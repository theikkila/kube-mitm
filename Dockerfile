FROM ubuntu

RUN apt-get update && apt-get install -y wget
RUN wget https://snapshots.mitmproxy.org/5.0.1/mitmproxy-5.0.1-linux.tar.gz -O /tmp/mitm.tar.gz && cd /tmp && tar -xzvf mitm.tar.gz && mv mitmweb /bin/mitmweb
ADD proxy.sh /bin/proxy.sh
EXPOSE 45455
CMD proxy.sh
