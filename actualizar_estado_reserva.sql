-- la idea de este archivo es que el estado de la reserva se cambie automaticamente de activa a finalizada,
-- si los participantes asistieron (o sea, no se marcó como 'sin asistencia'), y si la fecha de la reserva ya pasó
USE ObligatorioBD1;
SET GLOBAL event_scheduler = ON;

CREATE EVENT IF NOT EXISTS actualizar_estados_reservas
    ON SCHEDULE EVERY 1 DAY
    DO
    UPDATE ObligatorioBD1.reserva
    SET estado = CASE
                     WHEN fecha < CURDATE() AND estado = 'activa' THEN 'finalizada'
                     ELSE estado
    END
    WHERE fecha < CURDATE();