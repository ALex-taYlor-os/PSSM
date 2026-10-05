import paramiko
import sys
from datetime import datetime
import pymysql
import subprocess


# Adresse du serveur MariaDB (toujours le même, quel que soit le serveur mesuré)
mariadb = "192.168.112.111"

send=False
listAlert=[]
threshCPU=86
threshDisk=98
threshRAM=96



def IsMoreThanOneHour():
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
    corpsmes="\n".join(myList)
    message = "Subject: Alerte utilisation\n\n" + corpsmes
    result = subprocess.run(["msmtp", "alex.taylor@laplateforme.io"], input=message, text=True, capture_output=True)


def ressourceTaking(ipAdress):
    global send
    # Connexion SSH au serveur à mesurer
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ipAdress, username="monitor", key_filename="/home/client/.ssh/id_rsa")

    # CPU avec vmstat 
    _stdin, _stdout, _stderr = client.exec_command("vmstat 1 2")
    resultcpu = _stdout.read().decode().splitlines()
    header = resultcpu[1].split()
    values = resultcpu[-1].split()
    perCpu = 100 - int(values[header.index("id")])

    # Mémoire avec free -h
    _stdin, _stdout, _stderr = client.exec_command("free -h")
    resultmem = _stdout.read().decode().splitlines()

    precalcul = resultmem[1].split()[4]
    print(precalcul)
    # Pour savoir le taux d'utilisation de la mémoire

    if "Mi" in resultmem[1].split()[2]:
        numerator = 0.001 * int(float(resultmem[1].split()[2].replace("Mi", "").replace(",", ".")))
    else:
        numerator = int(float(resultmem[1].split()[2].replace("Gi", "").replace(",", ".")))

    if "Mi" in resultmem[1].split()[1]:
        denominatorRam = 0.001 * float(resultmem[1].split()[1].replace("Mi", "").replace(",", "."))
    else:
        denominatorRam = float(resultmem[1].split()[1].replace("Gi", "").replace(",", "."))

    preRam = (numerator * 100) / denominatorRam

    # On précise 2 chiffres après la virgule
    preRam = round(preRam, 2)

    # Disque avec df : colonne Uti%
    _stdin, _stdout, _stderr = client.exec_command("df -h /")
    resultdisk = _stdout.read().decode().splitlines()
    perDisk = int(resultdisk[-1].split()[4].replace("%", ""))

    client.close()

    print("Serveur :", ipAdress)
    print("Taux d'utilisation de la mémoire :", str(preRam), "%")
    print("Taux d'utilisation du disque :", str(perDisk), "%")
    print("Taux d'utilisation CPU :", str(perCpu), "%")

    dateHour = datetime.today().strftime('%Y-%m-%d %H:%M:%S')


   #Test pour mes valeurs d'utilisation
    if threshRAM > 80:
        listAlert.append('le taux d\'utilisation RAM dépasse '+str(threshRAM)+'% pour le serveur : '+ipAdress)
        send=True
    if threshDisk > 90:
        listAlert.append('le taux d\'utilisation RAM dépasse '+str(threshDisk)+'%  pour le serveur : '+ipAdress)
        send = True
    if threshCPU > 70:
        listAlert.append('le taux d\'utilisation RAM dépasse '+str(threshCPU)+'% pour le serveur : '+ipAdress)
        send=True
   # Enregistrement dans la base
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

            cursor.execute("""CREATE TABLE IF NOT EXISTS ResSys (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                Ip_Adress VARCHAR(100),
                date_hour VARCHAR(100),
                Memory VARCHAR(10),
                CPU VARCHAR(10),
                Disk VARCHAR(10));""")

            sql = """INSERT INTO ResSys (Ip_Adress, date_hour, Memory, CPU, Disk)
                     VALUES (%s, %s, %s, %s, %s);"""
            cursor.execute(sql, (ipAdress, dateHour, preRam, perCpu, perDisk))

            # Garde que les mesures des dernières 72h
            cursor.execute("DELETE FROM ResSys WHERE date_hour < NOW() - INTERVAL 72 HOUR;")

        connection.commit()


# argv[0] nom du script, les arguments suivants sont les serveurs à mesurer
listServers = sys.argv[1:]

for server in listServers:
    ressourceTaking(server)

if send:
   if (IsMoreThanOneHour()):
        send_mail(listAlert)
