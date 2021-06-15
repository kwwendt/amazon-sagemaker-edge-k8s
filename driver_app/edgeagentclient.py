import torch
import os
import sys
import grpc
import logging
import agent_pb2 as agent
import agent_pb2_grpc as agent_grpc
import struct
import uuid
import base64
import io
import json
import utils
import numpy as np
import torchvision.transforms as transforms

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
JPEG_CONTENT_TYPE = 'application/x-image'
MAX_MESSAGE_LENGTH = 80000000
logger = logging.getLogger()

class EdgeAgentClient(object):
    """ Helper class that uses the Edge Agent stubs to
        communicate with the SageMaker Edge Agent through unix socket.
        
        To generate the stubs you need to use protoc. First install/update:
        pip3 install -U grpcio-tools grpcio protobuf
        then generate the code using the provided agent.proto file
        
        python3 -m grpc_tools.protoc \
            --proto_path=$PWD/agent/docs/api --python_out=. --grpc_python_out=. $PWD/agent/docs/api/agent.proto
        
    """
    def __init__(self, channel_path):
        # connect to the agent and list the models
        self.channel = grpc.insecure_channel('unix://%s' % channel_path, options=[
                ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
                ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
            ],)
        self.agent = agent_grpc.AgentStub(self.channel)
        self.model_map = {}
        self.__update_models_list__()            
    
    def __update_models_list__(self):
        models_list = self.agent.ListModels(agent.ListModelsRequest())
        self.model_map = {m.name:{'in': m.input_tensor_metadatas, 'out': m.output_tensor_metadatas} for m in models_list.models}
        return self.model_map
    
    def capture_data(self, model_name, input_data, output_data):
        try:
            req = agent.CaptureDataRequest()
            req.model_name = model_name
            req.capture_id = str(uuid.uuid4())

            req.input_tensors.append( self.create_tensor(input_data, 'input' ) )
            req.output_tensors.append( self.create_tensor(output_data, 'output' ) )
            resp = self.agent.CaptureData(req)
        except Exception as e:
            logging.error(e)

    def create_tensor(self, x, tensor_name):
        if (x.dtype != np.float32):
            raise Exception( "It only supports numpy float32 arrays for this tensor" )
        tensor = agent.Tensor()
        tensor.tensor_metadata.name = tensor_name
        tensor.tensor_metadata.data_type = agent.FLOAT32
        for s in x.shape: tensor.tensor_metadata.shape.append(s)
        tensor.byte_data = x.tobytes()
        return tensor

    def predict(self, model_name, x, shm=False):
        image_tensor = agent.Tensor()

        if shm:
            image_tensor.shared_memory_handle.offset = 0
            image_tensor.shared_memory_handle.segment_id = x
        else:
            processed_img = utils.preprocess_image(x)
            
            image_tensor.byte_data = processed_img.tobytes()

        if self.model_map.get(model_name) is None:
            return None

        image_tensor_metadata = self.model_map[model_name]['in'][0]
        image_tensor.tensor_metadata.name = image_tensor_metadata.name
        image_tensor.tensor_metadata.data_type = image_tensor_metadata.data_type

        for shape in image_tensor_metadata.shape:
            image_tensor.tensor_metadata.shape.append(shape)
        predict_request = agent.PredictRequest()
        predict_request.name = model_name
        predict_request.tensors.append(image_tensor)
        predict_response = self.agent.Predict(predict_request)
        return predict_response

    def is_model_loaded(self, model_name):
        return self.model_map.get(model_name) is not None
    
    def load_model(self, model_name, model_path):
        """ Load a new model into the Edge Agent if not loaded yet"""
        try:
            if self.is_model_loaded(model_name):
                logging.info( "Model %s was already loaded" % model_name )
                return self.model_map
            req = agent.LoadModelRequest()
            req.url = model_path
            req.name = model_name
            resp = self.agent.LoadModel(req)

            return self.__update_models_list__()            
        except Exception as e:
            logging.error(e)        
            return None
        
    def unload_model(self, model_name):
        """ UnLoad model from the Edge Agent"""
        try:
            if not self.is_model_loaded(model_name):
                logging.info( "Model %s was not loaded" % model_name )
                return self.model_map
            
            req = agent.UnLoadModelRequest()
            req.name = model_name
            resp = self.agent.UnLoadModel(req)
            
            return self.__update_models_list__()
        except Exception as e:
            logging.error(e)        
            return None
    
    def write_to_shm(self, sm, file_name):
        if sm.attached: sm.detach()
        # set mode read/write
        sm.mode = 0o0606
        sm.attach()

        processed_img = utils.preprocess_image(file_name)

        sm.write(processed_img.tobytes())
        # set mode read only
        sm.mode = 0o0404

        return processed_img
