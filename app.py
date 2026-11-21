import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ['SESSION_SECRET']
app.config.update(MAX_CONTENT_LENGTH=4 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
ENDPOINT = os.getenv('AWS_ENDPOINT_URL', 'http://localhost:4566')
REGION = 'us-east-1'
BUCKET = 'pc3-imagenes-usuarios'
QUEUE = 'pc3-pedidos'
TABLE = 'PC3-Tienda'
kwargs = {'endpoint_url': ENDPOINT, 'region_name': REGION, 'config': Config(s3={'addressing_style': 'path'}, retries={'max_attempts': 8})}
dynamo = boto3.resource('dynamodb', **kwargs)
s3 = boto3.client('s3', **kwargs)
sqs = boto3.client('sqs', **kwargs)
table = dynamo.Table(TABLE)

PRODUCTS = [
    {'id': 'p01', 'name': 'Cuaderno de tapa dura', 'description': 'Páginas punteadas para ideas y proyectos.', 'price': Decimal('32.00'), 'category': 'Escritura', 'color': 'sage'},
    {'id': 'p02', 'name': 'Botella térmica', 'description': 'Acero inoxidable, práctica para cada día.', 'price': Decimal('58.00'), 'category': 'Accesorios', 'color': 'clay'},
    {'id': 'p03', 'name': 'Bolígrafo de aluminio', 'description': 'Trazo suave y diseño ligero.', 'price': Decimal('24.00'), 'category': 'Escritura', 'color': 'ink'},
    {'id': 'p04', 'name': 'Bolsa de lona', 'description': 'Una compañera resistente para llevar lo esencial.', 'price': Decimal('45.00'), 'category': 'Accesorios', 'color': 'sand'},
]


def initialize():
    try:
        dynamo.create_table(TableName=TABLE, KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}], AttributeDefinitions=[{'AttributeName': 'pk', 'AttributeType': 'S'}], BillingMode='PAY_PER_REQUEST')
    except ClientError as exc:
        if exc.response['Error']['Code'] != 'ResourceInUseException':
            raise
    table.wait_until_exists()
    for product in PRODUCTS:
        table.put_item(Item={'pk': f"PRODUCT#{product['id']}", 'type': 'product', **product})
    try:
        s3.create_bucket(Bucket=BUCKET)
    except ClientError as exc:
        if exc.response['Error']['Code'] not in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
            raise
    sqs.create_queue(QueueName=QUEUE)


def queue_url():
    return sqs.get_queue_url(QueueName=QUEUE)['QueueUrl']


def products():
    return sorted([item for item in table.scan().get('Items', []) if item.get('type') == 'product'], key=lambda item: item['id'])


def admin_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return decorated


@app.get('/')
def index():
    catalog = products()
    cart = session.get('cart', {})
    lines = [{'product': product, 'quantity': cart[product['id']]} for product in catalog if product['id'] in cart]
    total = sum((line['product']['price'] * line['quantity'] for line in lines), Decimal('0'))
    return render_template('index.html', products=catalog, lines=lines, total=total, cart_count=sum(cart.values()))


@app.post('/cart/add/<product_id>')
def cart_add(product_id):
    if product_id not in {item['id'] for item in products()}:
        abort(404)
    cart = session.get('cart', {})
    cart[product_id] = min(cart.get(product_id, 0) + 1, 20)
    session['cart'] = cart
    flash('Producto agregado al carrito.', 'success')
    return redirect(url_for('index') + '#carrito')


@app.post('/cart/remove/<product_id>')
def cart_remove(product_id):
    cart = session.get('cart', {})
    cart.pop(product_id, None)
    session['cart'] = cart
    return redirect(url_for('index') + '#carrito')


@app.post('/checkout')
def checkout():
    name = request.form.get('name', '').strip()[:100]
    cart = session.get('cart', {})
    lines = [{'product': p, 'quantity': cart[p['id']]} for p in products() if p['id'] in cart]
    if not name or not lines:
        flash('Agrega productos y escribe tu nombre para confirmar.', 'error')
        return redirect(url_for('index') + '#carrito')
    order_id = uuid.uuid4().hex[:12]
    total = sum((line['product']['price'] * line['quantity'] for line in lines), Decimal('0'))
    item = {'pk': 'ORDER#' + order_id, 'type': 'order', 'order_id': order_id, 'customer': name, 'total': total, 'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'EN_COLA', 'items': [{'id': l['product']['id'], 'name': l['product']['name'], 'quantity': l['quantity'], 'price': l['product']['price']} for l in lines]}
    table.put_item(Item=item)
    try:
        sqs.send_message(QueueUrl=queue_url(), MessageBody=json.dumps(item, default=str))
    except Exception:
        table.update_item(Key={'pk': item['pk']}, UpdateExpression='SET #s = :s', ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':s': 'ERROR_COLA'})
        app.logger.exception('No se pudo enviar el pedido %s a SQS', order_id)
        flash('El pedido se guardó, pero no pudo enviarse a la cola. Consulta al administrador.', 'error')
        session.pop('cart', None)
        return redirect(url_for('index'))
    session.pop('cart', None)
    flash(f'Pedido {order_id} registrado y enviado a la cola.', 'success')
    return redirect(url_for('index'))


@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        valid_user = hmac.compare_digest(request.form.get('username', ''), os.environ['ADMIN_USER'])
        valid_password = hmac.compare_digest(request.form.get('password', ''), os.environ['ADMIN_PASSWORD'])
        if valid_user and valid_password:
            session.clear()
            session['admin'] = True
            return redirect(url_for('admin'))
        flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')


@app.post('/admin/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:100]
        upload = request.files.get('image')
        allowed = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
        if not name or not upload or upload.mimetype not in allowed:
            flash('Indica un nombre y una imagen JPG, PNG o WebP.', 'error')
            return redirect(url_for('admin'))
        uid = uuid.uuid4().hex
        key = f"users/{uid}{allowed[upload.mimetype]}"
        s3.upload_fileobj(upload.stream, BUCKET, key, ExtraArgs={'ContentType': upload.mimetype})
        table.put_item(Item={'pk': 'USER#' + uid, 'type': 'user', 'name': name, 'image_key': key})
        flash('Usuario guardado e imagen subida a S3 local.', 'success')
        return redirect(url_for('admin'))
    items = table.scan().get('Items', [])
    orders = sorted((i for i in items if i.get('type') == 'order'), key=lambda i: i.get('created_at', ''), reverse=True)
    users = [i for i in items if i.get('type') == 'user']
    attrs = sqs.get_queue_attributes(QueueUrl=queue_url(), AttributeNames=['ApproximateNumberOfMessages'])
    return render_template('admin.html', orders=orders, users=users, queued=attrs['Attributes']['ApproximateNumberOfMessages'])


@app.get('/admin/image/<uid>')
@admin_required
def user_image(uid):
    item = table.get_item(Key={'pk': 'USER#' + uid}).get('Item')
    if not item:
        abort(404)
    obj = s3.get_object(Bucket=BUCKET, Key=item['image_key'])
    return send_file(BytesIO(obj['Body'].read()), mimetype=obj.get('ContentType', 'application/octet-stream'))


if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=8000)


initialize()
