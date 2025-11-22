-- la idea de este archivo es que el estado de la reserva se cambie automaticamente de activa a finalizada,
-- si los participantes asistieron (o sea, no se marcó como 'sin asistencia'), y si la fecha de la reserva ya pasó
CREATE DEFINER = `root`@`localhost` EVENT actualizar_estados_reservas
    ON SCHEDULE EVERY 1 HOUR
        STARTS '2025-11-19 15:05:57'
    DO
    UPDATE reserva AS r
        JOIN turno AS t ON r.id_turno = t.id_turno
    SET r.estado = 'finalizada'
    WHERE TIMESTAMP(r.fecha, t.hora_fin) < NOW()
      AND r.estado = 'activa';