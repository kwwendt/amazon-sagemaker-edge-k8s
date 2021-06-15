#FROM nvcr.io/nvidia/l4t-base:r32.5.0
FROM public.ecr.aws/lts/ubuntu:latest

ADD 1.20210512.96da6cc.tgz /opt/edge_manager/agent
RUN chmod +x /opt/edge_manager/agent/bin/*
RUN apt update -y && \
	apt install -y curl sudo ca-certificates && \
	update-ca-certificates --fresh && \
	rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/edge_manager/agent/bin:/home/agent/bin:$PATH

ENV TVM_TENSORRT_MAX_WORKSPACE_SIZE=2147483647

WORKDIR /home/agent

ADD models /home/agent/models
ADD certs /home/agent/certs
ADD conf /home/agent/conf

RUN mkdir -p /home/agent/sock
RUN mkdir -p /tmp/.X11-unix

RUN mkdir -p /home/agent/bin/ && echo "\
if [ ! -f \"/home/agent/conf/agent.json\" ]; then\n\
    echo $(ls)\n\
    echo \"Please, mount dir 'conf' from host to '/home/agent/conf'. This dir needs to contain config.json, certificates and other stuff\"\n\
    exit 0\n\
fi\n\
sagemaker_edge_agent_binary -c /home/agent/conf/agent.json -a /home/agent/sock/edge_agent -f\n\
" >> bin/init_agent.sh

RUN chmod +x bin/init_agent.sh
ENTRYPOINT ["/bin/bash", "/home/agent/bin/init_agent.sh"]