DROP DATABASE IF EXISTS ObligatorioBD1;
CREATE DATABASE ObligatorioBD1 DEFAULT CHARACTER SET utf8 COLLATE utf8_spanish_ci;
USE ObligatorioBD1;

CREATE TABLE login(
    correo VARCHAR(30) PRIMARY KEY,
    contraseña VARCHAR(50),
    es_administrador BOOLEAN
);

CREATE TABLE participante (
    ci int PRIMARY KEY,
    nombre varchar(50),
    apellido varchar(50),
    email varchar(100)
);

CREATE TABLE programa_academico(
    nombre_programa VARCHAR(30) PRIMARY KEY,
    id_facultad INT,
    tipo VARCHAR(20)
);

CREATE TABLE participante_programa_academico(
    id_alumno_programa int PRIMARY KEY auto_increment,
    ci_participante int,
    nombre_programa varchar(30),
    rol varchar(20),
    foreign key (ci_participante) references participante(ci),
    foreign key (nombre_programa) references programa_academico(nombre_programa)
);

CREATE TABLE facultad(
    id_facultad INT,
    nombre VARCHAR(50)
);

CREATE TABLE edificio(
    nombre_edificio varchar(50) primary key,
    direccion varchar(100),
    departamento varchar(50)
);

CREATE TABLE sala (
    nombre_sala varchar(50),
    edificio varchar(50),
    PRIMARY KEY (nombre_sala,edificio),
    capacidad int,
    tipo_sala varchar(50),
    foreign key (edificio) references edificio(nombre_edificio)
);

CREATE TABLE turno (
    id_turno int primary key auto_increment,
    hora_inicio time,
    hora_fin time
);

CREATE TABLE reserva (
    id_reserva INT PRIMARY KEY,
    nombre_sala VARCHAR(50),
    edificio VARCHAR(50),
    fecha DATE,
    id_turno INT,
    estado VARCHAR(20),
    FOREIGN KEY (nombre_sala,edificio) REFERENCES sala (nombre_sala,edificio),
    FOREIGN KEY (id_turno) REFERENCES turno(id_turno)
);

CREATE TABLE reserva_participante (
    ci_participante INT,
    id_reserva INT,
    PRIMARY KEY (ci_participante,id_reserva),
    fecha_solicitud_reserva DATE,
    asistencia BOOLEAN,
    FOREIGN KEY (ci_participante) REFERENCES participante(ci),
    FOREIGN KEY (id_reserva) REFERENCES reserva(id_reserva)
);

CREATE TABLE sancion_participante(
    ci_participante INT,
    fecha_inicio DATE,
    fecha_fin DATE,
    PRIMARY KEY (ci_participante,fecha_inicio,fecha_fin),
    FOREIGN KEY (ci_participante) REFERENCES participante(ci)
);


/*  Nuva tabla  */

CREATE TABLE invitados(
    ci_invitado INT PRIMARY KEY,
    responsable_ci INT,
    nombre_invitado VARCHAR(20),
    apellido_invitado VARCHAR(20),
    email VARCHAR(50),
    fecha DATE,
    hora_inicio TIME,
    hora_fin TIME,
    FOREIGN KEY (responsable) REFERENCES participante(ci),
    FOREIGN KEY (fecha) REFERENCES reserva(fecha),
    FOREIGN KEY (hora_inicio,hora_fin) REFERENCES turno(hora_inicio,hora_fin)
);
