-- la idea de este archivo es que el estado de la reserva se cambie automaticamente de activa a finalizada,
-- si los participantes asistieron (o sea, no se marcó como 'sin asistencia'), y si la fecha de la reserva ya pasó
USE ObligatorioBD1;
SET GLOBAL event_scheduler = ON;

CREATE EVENT actualizar_estados_reservas
ON SCHEDULE EVERY 1 DAY
STARTS TIMESTAMP(CURRENT_DATE, '23:00:00')
DO
    UPDATE reserva
    SET estado = 'finalizada'
    WHERE fecha < NOW()
      AND estado = 'activa';