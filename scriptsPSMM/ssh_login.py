import paramiko
import sys



# argv[0] nom du script pour mettre l'adresse ip du serveur que l'on choisit
host = sys.argv[1]
username = "monitor"
key_filename="/home/client/.ssh/id_rsa"

#try:
client = paramiko.client.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=username, key_filename=key_filename)
_stdin, _stdout,_stderr = client.exec_command("df")
print(_stdout.read().decode())
client.close()
#except paramiko.AuthenticationException as error:
 #   print("ERROR")
