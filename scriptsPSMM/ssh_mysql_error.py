import paramiko
import sys
import os
import pymysql
import re

# Job 06 : récupérer dans les logs de MariaDB les tentatives de connexion
# avec un compte ou un mot de passe incorrect, et les enregistrer dans la
# table logsTable de la base PSMM.
# Utilisation : python3 ssh_mysql_error.py <ip_du_serveur_mariadb>
# Le mot de passe sudo est lu dans la variable d'environnement PSSWD_PSMM.

# Adresse IP du serveur passée en argument (sys.argv[0] contient le nom du script)
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

# Connexion SSH avec la clé privée du compte monitor
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, username=username, key_filename=key_filename)


# Connexion à la base MariaDB
connection = pymysql.connect(
    host=hostname,
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


        # Lecture du log d'erreurs de MariaDB en sudo, en ne gardant que les
        # lignes "Access denied for user"
        # get_pty=True simule un terminal pour que sudo puisse demander le mot de passe
        _stdin, _stdout,_stderr = client.exec_command("sudo cat /var/log/mysql/error.log | grep -e \"Access denied for user\" " , get_pty=True)
        # Envoi du mot de passe sudo
        _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
        _stdin.flush()

        # Traitement de chaque ligne du log
        for line in iter(_stdout.readline,"") :
            if "Access denied" in line:

                # Exemple de ligne :
                # 2026-09-28 14:03:03 5 [Warning] Access denied for user 'monitor'@'localhost' (using password: YES)
                # Le nom du compte est entre la 1re paire d'apostrophes
                acc_name=line.split("'")[1]
                # Date et heure : les deux premiers mots de la ligne
                dateHour=line.split()[0]+" "+line.split()[1]

                # Adresse IP (ou nom de machine) : entre la 2e paire d'apostrophes
                ipAdress=line.split("'")[3]
                print("Ajout de "+acc_name)

                # Insertion de la tentative, seulement si aucune ligne n'a déjà
                # cette date/heure (évite les doublons à chaque exécution)
                sql = """ INSERT INTO logsTable ( application, date_hour,name_account,IP_adress)
                SELECT 'mariadb', %s, %s, %s
                FROM DUAL
                WHERE NOT EXISTS (
                SELECT 1 FROM logsTable
                WHERE date_hour = %s
                );    """
                cursor.execute(sql,(dateHour,acc_name,ipAdress,dateHour))
                connection.commit()
cursor.close()
client.close()
