import paramiko
import sys
import os
import pymysql

# Job 05 : vérifier l'accès au serveur MariaDB/MySQL.
# Utilisation : python3 ssh_mysql.py <ip_du_serveur_mariadb>

# Adresse IP du serveur passée en argument (sys.argv[0] contient le nom du script)
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

# Connexion SSH au serveur ; le script s'arrête si elle échoue
try:
     client = paramiko.client.SSHClient()
     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
     client.connect(hostname, username=username, key_filename=key_filename)
except:
     print("Erreur de connexion...")
     sys.exit(1)


     # Affichage de l'utilisateur connecté et des adresses IP du serveur
     _stdin, _stdout,_stderr = client.exec_command("whoami && ip a ", get_pty=True)
     _stdin.flush()
     print(_stdout.read().decode())

# Connexion à la base MariaDB ; le script s'arrête si elle échoue
try:
   connection = pymysql.connect(
        host=hostname,
        user="client",
        password="clientpass",
        database=None,
        cursorclass=pymysql.cursors.DictCursor,
       )
except pymysql.Error as e:
     print("Erreur lors de l'établissement de la connexion à la base de donnée : ")
     print(e)
     sys.exit(1)



client.close()
