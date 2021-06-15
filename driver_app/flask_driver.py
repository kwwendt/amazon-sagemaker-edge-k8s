import os
import copy
import torch
import boto3
import logging
import numpy as np
from flask import request, Flask
from edgeagentclient import EdgeAgentClient
import torchvision
import torchvision.ops as ops
import torchvision.transforms as transforms
import cv2
import sysv_ipc as ipc
import utils

app = Flask(__name__)

channel_path = '/home/agent/sock/edge_agent'
client = EdgeAgentClient(channel_path=channel_path)

s3_client = boto3.client('s3')

# Load names of classes
classes = open('coco.names').read().strip().split('\n')

@app.route('/model/load', methods=['POST'])
def load_model():
    request_data = request.get_json()
    device_name = request_data['device_name']
    model_name = request_data['model_name']
    version = request_data['version']
    model_path = f"/home/agent/models/{device_name}/{model_name}/{version}"
    try:
        res = client.load_model(model_name=model_name, model_path=model_path)
        if res != None:
            return {'statusCode': 200}
        else:
            return {'statusCode': 500}
    except Exception as e:
        logging.error(e)
        print(e)
        return {'statusCode': 500}

@app.route('/model/unload', methods=['POST'])
def unload_model():
    request_data = request.get_json()
    model_name = request_data['model_name']

    try:
        res = client.unload_model(model_name=model_name)
        
        if res != None:
            return {'statusCode': 200}
        else:
            return {'statusCode': 500}
    except Exception as e:
        logging.error(e)
        print(e)
        return {'statusCode': 500}

@app.route('/model/predict', methods=['POST'])
def model_predict():
    request_data = request.get_json()
    model_name = request_data['model_name']
    s3_img_bucket = request_data['s3_bucket']
    s3_img_key = request_data['s3_key']

    img_loc, extension = os.path.splitext(s3_img_key)
    file_name = f"predict_img{extension}"

    with open(file_name, 'wb') as data:
        s3_client.download_fileobj(Bucket=s3_img_bucket, Key=s3_img_key, Fileobj=data)
    
    try:
        tensor_output = []
        shape=(1,3,608,608)
        payload_size=4
        for i in shape: payload_size *= i

        key=41
        sm=None

        ## create/reserve some space in the device's shared memory
        try:
            sm = ipc.SharedMemory(key, mode=0o606, size = payload_size)
        except ipc.ExistentialError as e:
            sm = ipc.SharedMemory(key, flags=ipc.IPC_CREX, size = payload_size)
        
        input_data = client.write_to_shm(sm, file_name)
        res = client.predict(model_name=model_name, x=sm.id, shm=True)

        image = cv2.imread(file_name)
        resized = cv2.resize(image, (608, 608))

        if res != None:
            tensors = res.tensors

            # Boxes
            box_tensor = tensors[0]
            boxes_data = np.frombuffer(box_tensor.byte_data, dtype=np.float32)
            boxes_np = copy.deepcopy(boxes_data.reshape(box_tensor.tensor_metadata.shape))
            boxes = torch.from_numpy(boxes_np)

            # Scores
            scores_tensor = tensors[1]
            scores_data = np.frombuffer(scores_tensor.byte_data, dtype=np.float32)
            scores_np = copy.deepcopy(scores_data.reshape(scores_tensor.tensor_metadata.shape))
            scores = torch.from_numpy(scores_np)

            boxes_v2 = utils.post_processing(resized, 0.4, 0.6, boxes, scores)
            utils.plot_boxes_cv2(resized, boxes_v2[0], savename='output.jpg', class_names=classes)

            with open('output.jpg', 'rb') as data:
                s3_client.upload_fileobj(Bucket=s3_img_bucket, Key=f"{img_loc}_annotated.jpg", Fileobj=data)

            client.capture_data(model_name=model_name, input_data=input_data[0, :, :], output_data=np.asarray(boxes_v2[0], dtype=np.float32))

            if sm is not None:
                sm.detach()
                sm.remove()
                sm = None

            return {'statusCode': 200}
        else:
            if sm is not None:
                sm.detach()
                sm.remove()
                sm = None
            return {'statusCode': 500}
    except Exception as e:
        logging.error(e)
        if sm is not None:
            sm.detach()
            sm.remove()
            sm = None
        return {'statusCode': 500}

    return {'statusCode': 200}

@app.route('/', methods=['POST', 'GET'])
def model_hb():
    print('Health check response')
    return {'statusCode': 200}

if __name__ == "__main__":
    app.run(host ='0.0.0.0', port = 5001)
