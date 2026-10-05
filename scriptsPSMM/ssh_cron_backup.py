import paramiko
import sys
import os
import pymysql
import subprocess
import datetime
import time
import shlex

# Job 10 : sauvegarde locale et horodatée de la table logsTable, avec
# conservation des 7 dernières sauvegardes. Lancé par cron toutes les 3h.
# Utilisation : python3 ssh_cron_backup.py <ip_du_serveur_mariadb>


# Adresse IP du serveur passée en argument (sys.argv[0] contient le nom du script)
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

# Connexion SSH avec la clé privée du compte monitor
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, username=username, key_filename=key_filename)

# Date et heure de la sauvegarde, utilisées dans le nom du fichier
dateHour=datetime.datetime.today().strftime('%Y-%m-%d_%H-%M-%S')

print(dateHour)

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
        # Sélection de la base PSMM
        sql = "USE PSMM; "
        cursor.execute(sql)

        # Récupération de toutes les lignes de la table logsTable
        sql = """SELECT * FROM logsTable;"""
        cursor.execute(sql)
        listLogs=cursor.fetchall() 


# Contenu de la sauvegarde : une ligne de la table par ligne de texte
backupFormated="\n".join(str(log) for log in listLogs)

# Dossier des sauvegardes (chemin absolu, car cron ne lance pas le script depuis ce dossier)
dir = "/home/client/scriptsPSMM/backup"


# --- Rotation : s'il y a déjà 7 sauvegardes, on supprime la plus ancienne ---

numFiles=len(os.listdir(dir))

# Point de départ : l'heure actuelle, forcément plus récente que tous les fichiers
minDateCreation=time.time()


if numFiles == 7:
    for path in os.listdir(dir):
     # Chemin complet du fichier (dossier + nom)
     myPath=os.path.join(dir, path)
     # On ignore les éventuels sous-dossiers
     if os.path.isfile(myPath):
         # On garde le fichier dont la date de modification est la plus ancienne
         if os.path.getmtime(myPath)<minDateCreation:   
             minDateCreation=os.path.getmtime(myPath)
             minName=myPath
    # Suppression de la sauvegarde la plus ancienne
    res = subprocess.run(f'rm '+minName, shell=True)


# --- Création de la nouvelle sauvegarde ---

message=backupFormated

file_name =dir+'/backup_'+dateHour+".txt"

# Écriture du contenu dans le fichier ; shlex.quote protège les apostrophes
# et caractères spéciaux pour le shell
res = subprocess.run(f'echo {shlex.quote(message)} >> {shlex.quote(file_name)}', shell=True)


print(res.stdout)

cursor.close()
client.close()
