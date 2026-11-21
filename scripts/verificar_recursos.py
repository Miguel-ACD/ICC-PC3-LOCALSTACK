"""Muestra recursos y cantidades sin consumir mensajes de la cola."""
from app import BUCKET, TABLE, products, queue_url, s3, sqs, table

items = table.scan()['Items']
orders = sum(item.get('type') == 'order' for item in items)
users = sum(item.get('type') == 'user' for item in items)
images = s3.list_objects_v2(Bucket=BUCKET).get('KeyCount', 0)
messages = sqs.get_queue_attributes(QueueUrl=queue_url(), AttributeNames=['ApproximateNumberOfMessages'])['Attributes']['ApproximateNumberOfMessages']

print('AWS LOCAL — LOCALSTACK')
print(f'DynamoDB: tabla {TABLE} | productos: {len(products())} | pedidos: {orders} | usuarios: {users}')
print(f'S3: bucket {BUCKET} | imágenes: {images}')
print(f'SQS: cola pc3-pedidos | mensajes disponibles: {messages} (aproximado)')
