import paramiko
import sys
import os
import pymysql

#argv[0] nom du script
hostname = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"
try:
     client = paramiko.client.SSHClient()
     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
     client.connect(hostname, username=username, key_filename=key_filename)
except:
     print("Erreur de connexion...")
     sys.exit(1)


#pour rentrer le mot de passe en interactif
     _stdin, _stdout,_stderr = client.exec_command("whoami && ip a ", get_pty=True)
#utilisation de la variable d'environnement avec le mot de passe sudo pour les vm 
#_stdin.write(os.environ["PSSWD_PSMM"])
     _stdin.flush()
     print(_stdout.read().decode())

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
