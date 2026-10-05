import paramiko
import sys
import datetime
import pymysql

# Adresse du serveur MariaDB (toujours le même, quel que soit le serveur mesuré)
mariadb = "192.168.112.111"


def ressourceTaking(ipAdress):

    # Connexion SSH au serveur à mesurer
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ipAdress, username="monitor", key_filename="/home/client/.ssh/id_rsa")

    # CPU avec vmstat : utilisation = 100 - id
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
    print("Taux d'utilisation de la mémoire :", preRam, "%")
    print("Taux d'utilisation du disque :", perDisk, "%")
    print("Taux d'utilisation CPU :", perCpu, "%")

    dateHour = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')

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

            # On ne garde que les mesures des dernières 72h
            cursor.execute("DELETE FROM ResSys WHERE date_hour < NOW() - INTERVAL 72 HOUR;")

        connection.commit()


# argv[0] nom du script, les arguments suivants sont les serveurs à mesurer
listServers = sys.argv[1:]

for server in listServers:
    ressourceTaking(server)
