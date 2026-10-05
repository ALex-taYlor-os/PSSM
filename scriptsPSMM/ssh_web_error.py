import paramiko
import sys
import os
import pymysql
import re

# Job 08 : récupérer dans les logs de nginx les tentatives de connexion
# (authentification basic) avec un utilisateur inconnu, et les enregistrer
# dans la table logsTable de la base PSMM.
# Utilisation : python3 ssh_web_error.py <ip_du_serveur_web>
# Le mot de passe sudo est lu dans la variable d'environnement PSSWD_PSMM.

# Adresse IP du serveur Web passée en argument (sys.argv[0] contient le nom du script)
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

# Connexion SSH au serveur Web avec la clé privée du compte monitor
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, username=username, key_filename=key_filename)


# Connexion à la base, hébergée sur le serveur MariaDB
connection = pymysql.connect(
    host="192.168.112.111",
    user="client",
    password="clientpass",
    database=None,
    cursorclass=pymysql.cursors.DictCursor,
)

with connection:
    with connection.cursor() as cursor:
        # Création de la base PSMM si elle n'existe pas
        sql = "CREATE DATABASE IF NOT EXISTS PSMM; "
        cursor.execute(sql)


        # Sélection de la base PSMM
        sql = "USE PSMM;"
        cursor.execute(sql)


        # Création de la table des tentatives de connexion échouées si elle n'existe pas
        sql =  """ CREATE TABLE IF NOT EXISTS logsTable (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        application VARCHAR(100),
        date_hour VARCHAR(100),
        name_account VARCHAR(100),
        IP_adress VARCHAR(20));  """
        cursor.execute(sql)


        # Lecture du log d'erreurs de nginx en sudo, en ne gardant que les
        # lignes de tentatives avec un utilisateur inconnu
        # get_pty=True simule un terminal pour que sudo puisse demander le mot de passe
        _stdin, _stdout,_stderr = client.exec_command("sudo cat /var/log/nginx/error.log | grep -e \"*1 user\" " , get_pty=True)
        # Envoi du mot de passe sudo
        _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
        _stdin.flush()

        # Traitement de chaque ligne du log
        for line in iter(_stdout.readline,"") :
            if "*1 user" in line:

                # Exemple de ligne :
                # 2026/09/28 17:20:12 [error] 1234#1234: *1 user "rze" was not found in "/etc/nginx/.htpasswd", client: 192.168.112.1, ...

                # Nom du compte : 7e mot de la ligne, entre guillemets qu'on retire
                acc_name=line.split(" ")[6]
                acc_name=acc_name.replace('"',"")
                print(acc_name)

                # Date (1er mot), convertie de aaaa/mm/jj en aaaa-mm-jj
                date=line.split(" ")[0]
                date=date.replace("/","-")
                # Heure (2e mot), limitée au format hh:mm:ss
                hour=line.split(" ")[1]
                hour=hour[:8]
                print(hour[:8])

                dateHour=date+" "+hour
                print(dateHour)

                # Adresse IP du poste : 14e mot de la ligne, suivi d'une virgule qu'on retire
                ipAdress=line.split(" ")[13]
                ipAdress=ipAdress.replace(",","")

                # Insertion de la tentative, seulement si aucune tentative Web
                # n'a déjà cette date/heure (évite les doublons à chaque exécution)
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
