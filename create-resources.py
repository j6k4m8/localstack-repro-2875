import io
import json
import sys
import time
import zipfile
from zipfile import ZipFile, ZipInfo

import boto3

ASSUME_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "",
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "apigateway.amazonaws.com",
                        "lambda.amazonaws.com",
                        "events.amazonaws.com" "sqs.amazonaws.com",
                    ]
                },
                "Action": "sts:AssumeRole",
            }
        ],
    }
)

QUEUE_NAME = "MyQueue"
FUNCTION_NAME = "MyFunction"

FUNCTION_HANDLER = """
import json
import os

import boto3

def handler(event, lambda_context):

    sqs_client = boto3.client(
        "sqs",
        endpoint_url="http://172.17.0.1:4566",
        # endpoint_url="http://" + os.getenv("LOCALSTACK_HOSTNAME") + ":4566",
        aws_access_key_id="foo",
        aws_secret_access_key="foo",
        region_name='us-east-1'
    )

    print("I was able to create an SQS client.")
    queue_url = sqs_client.get_queue_url(QueueName="MyQueue")["QueueUrl"]
    print("I was able to get the SQS queue URL.")
    result = json.dumps({"queue_url": queue_url})
    print(result)
    return result

"""


class PermissiveZipFile(ZipFile):
    def writestr(self, zinfo_or_arcname, data, compress_type=None):
        if not isinstance(zinfo_or_arcname, ZipInfo):
            zinfo = ZipInfo(
                filename=zinfo_or_arcname, date_time=time.localtime(time.time())[:6]
            )

            zinfo.compress_type = self.compression
            if zinfo.filename[-1] == "/":
                zinfo.external_attr = 0o40775 << 16  # drwxrwxr-x
                zinfo.external_attr |= 0x10  # MS-DOS directory flag
            else:
                zinfo.external_attr = 0o664 << 16  # ?rw-rw-r--
        else:
            zinfo = zinfo_or_arcname

        super(PermissiveZipFile, self).writestr(zinfo, data, compress_type)


def generate_zip():
    mem_zip = io.BytesIO()

    files = [("main.py", FUNCTION_HANDLER)]

    with PermissiveZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, bytes in files:
            zf.writestr(name, bytes)

    return mem_zip.getvalue()


# Create boto clients:

sqs_client = boto3.client(
    "sqs",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="foo",
    aws_secret_access_key="foo",
)

lambda_client = boto3.client(
    "lambda",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="foo",
    aws_secret_access_key="foo",
)

iam_client = boto3.client(
    "iam",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="foo",
    aws_secret_access_key="foo",
)


def provision_resources():
    # Create queue:

    new_queue_request = sqs_client.create_queue(
        QueueName=QUEUE_NAME, Attributes={"FifoQueue": "false"}
    )

    queue_arn = sqs_client.get_queue_attributes(
        QueueUrl=new_queue_request["QueueUrl"], AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]

    # First, create a lambda execution role in IAM.

    # This means creating a Policy for a user:
    try:
        role = iam_client.get_role(RoleName="role_lambda_execution")
    except:
        role = iam_client.create_role(
            RoleName="role_lambda_execution", AssumeRolePolicyDocument=ASSUME_POLICY,
        )
    role_arn = role["Role"]["Arn"]

    try:
        lambda_function = lambda_client.get_function(FunctionName=FUNCTION_NAME)
        lambda_arn = lambda_function["Configuration"]["FunctionArn"]
    except:
        lambda_function = lambda_client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.8",
            Role=role_arn,
            Handler="main.handler",
            Code={"ZipFile": generate_zip()},
        )
        lambda_arn = lambda_function["FunctionArn"]


def invoke_lambda():
    response = lambda_client.invoke(FunctionName=FUNCTION_NAME)
    # print(response)
    return json.load(response["Payload"])


if sys.argv[-1] == "provision":
    provision_resources()

elif sys.argv[-1] == "invoke":
    print(invoke_lambda())
