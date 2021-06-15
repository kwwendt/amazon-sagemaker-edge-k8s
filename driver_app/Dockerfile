FROM public.ecr.aws/entelect-challenge/languages/python_pytorch:2021

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update && \
   apt-get -y install gcc mono-mcs && \
   apt-get -y install libopencv-dev && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir /app
RUN touch /app/predict_img.jpg
COPY edgeagentclient.py /app
COPY agent_pb2.py /app
COPY agent_pb2_grpc.py /app
COPY flask_driver.py /app
COPY coco.names /app
COPY utils.py /app
WORKDIR /app
RUN pip3 install boto3
RUN pip3 install sysv_ipc
RUN pip3 install grpcio
RUN pip3 install flask
RUN pip3 install protobuf
RUN pip3 install numpy
RUN pip3 install matplotlib
RUN pip3 install opencv-python
RUN pip3 install opencv-contrib-python
EXPOSE 5001
ENTRYPOINT [ "python3", "flask_driver.py" ]