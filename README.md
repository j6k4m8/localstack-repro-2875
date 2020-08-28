# Reproduce [localstack GitHub Issue #2875](https://github.com/localstack/localstack/issues/2875)

This repo reproduces issue [#2875](https://github.com/localstack/localstack/issues/2875) in the localstack repository.

## Usage

Start localstack in a docker-compose (all default config values).

```shell
docker-compose up
```

Then provision resources (queue and lambda)

```
python3 ./resources.py provision
```

If the above exists with no errors, the provision was successful.

Now invoke the lambda:

```
python3 ./resources.py invoke
```

The issue is that NO output will be returned and the localstack lambda will hang. If you are running in a docker container, you can `docker logs -f [containerID]` to see the following:

```
START RequestId: 2f80cbde-6331-15e6-9291-52b36855ca5b Version: $LATEST
I was able to create an SQS client.
```

But the following text will NOT be in the logs:

```
I was able to get the SQS queue URL.
```

This is because the following line in the lambda handler code hands indefinitely:

```python
queue_url = sqs_client.get_queue_url(QueueName="MyQueue")["QueueUrl"]
```
