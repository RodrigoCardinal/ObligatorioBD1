#import mysql.connector

#Establecer conexión
#cnx = mysql.connector.connect(user='root', password='root', host='127.0.0.1',
 #                             database='ObligatorioBD1')





import mysql.connector

def get_admin_connection():
    return mysql.connector.connect(
        user='admin_user',
        password='administrador',
        host='127.0.0.1',
        database='ObligatorioBD1'
    )

def get_user_connection():
    return mysql.connector.connect(
        user='user',
        password='usuario',
        host='127.0.0.1',
        database='ObligatorioBD1'
    )