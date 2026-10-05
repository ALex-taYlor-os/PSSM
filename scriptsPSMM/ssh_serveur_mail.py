import paramiko
import sys
import os
import pymysql
import subprocess

# argv[0] nom du script
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, username=username, key_filename=key_filename)
#pour rentrer le mot de passe en interactif


connection = pymysql.connect(
    host=hostname,
    user="client",
    password="clientpass",
    database=None,
    cursorclass=pymysql.cursors.DictCursor,
)

with connection:
#connection.commit()
    with connection.cursor() as cursor:
        # Creation de la base si non présente
        sql = "USE PSMM; "
        cursor.execute(sql)
        # ajout des données pour chaque lignes trouvées
         #On enlève le : pour que le l'heure et supprimer la  virgule
        # print("Ajout de "+acc_name)
        sql = """SELECT * FROM logsTable 
        WHERE DATE(date_hour) >= DATE_SUB(CURDATE(), INTERVAL  DAY) AND DATE(date_hour) < CURDATE() ;    """
        cursor.execute(sql)
        listLogs=cursor.fetchall() 
        #print(type(listLogs))
        listToSend=[]
        for log in listLogs:
         listToSend.append("Connexion échouée sur le serveur : "+log["application"]+". Le "+log["date_hour"]+" avec le compte : "+log["name_account"]+"  avec l'adresse IP :  "+log["IP_adress"]+".")

        print(listToSend)

corpsmes="\n".join(listToSend)

message = "Subject: Dump de Logs\n\n" + corpsmes

result = subprocess.run(["msmtp", "alex.taylor@laplateforme.io"], input=message, text=True, capture_output=True)

print(result.stdout)


cursor.close()
client.close()
