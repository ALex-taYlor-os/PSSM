import paramiko
import sys
import os

# Job 04 : se connecter en SSH à un serveur et y lancer une commande en sudo.
# Utilisation : python3 ssh_login_sudo.py <ip_du_serveur>
# Le mot de passe sudo est lu dans la variable d'environnement PSSWD_PSMM.

# Adresse IP du serveur passée en argument (sys.argv[0] contient le nom du script)
host = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

# Connexion SSH avec la clé privée du compte monitor
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, key_filename=key_filename)

# Lancement de la commande en sudo
# get_pty=True simule un terminal pour que sudo puisse demander le mot de passe
_stdin, _stdout,_stderr = client.exec_command("sudo apt update", get_pty=True)

# Envoi du mot de passe sudo
_stdin.write(os.environ["PSSWD_PSMM"]+'\n') 
_stdin.flush()

# Affichage du résultat de la commande
print(_stdout.read().decode())

client.close()
