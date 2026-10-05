import paramiko
import sys
import os
import pymysql
import subprocess

# Job 09 : envoyer par mail à l'administrateur l'historique des tentatives
# de connexion échouées de la veille, enregistrées dans la table logsTable.
# Utilisation : python3 ssh_serveur_mail.py <ip_du_serveur_mariadb>

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
        # Sélection de la base PSMM
        sql = "USE PSMM; "
        cursor.execute(sql)

        # Récupération des tentatives de la veille (de minuit à minuit)
        sql = """SELECT * FROM logsTable 
        WHERE DATE(date_hour) >= DATE_SUB(CURDATE(), INTERVAL  DAY) AND DATE(date_hour) < CURDATE() ;    """
        cursor.execute(sql)
        listLogs=cursor.fetchall() 

        # Une phrase lisible par tentative de connexion
        listToSend=[]
        for log in listLogs:
         listToSend.append("Connexion échouée sur le serveur : "+log["application"]+". Le "+log["date_hour"]+" avec le compte : "+log["name_account"]+"  avec l'adresse IP :  "+log["IP_adress"]+".")

        print(listToSend)

# Corps du mail : une tentative par ligne
corpsmes="\n".join(listToSend)

# En-tête Subject, ligne vide obligatoire, puis le corps du message
message = "Subject: Dump de Logs\n\n" + corpsmes

# Envoi du mail avec msmtp
result = subprocess.run(["msmtp", "alex.taylor@laplateforme.io"], input=message, text=True, capture_output=True)

print(result.stdout)


cursor.close()
client.close()
