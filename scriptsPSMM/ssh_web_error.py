import paramiko
import sys
import os
import pymysql
import re

# argv[0] nom du script
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, username=username, key_filename=key_filename)
#pour rentrer le mot de passe en interactif


connection = pymysql.connect(
    host="192.168.112.111",
    user="client",
    password="clientpass",
    database=None,
    cursorclass=pymysql.cursors.DictCursor,
)

with connection:
#connection.commit()
    with connection.cursor() as cursor:
        # Creation de la base si non présente
        sql = "CREATE DATABASE IF NOT EXISTS PSMM; "
        cursor.execute(sql)


        # Se déplacer dans la base
        sql = "USE PSMM;"
        cursor.execute(sql)


        # Créer une  table si elle n'existe pas 
        sql =  """ CREATE TABLE IF NOT EXISTS logsTable (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        application VARCHAR(100),
        date_hour VARCHAR(100),
        name_account VARCHAR(100),
        IP_adress VARCHAR(20));  """
        cursor.execute(sql)


        # ajout des données pour chaque lignes trouvées


        _stdin, _stdout,_stderr = client.exec_command("sudo cat /var/log/nginx/error.log | grep -e \"*1 user\" " , get_pty=True)
	#utilisation de la variable d'environnement avec le mot de passe sudo pour les vm 
        _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
        _stdin.flush()

        #print(_stdout.read().decode()) 

        for line in iter(_stdout.readline,"") :
            if "*1 user" in line:

                acc_name=line.split(" ")[6]
          #On enlève le : pour le nom du compte
                acc_name=acc_name.replace('"',"")
                print(acc_name)
                date=line.split(" ")[0]
                date=date.replace("/","-")
                hour=line.split(" ")[1]
          #On coupe pour avoir que le l'heure et supprimer la  virgule
                hour=hour[:8]
                print(hour[:8])

                dateHour=date+" "+hour
                print(dateHour)
                ipAdress=line.split(" ")[13]
                ipAdress=ipAdress.replace(",","")
               # print("Ajout de "+acc_name)
                sql = """ INSERT INTO logsTable ( application, date_hour,name_account,IP_adress)
                SELECT 'web', %s, %s, %s
                FROM DUAL
                WHERE NOT EXISTS (
                SELECT 1 FROM logsTable
                WHERE date_hour = %s AND application='web'
                );    """
                cursor.execute(sql,(dateHour,acc_name,ipAdress,dateHour))
                connection.commit()
cursor.close()
client.close()
