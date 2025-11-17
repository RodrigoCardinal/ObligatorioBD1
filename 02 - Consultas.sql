USE ObligatorioBD1;

#Salas más reservadas
select nombre_sala, count(*) as total
from reserva
group by nombre_sala
having count(*) = (select max(CantReservas) from (select count(*) as CantReservas
                                                  from reserva
                                                  group by nombre_sala) sub);

#Turnos más demandados
select t.hora_inicio, t.hora_fin, count(*) as total
from turno t
join reserva r on t.id_turno = r.id_turno
group by t.id_turno, t.hora_inicio, t.hora_fin
having count(*) = (select max(CantReservas) from (select count(*) as CantReservas
                                                  from reserva
                                                  group by id_turno)sub);

#Promedio de participantes por sala
select s.nombre_sala, avg(sub.cantParticipantes) as promedio
from (SELECT r.nombre_sala, COUNT(rp.ci_participante) AS CantParticipantes
      FROM reserva r
      join reserva_participante rp on r.id_reserva = rp.id_reserva
      GROUP BY r.nombre_sala)sub
join sala s on sub.nombre_sala = s.nombre_sala
group by s.nombre_sala;

#Cantidad de reservas por carrera y facultad
select f.nombre as facultad, pa.nombre_programa as carrera, count(r.id_reserva) as total
from facultad f
left join programa_academico pa on pa.id_facultad = f.id_facultad
left join participante_programa_academico ppa on pa.nombre_programa = ppa.nombre_programa
left join reserva_participante rp on ppa.ci_participante = rp.ci_participante
left join reserva r on r.id_reserva = rp.id_reserva
group by f.nombre, pa.nombre_programa
order by facultad;

#Porcentaje de ocupación de salas por edificio
SELECT e.nombre_edificio as nombre_sala, COUNT(r.id_reserva) / SUM(s.capacidad) * 100.00  AS ocupacion
FROM edificio e
JOIN sala s ON e.nombre_edificio = s.edificio
JOIN reserva r ON r.nombre_sala = s.nombre_sala
GROUP BY e.nombre_edificio
ORDER BY ocupacion DESC;

#Cantidad de reservas y asistencias de profesores y alumnos (grado y posgrado)
select DISTINCT ppa.rol,
            count(rp.id_reserva) as CantReservas, count(if(rp.asistencia = True, 1, null)) as CantAsistencias
from participante_programa_academico ppa
join reserva_participante rp on ppa.ci_participante = rp.ci_participante
group by ppa.rol;

#Cantidad de sanciones para profesores y alumnos (grado y posgrado)
select ppa.rol, count(DISTINCT sp.ci_participante) as CantSanciones
from participante_programa_academico ppa
join reserva_participante rp on ppa.ci_participante = rp.ci_participante
join sancion_participante sp on rp.ci_participante = sp.ci_participante
group by ppa.rol;

#Porcentaje de reservas efectivamente utilizadas vs. canceladas/no asistidas
SELECT
    IF(estado IN ('activa', 'finalizada'), 'Utilizadas', 'No utilizadas') AS estado,
    COUNT(*) / (SELECT COUNT(*) FROM reserva) * 100 AS total
FROM reserva
GROUP BY estado;

#Reservas por turno
select t.hora_inicio, t.hora_fin, count(r.id_reserva) as total
from turno t
left join reserva r on t.id_turno = r.id_turno
group by t.hora_inicio, t.hora_fin
order by t.hora_inicio;

#Reservas realizadas en un semestre específico (segundo semestre de 2025)
select *
from reserva
where fecha between '2025-08-12' and '2025-12-05';

#Participantes con sanciones
SELECT p.nombre, p.apellido, p.ci, 
        COUNT(*) as CantSanciones,
        MIN(sp.fecha_inicio) as fecha_inicio, 
        MAX(sp.fecha_fin) as fecha_fin
FROM participante p
JOIN sancion_participante sp ON sp.ci_participante = p.ci
GROUP BY p.nombre, p.apellido, p.ci
ORDER BY p.apellido, p.nombre;
