import paramiko
import sys
import os

# argv[0] nom du script
host = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, key_filename=key_filename)
#pour rentrer le mot de passe en interactif
_stdin, _stdout,_stderr = client.exec_command("sudo apt update", get_pty=True)
#utilisation de la variable d'environnement avec le mot de passe sudo pour les vm 
_stdin.write(os.environ["PSSWD_PSMM"]+'\n') 
_stdin.flush()
print(_stdout.read().decode())

client.close()
