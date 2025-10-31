USE ObligatorioBD1;

-- Tabla: login
INSERT INTO login (correo, contraseña) VALUES
('juan.perez@ucu.edu.uy', 'Jperez#2025!'),
('maria.gomez@ucu.edu.uy', 'Mgomez@45Ux'),
('ana.rodriguez@ucu.edu.uy', 'Ana_Rdz!89'),
('carlos.silva@ucu.edu.uy', 'SilvaC#33$'),
('sofia.fernandez@ucu.edu.uy', 'SofiFz_2025!'),
('martin.lopez@ucu.edu.uy', 'Mlopez#77*');
-- Tabla: facultad
INSERT INTO facultad (id_facultad, nombre) VALUES
(1, 'Facultad de Ingeniería y Tecnologías'),
(2, 'Facultad de Ciencias Empresariales'),
(3, 'Facultad de Psicología'),
(4, 'Facultad de Derecho');

-- Tabla: edificio
INSERT INTO edificio (nombre_edificio, direccion, departamento) VALUES
('Edificio Central', 'Av. 8 de Octubre 2738', 'Montevideo'),
('Edificio de Ingeniería', 'Bvar. Artigas 1514', 'Montevideo'),
('Campus Punta del Este', 'Av. Roosevelt 1234', 'Maldonado');

-- Tabla: programa_académico
INSERT INTO programa_academico (nombre_programa, id_facultad, tipo) VALUES
('Ingeniería Informática', 1, 'grado'),
('Administración de Empresas', 2, 'grado'),
('Psicología Clínica', 3, 'grado'),
('Derecho', 4, 'grado'),
('MBA', 2, 'posgrado'),
('Psicología Organizacional', 3, 'posgrado');

-- Tabla: participante
INSERT INTO participante(ci, nombre, apellido, email) VALUES
(49382716, 'Juan', 'Pérez', 'juan.perez@ucu.edu.uy'),
(51293487, 'María', 'Gómez', 'maria.gomez@ucu.edu.uy'),
(47851239, 'Ana', 'Rodríguez', 'ana.rodriguez@ucu.edu.uy'),
(50128394, 'Carlos', 'Silva', 'carlos.silva@ucu.edu.uy'),
(48927153, 'Sofía', 'Fernández', 'sofia.fernandez@ucu.edu.uy'),
(52349872, 'Martín', 'López', 'martin.lopez@ucu.edu.uy');

-- Tabla: participante_programa_académico
INSERT INTO participante_programa_academico (id_alumno_programa, ci_participante, nombre_programa, rol) VALUES
(1, 49382716, 'Ingeniería Informática', 'alumno'),
(2, 51293487, 'Administración de Empresas', 'alumno'),
(3, 47851239, 'Psicología Clínica', 'alumno'),
(4, 50128394, 'Ingeniería Informática', 'docente'),
(5, 48927153, 'MBA', 'alumno'),
(6, 52349872, 'Psicología Organizacional', 'docente');

-- Tabla: sala
INSERT INTO sala (nombre_sala, edificio, capacidad, tipo_sala) VALUES
('Lab A', 'Edificio de Ingeniería', 30, 'grado'),
('Sala 101', 'Edificio Central', 50, 'grado'),
('Aula Magna', 'Edificio Central', 100, 'libre'),
('Sala Posgrado 1', 'Campus Punta del Este', 25, 'posgrado'),
('Sala Docente 2', 'Edificio de Ingeniería', 10, 'docente');

-- Tabla: turno
INSERT INTO turno (id_turno, hora_inicio, hora_fin) VALUES
(1, '08:00', '10:00'),
(2, '10:00', '12:00'),
(3, '14:00', '16:00'),
(4, '16:00', '18:00');

-- Tabla: reserva
INSERT INTO reserva (id_reserva, nombre_sala, edificio, fecha, id_turno, estado) VALUES
(1, 'Lab A', 'Edificio de Ingeniería', '2025-09-01', 1, 'activa'),
(2, 'Sala 101', 'Edificio Central', '2025-09-01', 2, 'cancelada'),
(3, 'Aula Magna', 'Edificio Central', '2025-09-02', 3, 'finalizada'),
(4, 'Sala Posgrado 1', 'Campus Punta del Este', '2025-09-02', 1, 'activa'),
(5, 'Lab A', 'Edificio de Ingeniería', '2025-09-03', 2, 'sin asistencia'),
(6, 'Sala Docente 2', 'Edificio de Ingeniería', '2025-09-04', 3, 'finalizada'),
(7, 'Sala 101', 'Edificio Central', '2025-09-05', 4, 'activa');

-- Tabla: reserva_participante
INSERT INTO reserva_participante (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia) VALUES
(49382716, 1, '2025-08-28', true),
(51293487, 2, '2025-08-28', false),
(47851239, 3, '2025-08-29', true),
(50128394, 1, '2025-08-30', true),
(48927153, 4, '2025-08-31', true),
(52349872, 6, '2025-08-31', true),
(49382716, 5, '2025-09-01', false),
(51293487, 7, '2025-09-02', true);

-- Tabla: sancion_participante
INSERT INTO sancion_participante (ci_participante, fecha_inicio, fecha_fin) VALUES
(51293487, '2025-09-05', '2025-09-15'),
(49382716, '2025-09-10', '2025-09-20'),
(52349872, '2025-09-08', '2025-09-18');


-- Tabla: invitados
INSERT INTO invitados(ci_invitado,responsable_ci,nombre_invitado,apellido_invitado,email,fecha,hora_inicio,hora_fin) VALUES 
(43459814,50128394,'Julian','Perez','julian.perez@gmail.com','2025-09-01','08:00','9:00'),
(56784229,51293487,'Ana','Gonzalez','ana.gonzalez@gmail.com','2025-09-05','11:00','12:00'),
(93245881,48927153,'Juliana','Mendez','juliana.mendez@gmail.com','2025-09-02','08:00','09:00');
