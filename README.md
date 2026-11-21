# Estación · PC3 LocalStack

Repositorio público: [Miguel-ACD/ICC-PC3-LOCALSTACK](https://github.com/Miguel-ACD/ICC-PC3-LOCALSTACK)

Tienda de demostración local para la PC3 de Introducción a Cognitive Computing. Permite consultar productos, agregarlos al carrito, registrar compras y acceder a un panel de administrador. Los datos se almacenan en DynamoDB local, las imágenes de usuario en S3 local y los pedidos se envían a SQS local, todo mediante LocalStack.

> Es una aplicación de laboratorio: las compras son simuladas y no se procesan pagos reales. No debe desplegarse como servicio público.

## Requisitos

- Windows con Debian u otra distribución WSL 2 y Docker Desktop, con integración WSL habilitada.
- Una cuenta LocalStack y un token personal con acceso a LocalStack para AWS.
- Docker Compose disponible desde la distribución WSL.

## Preparación y ejecución

1. Clona el repositorio y entra en la carpeta del proyecto desde tu distribución WSL.
2. Copia `.env.example` como `.env` y configura `LOCALSTACK_AUTH_TOKEN`, el usuario y la contraseña de administrador y un `SESSION_SECRET` largo y aleatorio. **No compartas ni subas `.env`.**
3. Ejecuta:

```bash
docker compose up -d --build
```

4. Abre [http://localhost:8081](http://localhost:8081). El acceso al administrador está en `/admin`.

El primer inicio puede tardar mientras se descarga la imagen y LocalStack activa la licencia. La aplicación crea la tabla, el bucket, la cola y los productos iniciales automáticamente.

## Prueba de 100 pedidos

Con los servicios activos, ejecuta en WSL desde la carpeta del proyecto:

```bash
docker compose exec -T web python scripts/simular_100_pedidos.py
docker compose exec -T web python -m scripts.verificar_recursos
```

Cada ejecución agrega 100 pedidos nuevos a DynamoDB y 100 mensajes a SQS. El script de verificación solo consulta los recursos y no consume los mensajes; el número de SQS es aproximado.

## Detener

```bash
docker compose stop
```

Por defecto, los datos de LocalStack de esta configuración son temporales y pueden perderse al recrear el contenedor. No uses credenciales ni datos personales reales.

## Documentación y evidencias

- [Documentación técnica](DOCUMENTACION_TECNICA.md)
- [Capturas de evidencia](evidencias/)

La solución usa credenciales AWS ficticias y el endpoint de LocalStack; no necesita acceso a una cuenta real de AWS.
