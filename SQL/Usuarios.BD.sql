DROP DATABASE IF EXISTS ObligatorioBD1;
CREATE DATABASE ObligatorioBD1;

CREATE USER 'admin_user'@'localhost' IDENTIFIED BY 'administrador';
CREATE USER 'user'@'localhost' IDENTIFIED BY 'usuario';

GRANT ALL PRIVILEGES ON ObligatorioBD1.* TO 'admin_user'@'localhost';
GRANT SELECT, INSERT ON ObligatorioBD1.* TO 'user'@'localhost'; # Solo puede leer y agregar datos

FLUSH PRIVILEGES; # Aplica los cambios inmediatamente