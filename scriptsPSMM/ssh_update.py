import paramiko
import sys
import os
import subprocess


def send_mail(ipAdress):
   corpsmes ="Redémarrage du serveur "+ipAdress+" est requis pour finir d'installer les mises à jour."
   message = "Subject: Un redémarrage du serveur est requis\n\n" + corpsmes
   result = subprocess.run(["msmtp", "alex.taylor@laplateforme.io"], input=message, text=True, capture_output=True)
   return


def updateServers(server):

    username = "monitor"
    key_filename="/home/client/.ssh/id_rsa"
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, username=username, key_filename=key_filename)


#----Se connecter au wifi de la plateforme


#pour rentrer le mot de passe en interactif
    _stdin, _stdout,_stderr = client.exec_command("sudo apt update -y", get_pty=True)
#utilisation de la variable d'environnement avec le mot de passe sudo pour les vm
    _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
    _stdin.flush()
    isUpdate=_stdout.read().decode()
    print(isUpdate)

    if "paquets peuvent être mis à jour" or " paquet peut être mis à jour " in isUpdate :
       print("continuer vers l'installation")
       _stdin, _stdout,_stderr = client.exec_command("sudo apt-get upgrade -y", get_pty=True)
       _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
       _stdin.flush()
       codeReturn= _stdout.channel.recv_exit_status()
       if codeReturn==0:
           print("Fin de l'installation.")
       #print(_stdout.read().decode())
       rebootRequired="/var/run/reboot-required"
       findFile = "if [ -f " + rebootRequired + " ]; then echo \"yes\"; else echo \"no\"; fi"
       _stdin, _stdout,_stderr = client.exec_command(findFile)
       if "yes" in _stdout.read().decode():
           send_mail(server)
       else:
           print("Les mises à jour ont été installées avec succès !")
#Partie pour se deconnecter du wifi de l'alcasar

    client.close()

# argv[0] nom du script
listServers= sys.argv[1:]
for server in listServers:
    updateServers(server)
