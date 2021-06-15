# Amazon SageMaker Edge Manager YOLO v4 + Kubernetes Deployment

### **NOTE**: Please be advised, the artifacts in this repository should not be used in a production environment without extensive testing.

In this demo, we will deploy a pre-trained YOLO v4 model using Amazon SageMaker Edge Manager. We will containerize both the agent & corresponding model artifacts, config files, and IoT certificates as well as the driver application that interacts with the model to perform inference.

## Pre-requisite steps
1. Clone this repo locally

2. Ensure Docker is installed on your machine

3. AWS CLI credentials or the ability to assume a role which has the following permissions:
   - s3:GetObject
   - ecr:CreateRepository
   - ecr:PutImage

4. A Kubernetes cluster created and configured so `kubectl` can interact with the cluster. For this demo, I tested using Amazon EKS with a Node Group with c5.4xlarge instances.

## Steps
1. In Amazon SageMaker Studio, execute the notebook provided as part of this repo: **`SM_Edge_Demo.ipynb`**

2. Once you have completed the notebook steps, we can download our deployment artifacts to build our containers.

3. Execute the following commands to download the artifacts from Amazon S3.
```
aws s3 cp s3://<sagemaker-bucket-from-notebook>/agent_deployment/agent_deployment_package.tar.gz ./
```

```
aws s3 cp s3://<sagemaker-bucket-from-notebook>/agent_deployment/<model_name>-<model_version>.tar.gz ./
```

4. Now let's un-tar our packages and move our Dockerfile and build script into the appropriate locations.
```
tar -zxvf agent_deployment_package.tar.gz -C ./
mv ./agent_files/Dockerfile ./agent/
mv ./agent_files/build.sh ./agent/
tar -zxvf <model_name>-<model_version>.tar.gz -C ./agent/models/<device_id>/<model_name>/<model_version>/
```

5. Let's also move our Client API stubs into the driver_app directory since those will be used by our application.
```
mv ./agent/app/* ./driver_app/
rmdir ./agent/app
```

6. Now that everything is in the right place, let's build our containers. First, we will retrieve an authentication token and authenticate the Docker client to our registry
```
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws-account-id>.dkr.ecr.<region>.amazonaws.com
```

7. Next, we will build & push the edge agent container.
```
aws ecr create-repository --repository-name smagent
cd agent
chmod +x build.sh
./build.sh
docker tag edge_manager:1.0 <aws-account-id>.dkr.ecr.<region>.amazonaws.com/smagent:latest
docker push <aws-account-id>.dkr.ecr.<region>.amazonaws.com/smagent:latest
```

8. Next, we can build & push the driver application container.
```
aws ecr create-repository --repository-name smapp
cd ../driver_app
docker build -t driver_app:1.0 .
docker tag driver_app:1.0 <aws-account-id>.dkr.ecr.<region>.amazonaws.com/smapp:latest
docker push <aws-account-id>.dkr.ecr.<region>.amazonaws.com/smapp:latest
```

9. Now that our containers are in ECR, we can deploy the containers. For this example, we have provided a sample Kubernetes deployment file that deploys a single Pod with 2 containers (1 for the agent and 1 for the driver application). **Note**: make sure to update the template file with your ECR repository URL information.
```
kubectl config set-context --current --namespace=amazon-sm-edge
kubectl apply -f sagemaker_edge_deployment.yml
```

10. The driver application is a Python Flask app that performs object detection on images downloaded from Amazon S3. If you are using EKS, please ensure your Nodes have the appropriate permissions in the instance profile to interact with S3. 

11. Additionally, to interact with the exposed service, you can create an Application Load Balancer which routes HTTP traffic on port 80 to TCP traffic on port 5001 with the target group being the nodes in the Node Group.

## Contributions

**Huge** thank you to Samir for creating this docker container for the SageMaker Edge Agent: https://github.com/samir-souza/laboratory/tree/master/08_EdgeMLGettingStarted/sagemaker_edge_manager_agent_docker