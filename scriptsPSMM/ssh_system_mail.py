import paramiko
import sys
from datetime import datetime
import pymysql
import subprocess

# Jobs 12 et 13 : relever l'utilisation CPU, RAM et disque de chaque serveur,
# l'enregistrer dans la table ResSys, et envoyer un mail à l'administrateur
# si un seuil est dépassé, sans dépasser un mail par heure.
# Lancé par cron toutes les 5 minutes.
# Utilisation : python3 ssh_system_mail.py <ip_serveur_1> <ip_serveur_2> ...


# Adresse du serveur MariaDB (toujours la même, quel que soit le serveur mesuré)
mariadb = "192.168.112.111"

# Passe à True dès qu'une alerte est détectée sur un des serveurs
send=False
# Messages d'alerte, tous serveurs confondus, envoyés dans un seul mail
listAlert=[]

# Seuils d'alerte en pourcentage, modifiables ici
threshCPU=86
threshDisk=98
threshRAM=96



def IsMoreThanOneHour():
    # Renvoie True si le dernier mail date de plus d'une heure (ou si aucun
    # mail n'a encore été envoyé), et enregistre alors l'heure actuelle
    # comme heure du dernier envoi dans lastSent.txt
    try:
        with open('lastSent.txt', 'r', encoding='utf-8') as f:
            lastdate=datetime.strptime(f.read().strip(), "%d/%m/%Y %H:%M:%S")
    except FileNotFoundError:
        return True

    actualHour=datetime.now()
    if ((actualHour - lastdate).total_seconds() > 3600):
       with open('lastSent.txt', 'w', encoding='utf-8') as f:
            f.write(actualHour.strftime("%d/%m/%Y %H:%M:%S"))
       return True
    else:
        return False


def send_mail(myList):
    # Envoi du mail d'alerte avec msmtp : une alerte par ligne
    corpsmes="\n".join(myList)
    message = "Subject: Alerte utilisation\n\n" + corpsmes
    result = subprocess.run(["msmtp", "alex.taylor@laplateforme.io"], input=message, text=True, capture_output=True)


def ressourceTaking(ipAdress):
    # send est modifiée dans la fonction : il faut indiquer qu'on parle de la variable globale
    global send

    # Connexion SSH au serveur à mesurer
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ipAdress, username="monitor", key_filename="/home/client/.ssh/id_rsa")

    # --- CPU avec vmstat ---
    # Deux mesures à 1 seconde d'intervalle : la dernière ligne porte sur la dernière seconde.
    # La colonne "id" est le pourcentage d'inactivité, donc utilisation = 100 - id
    _stdin, _stdout, _stderr = client.exec_command("vmstat 1 2")
    resultcpu = _stdout.read().decode().splitlines()
    header = resultcpu[1].split()
    values = resultcpu[-1].split()
    perCpu = 100 - int(values[header.index("id")])

    # --- Mémoire avec free -h ---
    # resultmem[1] est la ligne "Mem:" : total, utilisé, libre, partagé, tampon/cache, disponible
    _stdin, _stdout, _stderr = client.exec_command("free -h")
    resultmem = _stdout.read().decode().splitlines()

    # Affichage de contrôle (colonne « partagé »)
    precalcul = resultmem[1].split()[4]
    print(precalcul)

    # Mémoire utilisée (colonne « utilisé »), ramenée en Gi si elle est affichée en Mi
    if "Mi" in resultmem[1].split()[2]:
        numerator = 0.001 * int(float(resultmem[1].split()[2].replace("Mi", "").replace(",", ".")))
    else:
        numerator = int(float(resultmem[1].split()[2].replace("Gi", "").replace(",", ".")))

    # Mémoire totale (colonne « total »), ramenée en Gi si elle est affichée en Mi
    if "Mi" in resultmem[1].split()[1]:
        denominatorRam = 0.001 * float(resultmem[1].split()[1].replace("Mi", "").replace(",", "."))
    else:
        denominatorRam = float(resultmem[1].split()[1].replace("Gi", "").replace(",", "."))

    # Pourcentage d'utilisation de la RAM, arrondi à 2 chiffres après la virgule
    preRam = (numerator * 100) / denominatorRam
    preRam = round(preRam, 2)

    # --- Disque avec df sur la racine : colonne Uti% ---
    _stdin, _stdout, _stderr = client.exec_command("df -h /")
    resultdisk = _stdout.read().decode().splitlines()
    perDisk = int(resultdisk[-1].split()[4].replace("%", ""))

    client.close()

    print("Serveur :", ipAdress)
    print("Taux d'utilisation de la mémoire :", str(preRam), "%")
    print("Taux d'utilisation du disque :", str(perDisk), "%")
    print("Taux d'utilisation CPU :", str(perCpu), "%")

    # Date et heure de la mesure, au format reconnu par MariaDB
    dateHour = datetime.today().strftime('%Y-%m-%d %H:%M:%S')


    # --- Vérification des seuils ---
    # Version de test : ce sont les seuils eux-mêmes qui sont comparés, pour
    # forcer l'envoi d'alertes. À remplacer par les mesures une fois les tests
    # terminés (par exemple : if preRam > threshRAM:)
    if threshRAM > 80:
        listAlert.append('le taux d\'utilisation RAM dépasse '+str(threshRAM)+'% pour le serveur : '+ipAdress)
        send=True
    if threshDisk > 90:
        listAlert.append('le taux d\'utilisation RAM dépasse '+str(threshDisk)+'%  pour le serveur : '+ipAdress)
        send = True
    if threshCPU > 70:
        listAlert.append('le taux d\'utilisation RAM dépasse '+str(threshCPU)+'% pour le serveur : '+ipAdress)
        send=True

    # --- Enregistrement dans la base ---
    connection = pymysql.connect(
        host=mariadb,
        user="client",
        password="clientpass",
        database=None,
        cursorclass=pymysql.cursors.DictCursor,
    )

    with connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS PSMM;")
            cursor.execute("USE PSMM;")

            # Table des mesures, créée si elle n'existe pas
            cursor.execute("""CREATE TABLE IF NOT EXISTS ResSys (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Ip_Adress VARCHAR(100),
                date_hour VARCHAR(100),
                Memory VARCHAR(10),
                CPU VARCHAR(10),
                Disk VARCHAR(10));""")

            # Ajout de la nouvelle mesure
            sql = """INSERT INTO ResSys (Ip_Adress, date_hour, Memory, CPU, Disk)
                     VALUES (%s, %s, %s, %s, %s);"""
            cursor.execute(sql, (ipAdress, dateHour, preRam, perCpu, perDisk))

            # Suppression des mesures de plus de 72h
            cursor.execute("DELETE FROM ResSys WHERE date_hour < NOW() - INTERVAL 72 HOUR;")

        connection.commit()


# Liste des serveurs à mesurer : tous les arguments après le nom du script
listServers = sys.argv[1:]

for server in listServers:
    ressourceTaking(server)

# Envoi d'un seul mail regroupant toutes les alertes, au maximum une fois par heure
if send:
   if (IsMoreThanOneHour()):
        send_mail(listAlert)
