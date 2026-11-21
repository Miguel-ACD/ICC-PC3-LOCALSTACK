"""Inserta 100 pedidos sintéticos en DynamoDB y los envía a SQS local."""
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.config import Config

endpoint = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
args = {'endpoint_url': endpoint, 'region_name': 'us-east-1', 'aws_access_key_id': 'test', 'aws_secret_access_key': 'test', 'config': Config(s3={'addressing_style': 'path'})}
table = boto3.resource('dynamodb', **args).Table('PC3-Tienda')
sqs = boto3.client('sqs', **args)
url = sqs.get_queue_url(QueueName='pc3-pedidos')['QueueUrl']

for number in range(1, 101):
    order_id = uuid.uuid4().hex[:12]
    order = {'pk': 'ORDER#' + order_id, 'type': 'order', 'order_id': order_id, 'customer': f'Cliente simulado {number:03}', 'total': Decimal('32.00'), 'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'EN_COLA', 'items': [{'id': 'p01', 'name': 'Cuaderno de tapa dura', 'quantity': 1, 'price': Decimal('32.00')}]}
    table.put_item(Item=order)
    try:
        sqs.send_message(QueueUrl=url, MessageBody=json.dumps(order, default=str))
    except Exception:
        table.update_item(Key={'pk': order['pk']}, UpdateExpression='SET #s = :s', ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':s': 'ERROR_COLA'})
        raise
    print(f'Pedido {number:03}/100 enviado: {order_id}')

print('Completado: 100 pedidos sintéticos guardados y enviados a SQS.')
