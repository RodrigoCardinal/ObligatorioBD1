# Proyecto Flask con MySQL – Sistema de Reservas

Este proyecto utiliza Python, Flask y MySQL. Para poder ejecutarlo, el usuario debe crear un entorno virtual, instalar las dependencias, configurar MySQL, ejecutar las tablas, triggers, inserts y eventos, modificar la contraseña de MySQL en los archivos del proyecto y finalmente ejecutar los archivos necesarios.

## Requisitos previos
- Python instalado
- MySQL instalado

## Creación y activación del entorno virtual

### Windows
`python -m venv .venv`

`.\.venv\Scripts\Activate.ps1`      

### macOS / Linux
`python3 -m venv .venv`

`source venv/bin/activate`

## Instalación de dependencias
`pip install -r requirements.txt`

## Configuración de MySQL
El usuario debe tener MySQL instalado.
Luego deberá ejecutar, en este orden:

1. Creación de las tablas -> Tablas.sql
2. Creación de los triggers -> Triggers.sql
3. Inserts de ejemplo -> InsertEjemplo.sql
4. Creación del evento -> actualizar_estado_reserva.sql

(Estos archivos SQL se ejecutan directamente en MySQL.)

## Modificación de contraseñas en el proyecto

### app.py
En la línea 30 cambiar:
app.config['MYSQL_PASSWORD'] = 'tu_contraseña'

### hash_password.py
En linea 9 cambiar:
password='tu_contraseña'

## Ejecución del proyecto

Primero ejecutar:
python hash_password.py

Luego iniciar la aplicación:
python app.py

Por último, ¡ingrese al sistema!

## Autores
- Rodrigo Cardinal
- Mónica Deus
- Ulises Rattin