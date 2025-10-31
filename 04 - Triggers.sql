USE ObligatorioBD1;
DELIMITER //

#Sólo es posible reservar las salas por bloques de hora, dentro del rango 08:00 hasta 23:00.
create trigger horario_correcto_insert
    before insert on turno
    for each row
    begin
        -- Verificar la coherencia horaria
        if new.hora_inicio >= new.hora_fin then
            signal sqlstate '45000'
            set message_text = 'La hora de inicio debe ser menor que la hora de fin.';
        end if;

        -- Verificar que ambas estén dentro del rango permitido y que sea la hora exacta
        if new.hora_inicio not in ('08:00:00', '09:00:00', '10:00:00', '11:00:00', '12:00:00', '13:00:00', '14:00:00', '15:00:00',
                              '16:00:00', '17:00:00', '18:00:00', '19:00:00', '20:00:00', '21:00:00', '22:00:00')
               or new.hora_fin not in ('09:00:00', '10:00:00', '11:00:00', '12:00:00', '13:00:00', '14:00:00', '15:00:00',
                                    '16:00:00', '17:00:00', '18:00:00', '19:00:00', '20:00:00', '21:00:00', '22:00:00', '23:00:00')  then
            signal sqlstate '45000'
            set message_text = 'La horas deben estar dentro del rango 08:00 - 23:00hs y deben ser exactas.';
        end if;
    end;
//

create trigger horario_correcto_update
    before update on turno
    for each row
begin
    -- Verificar la coherencia horaria
    if new.hora_inicio >= new.hora_fin then
        signal sqlstate '45000'
            set message_text = 'La hora de inicio debe ser menor que la hora de fin.';
    end if;

    -- Verificar que ambas estén dentro del rango permitido y que sea la hora exacta
    if new.hora_inicio not in ('08:00:00', '09:00:00', '10:00:00', '11:00:00', '12:00:00', '13:00:00', '14:00:00', '15:00:00',
                               '16:00:00', '17:00:00', '18:00:00', '19:00:00', '20:00:00', '21:00:00', '22:00:00')
        or new.hora_fin not in ('09:00:00', '10:00:00', '11:00:00', '12:00:00', '13:00:00', '14:00:00', '15:00:00',
                                '16:00:00', '17:00:00', '18:00:00', '19:00:00', '20:00:00', '21:00:00', '22:00:00', '23:00:00')  then
        signal sqlstate '45000'
            set message_text = 'La horas deben estar dentro del rango 08:00 - 23:00hs y deben ser exactas.';
    end if;
end;
//

