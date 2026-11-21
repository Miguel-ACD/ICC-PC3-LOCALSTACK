# Documentación técnica — PC3

**Curso:** Introducción a Cognitive Computing  
**Estudiante:** Miguel Ángel Champi Hinojosa — 202110072  
**Objetivo:** tienda local con servicios AWS simulados y ejecución en contenedores sobre WSL 2.

**Repositorio:** [github.com/Miguel-ACD/ICC-PC3-LOCALSTACK](https://github.com/Miguel-ACD/ICC-PC3-LOCALSTACK)

## Arquitectura

```text
Navegador → Flask / tienda y administración → LocalStack
                                            ├─ DynamoDB: productos, pedidos y usuarios
                                            ├─ S3: imágenes de usuario
                                            └─ SQS: mensajes de pedidos
```

`compose.yaml` define dos servicios: `web`, construido desde `Dockerfile`, y `localstack`. La aplicación se ejecuta con Flask y Gunicorn; Boto3 se comunica con LocalStack mediante `http://localstack:4566` y credenciales ficticias. La interfaz y el puerto de LocalStack están publicados solo en `127.0.0.1`.

## Funcionalidad

1. Al iniciar, la aplicación crea la tabla `PC3-Tienda`, el bucket `pc3-imagenes-usuarios` y la cola `pc3-pedidos`, y carga cuatro productos de demostración.
2. El comprador agrega artículos al carrito, indica su nombre y confirma una compra simulada. El pedido se guarda en DynamoDB y se envía a SQS. Si el envío a la cola falla, el pedido queda marcado `ERROR_COLA`.
3. El administrador inicia sesión con las credenciales configuradas localmente en `.env`, consulta pedidos y carga imágenes JPG, PNG o WebP. El archivo se guarda en S3 local y la referencia del usuario en DynamoDB.
4. `scripts/simular_100_pedidos.py` genera 100 pedidos sintéticos, los guarda en la tabla y los envía a la cola. `scripts/verificar_recursos.py` muestra cantidades sin consumir mensajes.

## Archivos principales

- `app.py`: aplicación Flask, conexión a AWS emulado y reglas de carrito, acceso y pedidos.
- `templates/` y `static/`: interfaz de tienda y administración.
- `scripts/`: simulación de pedidos y consulta de recursos.
- `compose.yaml`, `Dockerfile` y `requirements.txt`: servicios, imagen y dependencias.
- `.env.example`: plantilla de configuración sin secretos.
- `evidencias/`: capturas tomadas durante la ejecución.

## Ejecución y verificación

Desde WSL, copiar `.env.example` a `.env`, configurar token y credenciales, y ejecutar `docker compose up -d --build`. La interfaz está en `http://localhost:8081`; LocalStack escucha en `http://localhost:4566`.

La ejecución comprobada incluyó acceso de administrador, compra, carga y lectura de imagen en S3 y simulación de 100 pedidos. Después de dos compras de prueba y la simulación se verificaron 102 pedidos y 102 mensajes disponibles, además de dos imágenes en el bucket. Las cantidades SQS son aproximadas y pueden cambiar con el uso.

## Alcance y seguridad

La aplicación es solo para laboratorio local: no procesa pagos reales, no usa AWS real y no proporciona garantías propias de un sistema de producción. Los servicios se enlazan a localhost. El token de LocalStack y las credenciales del administrador se guardan en `.env`, excluido de Git. La configuración no habilita persistencia de LocalStack: los datos pueden perderse al recrear el contenedor.
