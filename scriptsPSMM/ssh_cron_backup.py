import paramiko
import sys
import os
import pymysql
import subprocess
import datetime
import time
import shlex



# argv[0] nom du script
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, username=username, key_filename=key_filename)
#pour rentrer le mot de passe en interactif

dateHour=datetime.datetime.today().strftime('%Y-%m-%d_%H-%M-%S')

print(dateHour)

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
        sql = """SELECT * FROM logsTable;"""
        cursor.execute(sql)
        listLogs=cursor.fetchall() 
        #print(type(listLogs))


backupFormated="\n".join(str(log) for log in listLogs)

dir = "/home/client/scriptsPSMM/backup"


numFiles=len(os.listdir(dir))

minDateCreation=time.time()


if numFiles == 7:
    for path in os.listdir(dir):
     myPath=os.path.join(dir, path)
#Concatene pour savoir si le fichier dans le dossier est bien un fichier et pas un dossier
     if os.path.isfile(myPath):
#On regarde  quelle sont les dates de production les plus anciennes
         if os.path.getmtime(myPath)<minDateCreation:   
             minDateCreation=os.path.getmtime(myPath)
             minName=myPath
    res = subprocess.run(f'rm '+minName, shell=True)



#print(os.path.basename(path))
 #       print(datecreation)
message=backupFormated

file_name =dir+'/backup_'+dateHour+".txt"

res = subprocess.run(f'echo {shlex.quote(message)} >> {shlex.quote(file_name)}', shell=True)


print(res.stdout)

cursor.close()
client.close()
