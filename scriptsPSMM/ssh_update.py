import paramiko
import sys
import os
import subprocess

# Job 14 : mettre à jour chaque serveur et prévenir l'administrateur par mail
# si un redémarrage est nécessaire après les mises à jour.
# Utilisation : python3 ssh_update.py <ip_serveur_1> <ip_serveur_2> ...
# Le mot de passe sudo est lu dans la variable d'environnement PSSWD_PSMM.


def send_mail(ipAdress):
   # Mail envoyé à l'administrateur quand un redémarrage est requis
   corpsmes ="Redémarrage du serveur "+ipAdress+" est requis pour finir d'installer les mises à jour."
   message = "Subject: Un redémarrage du serveur est requis\n\n" + corpsmes
   result = subprocess.run(["msmtp", "alex.taylor@laplateforme.io"], input=message, text=True, capture_output=True)
   return


def updateServers(server):

    # Connexion SSH au serveur à mettre à jour
    username = "monitor"
    key_filename="/home/client/.ssh/id_rsa"
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, username=username, key_filename=key_filename)


    # --- Connexion au portail ALCASAR pour accéder à Internet (à compléter) ---


    # Mise à jour de la liste des paquets disponibles
    # get_pty=True simule un terminal pour que sudo puisse demander le mot de passe
    _stdin, _stdout,_stderr = client.exec_command("sudo apt update -y", get_pty=True)
    # Envoi du mot de passe sudo
    _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
    _stdin.flush()
    isUpdate=_stdout.read().decode()
    print(isUpdate)

    # S'il y a des paquets à mettre à jour, on lance l'installation
    if "paquets peuvent être mis à jour" or " paquet peut être mis à jour " in isUpdate :
       print("continuer vers l'installation")
       _stdin, _stdout,_stderr = client.exec_command("sudo apt-get upgrade -y", get_pty=True)
       _stdin.write(os.environ["PSSWD_PSMM"]+'\n')
       _stdin.flush()

       # On attend la fin de l'installation avant de continuer
       # (sinon la fermeture de la connexion SSH interromprait apt)
       codeReturn= _stdout.channel.recv_exit_status()
       if codeReturn==0:
           print("Fin de l'installation.")

       # Debian crée ce fichier quand une mise à jour nécessite un redémarrage.
       # La vérification se fait sur le serveur lui-même, via SSH
       rebootRequired="/var/run/reboot-required"
       findFile = "if [ -f " + rebootRequired + " ]; then echo \"yes\"; else echo \"no\"; fi"
       _stdin, _stdout,_stderr = client.exec_command(findFile)
       if "yes" in _stdout.read().decode():
           send_mail(server)
       else:
           print("Les mises à jour ont été installées avec succès !")


    # --- Déconnexion du portail ALCASAR (à compléter) ---

    client.close()


# Liste des serveurs à mettre à jour : tous les arguments après le nom du script
listServers= sys.argv[1:]
for server in listServers:
    updateServers(server)
