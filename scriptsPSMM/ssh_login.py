import paramiko
import sys

# Job 03 : se connecter en SSH à un serveur et y lancer une commande shell (df).
# Utilisation : python3 ssh_login.py <ip_du_serveur>

# Adresse IP du serveur passée en argument (sys.argv[0] contient le nom du script)
host = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

# Connexion SSH avec la clé privée du compte monitor
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, key_filename=key_filename)

# Exécution de la commande df et affichage du résultat
_stdin, _stdout,_stderr = client.exec_command("df")
print(_stdout.read().decode())
client.close()
