# PSMM : Python, Shell, MariaDB, Mail

Projet La Plateforme : centralisation des protocoles de gestion d'erreurs.

L'objectif est de récupérer les logs des serveurs FTP, MariaDB et Web, d'archiver les tentatives d'accès avec un compte ou un mot de passe invalide dans une base SQL, de surveiller les ressources des serveurs, et de prévenir l'administrateur système par mail et sur Google Chat.

---

## Sommaire

1. [Architecture](#architecture)
2. [Paramétrage des VM](#paramétrage-des-vm)
3. [Installation de MariaDB](#installation-de-mariadb)
4. [Installation de ProFTPD](#installation-de-proftpd)
5. [Installation de nginx](#installation-de-nginx)
6. [Accès SSH par clé](#accès-ssh-par-clé)
7. [VM cliente : Python et envoi de mails](#vm-cliente--python-et-envoi-de-mails)
8. [Variables d'environnement](#variables-denvironnement)
9. [Les jobs et leurs scripts](#les-jobs-et-leurs-scripts)
10. [Base de données](#base-de-données)
11. [Planification avec cron](#planification-avec-cron)
12. [Sécurité](#sécurité)
13. [Pistes d'amélioration](#pistes-damélioration)

---

## Architecture

| VM | Rôle | Ressources |
|---|---|---|
| `groupe_ftp` | Serveur FTP (ProFTPD) | 1 Go RAM, 1 vCPU, 8 Go disque |
| `groupe_web` | Serveur Web (nginx + authentification basic) | 1 Go RAM, 1 vCPU, 8 Go disque |
| `groupe_mariadb` | Serveur de base de données (MariaDB), héberge la base `PSMM` | 2 Go RAM, 2 vCPU, 8 Go disque |
| VM cliente | Supervision : exécute tous les scripts Python | Debian sans interface graphique |

Toutes les VM sont sous Debian (Trixie). Sur les trois serveurs, la connexion SSH en root est interdite : seul le compte `monitor`, membre du groupe `sudo`, peut se connecter, et uniquement avec une clé SSH.

La VM cliente se connecte en SSH aux serveurs pour lire leurs logs et mesurer leurs ressources, puis enregistre les résultats dans la base `PSMM` du serveur MariaDB.

Les adresses IP utilisées dans les exemples (`192.168.112.x`) sont distribuées par le DHCP du réseau de la plateforme et peuvent changer. Vérifiez-les avec `ip a` sur chaque VM.

---

## Paramétrage des VM

Passer toutes les VM en mode **pont (bridge)** dans les paramètres réseau de VMware, pour qu'elles soient sur le réseau de la plateforme.

Une adresse en `169.254.x.x` signifie que la VM n'a pas obtenu d'adresse auprès du DHCP : vérifier le mode réseau de la VM, puis redémarrer le réseau avec `sudo systemctl restart networking`.

---

## Installation de MariaDB

Sur le serveur MariaDB, ajout du dépôt officiel et installation :

```bash
curl -LsS https://r.mariadb.com/downloads/mariadb_repo_setup | bash
apt update
apt install mariadb-server mariadb-client -y
```

Vérification de la version :

```bash
mariadb --version
apt policy mariadb-server
```

Lancement et démarrage automatique :

```bash
systemctl start mariadb
systemctl enable mariadb
```

### Utilisateurs

Création d'un profil par membre du groupe (hugo, matis, alex), avec tous les droits :

```sql
CREATE USER 'alex'@'localhost' IDENTIFIED BY 'mot_de_passe';
GRANT ALL PRIVILEGES ON *.* TO 'alex'@'localhost' WITH GRANT OPTION;
```

Test de l'accès (le mot de passe est demandé) :

```bash
mariadb -u alex -p
```

Utilisateur utilisé par les scripts depuis la VM cliente :

```sql
CREATE USER 'client'@'ADRESSE_IP_VM_CLIENTE' IDENTIFIED BY 'mot_de_passe';
GRANT ALL PRIVILEGES ON *.* TO 'client'@'ADRESSE_IP_VM_CLIENTE' WITH GRANT OPTION;
```

La base `PSMM` et ses tables sont créées automatiquement par les scripts (`CREATE DATABASE IF NOT EXISTS` et `CREATE TABLE IF NOT EXISTS`).

### Logs et accès distant

Dans `/etc/mysql/mariadb.conf.d/50-server.cnf` :

```ini
log_error    = /var/log/mysql/error.log
bind-address = 0.0.0.0
```

- `log_error` écrit les erreurs, dont les tentatives de connexion refusées, dans un fichier séparé, lu par le Job 06.
- `bind-address = 0.0.0.0` autorise les connexions depuis les autres machines. Avec `127.0.0.1`, seules les connexions locales sont acceptées et les scripts reçoivent un `Connection refused`.

Création du dossier de logs, puis redémarrage :

```bash
sudo mkdir /var/log/mysql
sudo chown mysql:mysql /var/log/mysql
sudo systemctl restart mariadb
```

### Vérifier que la base fonctionne

```bash
systemctl status mariadb                        # le service doit être "active (running)"
sudo ss -tlnp | grep 3306                       # doit afficher 0.0.0.0:3306
mariadb -h ADRESSE_IP_MARIADB -u client -p      # depuis la VM cliente
```

---

## Installation de ProFTPD

Organisation de la configuration :

```
/etc/proftpd/
├── proftpd.conf                    ← config de base (identité serveur, port, IP d'écoute)
└── conf.d/
    ├── starfleet-ftp.conf          ← chroot, restrictions d'accès
    └── starfleet-tls.conf          ← chiffrement SSL/TLS
```

Installation :

```bash
apt update
apt install -y proftpd proftpd-mod-crypto
sudo service proftpd start
```

### Configuration de base

Dossier qui accueille les données du serveur FTP :

```bash
sudo mkdir /var/opt/psmmFTP
```

Dans `/etc/proftpd/proftpd.conf` :

```apache
# Nom d'hôte et message de bienvenue
ServerName "Serveur FTP"
DisplayLogin "La connexion au serveur FTP sous Debian s'est effectuée avec succès !"

<Global>
    # Connexion autorisée uniquement avec un shell déclaré dans /etc/shells
    RequireValidShell on
    # Connexion root interdite
    RootLogin off
    # Répertoire auquel l'utilisateur est limité
    DefaultRoot /var/opt/psmmFTP
</Global>

# Seuls les membres du groupe ftpuser peuvent se connecter
<Limit LOGIN>
    DenyGroup !ftpuser
</Limit>
```

Pour que les utilisateurs FTP n'aient pas accès à un shell sur le système :

```bash
sudo sh -c 'echo "/bin/false" >> /etc/shells'
```

Création de l'utilisateur FTP (Debian crée en même temps le groupe `ftpuser`) :

```bash
sudo adduser ftpuser --shell /bin/false --home /home/ftpuser
sudo service proftpd restart
```

Les tentatives avec un utilisateur inexistant sont écrites dans `/var/log/proftpd/proftpd.log`, lu par le Job 07.

---

## Installation de nginx

Vérifier que `/etc/apt/sources.list` contient bien les dépôts Trixie à jour.

### Dépôt officiel nginx

```bash
apt install -y wget gnupg2 ca-certificates lsb-release
wget -qO - https://nginx.org/keys/nginx_signing.key | gpg --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/debian $(lsb_release -cs) nginx" > /etc/apt/sources.list.d/nginx.list
```

Si `apt update` affiche « Le dépôt ... n'est pas signé », c'est que le fichier de clé `/usr/share/keyrings/nginx-archive-keyring.gpg` est absent : relancer la commande `wget ... gpg --dearmor` ci-dessus, ou supprimer le fichier du dépôt dans `/etc/apt/sources.list.d/` et utiliser le nginx de Debian.

### Installation et lancement

```bash
sudo apt update
sudo apt install nginx
sudo systemctl start nginx
```

### Site web

```bash
sudo mkdir /var/www/monserveurweb
sudo nano /var/www/monserveurweb/index.html
```

```html
<html>
<head></head>
<body>
<h1>Bienvenue sur mon serveur Web !</h1>
</body>
</html>
```

```bash
sudo chown -R www-data:www-data /var/www/monserveurweb
sudo chmod -R 755 /var/www/monserveurweb
```

### Authentification basic

Installation des outils d'Apache, qui fournissent `htpasswd` :

```bash
sudo apt install apache2-utils
```

Création du fichier des utilisateurs avec l'utilisateur `monitor`. L'option `-c` crée le fichier : ne pas la remettre pour ajouter d'autres utilisateurs, sinon le fichier est écrasé. Le mot de passe est enregistré sous forme hachée.

```bash
sudo htpasswd -c /etc/nginx/.htpasswd monitor
```

Configuration du site dans `/etc/nginx/sites-available/monserveurweb` :

```nginx
server {
    listen 80;
    listen [::]:80;

    root /var/www/monserveurweb/;
    index index.html;

    # N'importe quelle requête sur ce serveur renvoie vers ce site
    server_name _;

    location / {
        try_files $uri $uri/ =404;
    }

    # Authentification demandée pour tout le site
    auth_basic           "Monitor domain";
    auth_basic_user_file /etc/nginx/.htpasswd;
}
```

Activation du site, vérification de la configuration et redémarrage :

```bash
sudo ln -s /etc/nginx/sites-available/monserveurweb /etc/nginx/sites-enabled/monserveurweb
sudo nginx -t
sudo systemctl restart nginx
```

Les tentatives avec un utilisateur inconnu sont écrites dans `/var/log/nginx/error.log`, lu par le Job 08.

---

## Accès SSH par clé

Depuis la VM cliente, création de la paire de clés et copie de la clé publique sur chaque serveur :

```bash
ssh-keygen -t rsa -b 4096 -C "alex.taylor@laplateforme.io"
ssh-copy-id monitor@ADRESSE_IP_SERVEUR
```

Garder l'emplacement proposé par défaut pour la clé (`~/.ssh/id_rsa`), puis tester :

```bash
ssh monitor@ADRESSE_IP_SERVEUR
```

- `id_rsa` : clé privée, à garder secrète, jamais partagée, avec des permissions restrictives (`chmod 600`).
- `id_rsa.pub` : clé publique, copiée sur le serveur distant dans `~/.ssh/authorized_keys`.
- `known_hosts` : empreintes des serveurs déjà connus. Si un serveur est réinstallé ou change d'adresse, SSH affiche « REMOTE HOST IDENTIFICATION HAS CHANGED » : supprimer l'ancienne empreinte avec `ssh-keygen -R ADRESSE_IP`.

---

## VM cliente : Python et envoi de mails

### Python et bibliothèques

```bash
sudo apt install python3 python3-pip python3-paramiko -y
python3 -m pip install PyMySQL --break-system-packages
```

- **paramiko** : connexion SSH et exécution de commandes sur les serveurs.
- **PyMySQL** : connexion à la base MariaDB depuis Python.

### Envoi de mails avec msmtp

```bash
sudo apt install msmtp msmtp-mta
```

Configuration dans `~/.msmtprc`, avec un **mot de passe d'application** Gmail (à générer dans les paramètres de sécurité du compte Google, jamais le mot de passe du compte) :

```
defaults
auth           on
tls            on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
logfile        ~/.msmtp.log

account        gmail
host           smtp.gmail.com
port           587
from           alex.taylor@laplateforme.io
user           alex.taylor@laplateforme.io
password       MOT_DE_PASSE_APPLICATION

account default : gmail
```

```bash
chmod 600 ~/.msmtprc
```

Test :

```bash
printf "Subject: Test\n\nMessage de test" | msmtp alex.taylor@laplateforme.io
```

La ligne vide (`\n\n`) entre les en-têtes et le corps du message est obligatoire.

---

## Variables d'environnement

Les secrets ne sont pas écrits dans les scripts : ils sont lus dans des variables d'environnement.

| Variable | Utilisée par | Contenu |
|---|---|---|
| `PSSWD_PSMM` | Jobs 04, 06, 07, 08, 14 | Mot de passe sudo du compte `monitor` sur les serveurs |
| `PSMM_WEBHOOK` | Job 15 | Adresse du webhook Google Chat |

Définition persistante dans `~/.bashrc` :

```bash
echo 'export PSSWD_PSMM="mot_de_passe_sudo"' >> ~/.bashrc
echo 'export PSMM_WEBHOOK="https://chat.googleapis.com/v1/spaces/..."' >> ~/.bashrc
source ~/.bashrc
```

cron ne lit pas `~/.bashrc` : ces variables doivent aussi être définies en haut de la crontab (voir [Planification avec cron](#planification-avec-cron)).

---

## Les jobs et leurs scripts

Tous les scripts se trouvent dans `scriptsPSMM/` et s'exécutent depuis la VM cliente.

### Job 01 : création des serveurs

Création des trois VM Debian (FTP, Web, MariaDB) décrites dans [Architecture](#architecture), installation des services, compte `monitor` membre du groupe `sudo`, connexion SSH par clé uniquement et root interdit.

### Job 02 : VM cliente

VM Debian sans interface graphique, avec Python, le client MariaDB (sans le serveur), un client FTP et de quoi envoyer des mails en Python (voir [VM cliente](#vm-cliente--python-et-envoi-de-mails)).

### Job 03 : `ssh_login.py`

Se connecte en SSH à un serveur avec la clé du compte `monitor` et lance une commande shell (`df`).

```bash
python3 ssh_login.py ADRESSE_IP_SERVEUR
```

L'adresse du serveur est récupérée avec `sys.argv[1]` (`sys.argv[0]` contient le nom du script).

### Job 04 : `ssh_login_sudo.py`

Même principe, mais la commande est lancée avec `sudo`. `get_pty=True` simule un terminal pour que sudo puisse demander le mot de passe, qui est envoyé sur l'entrée standard depuis la variable `PSSWD_PSMM`.

```bash
python3 ssh_login_sudo.py ADRESSE_IP_SERVEUR
```

### Job 05 : `ssh_mysql.py`

Vérifie l'accès au serveur MariaDB : connexion SSH, puis connexion à la base avec PyMySQL. Le script s'arrête avec un message clair si l'une des deux échoue.

```bash
python3 ssh_mysql.py ADRESSE_IP_MARIADB
```

### Job 06 : `ssh_mysql_error.py`

Lit `/var/log/mysql/error.log` en sudo, garde les lignes `Access denied for user` et enregistre pour chaque tentative le nom du compte, la date/heure et l'adresse IP dans la table `logsTable`.

```bash
python3 ssh_mysql_error.py ADRESSE_IP_MARIADB
```

Exemple de ligne traitée :

```
2026-09-28 14:03:03 5 [Warning] Access denied for user 'monitor'@'localhost' (using password: YES)
```

Le nom du compte et l'IP se trouvent entre apostrophes, d'où le découpage avec `split("'")`.

Pour éviter les doublons à chaque exécution, l'insertion utilise la table virtuelle `DUAL` et `NOT EXISTS` : la ligne n'est insérée que si aucune ligne n'a déjà la même date/heure. `DUAL` permet d'écrire un `SELECT` sur des valeurs qui ne viennent d'aucune table, et donc d'y ajouter une condition `WHERE`.

```sql
INSERT INTO logsTable (application, date_hour, name_account, IP_adress)
SELECT 'mariadb', %s, %s, %s
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM logsTable WHERE date_hour = %s
);
```

Les valeurs sont passées en paramètres (`%s`), ce qui protège des injections SQL : les noms de comptes viennent des logs et peuvent contenir n'importe quoi.

### Job 07 : `ssh_ftp_error.py`

Même principe sur le serveur FTP : lecture de `/var/log/proftpd/proftpd.log` en sudo, filtrage des lignes `no such user found`, puis insertion dans `logsTable` avec l'application `ftp`. Le nom du compte est nettoyé du `:` final, et l'heure est limitée à `hh:mm:ss` (sans les millisecondes).

```bash
python3 ssh_ftp_error.py ADRESSE_IP_FTP
```

Pour générer des erreurs : se connecter avec de mauvais identifiants depuis FileZilla sur son poste, ou depuis un client FTP en ligne de commande sur la VM cliente.

### Job 08 : `ssh_web_error.py`

Même principe sur le serveur Web : lecture de `/var/log/nginx/error.log` en sudo et insertion dans `logsTable` avec l'application `web`.

```bash
python3 ssh_web_error.py ADRESSE_IP_WEB
```

Exemple de ligne traitée :

```
2026/09/28 17:20:12 [error] 1234#1234: *1 user "rze" was not found in "/etc/nginx/.htpasswd", client: 192.168.112.1, ...
```

La date est convertie de `aaaa/mm/jj` en `aaaa-mm-jj` pour être reconnue par MariaDB, et les guillemets du nom de compte ainsi que la virgule après l'IP sont retirés.

### Job 09 : `ssh_serveur_mail.py`

Récupère dans `logsTable` les tentatives de connexion de la veille (de minuit à minuit) et les envoie par mail à l'administrateur, une tentative par ligne.

```bash
python3 ssh_serveur_mail.py ADRESSE_IP_MARIADB
```

La requête compare uniquement la partie date de `date_hour` avec `DATE()`, car `date_hour` contient la date et l'heure alors que `CURDATE()` ne renvoie que la date :

```sql
SELECT * FROM logsTable
WHERE DATE(date_hour) >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
  AND DATE(date_hour) < CURDATE();
```

Le mail est envoyé en passant le message complet à msmtp avec `subprocess.run(..., input=message, text=True)`, sans passer par un shell, ce qui évite les problèmes de guillemets.

### Job 10 : `ssh_cron_backup.py`

Sauvegarde locale et horodatée de la table `logsTable`, avec conservation des 7 dernières sauvegardes, lancée par cron toutes les 3 heures (soit environ 21 heures d'historique).

```bash
python3 ssh_cron_backup.py ADRESSE_IP_MARIADB
```

- Les fichiers sont nommés `backup_AAAA-MM-JJ_HH-MM-SS.txt` dans le dossier `backup/`.
- **Rotation** : s'il y a déjà 7 fichiers, le script cherche le plus ancien en comparant les dates de modification (`os.path.getmtime`) et le supprime avant de créer la nouvelle sauvegarde. `os.listdir` ne renvoyant que les noms, le chemin complet est construit avec `os.path.join`.
- Le contenu est écrit avec `echo ... >>`, et `shlex.quote()` protège le texte (qui contient des apostrophes) pour qu'il soit transmis tel quel au shell.
- Le chemin du dossier est absolu, car cron ne lance pas le script depuis le dossier des scripts.

### Job 11 : `ssh_system_status.py`

Relève l'utilisation du CPU, de la RAM et du disque de chaque serveur, l'enregistre dans la table `ResSys` et ne garde que les mesures des 72 dernières heures.

```bash
python3 ssh_system_status.py IP_SERVEUR_1 IP_SERVEUR_2 IP_SERVEUR_3
```

Plusieurs serveurs peuvent être passés en arguments (`sys.argv[1:]`) : la fonction `ressourceTaking()` est appelée pour chacun.

| Ressource | Commande | Calcul |
|---|---|---|
| CPU | `vmstat 1 2` | `100 - id` sur la dernière ligne |
| RAM | `free -h` | `utilisé / total × 100`, avec conversion Mi/Gi et remplacement de la virgule décimale |
| Disque | `df -h /` | colonne `Uti%` |

- `vmstat 1 2` affiche deux mesures : la première est une moyenne depuis le démarrage (à ignorer), la seconde porte sur la dernière seconde. La colonne `id` (idle) est le pourcentage d'inactivité du processeur. Sa position est trouvée avec `header.index("id")`.
- La fenêtre de 72 heures est glissante : après chaque insertion, `DELETE FROM ResSys WHERE date_hour < NOW() - INTERVAL 72 HOUR` supprime les mesures trop anciennes.
- `htop` n'est pas utilisable dans un script, car il est interactif. `vmstat`, `free` et `df` affichent une mesure puis se terminent.

![Mesures des ressources](image.png)

#### Simuler une charge pour les tests

```bash
# CPU à environ 75 % (Ctrl + C après fg pour arrêter)
while true; do timeout 0.75 yes > /dev/null; sleep 0.25; done &

# RAM et CPU avec stress-ng (arrêt automatique au bout de 2 minutes)
stress-ng --vm 1 --vm-bytes 600M --vm-keep --timeout 120s

# Disque : fichier de 5 Go (rm ~/gros_fichier pour libérer)
fallocate -l 5G ~/gros_fichier
```

### Job 12 : `ssh_system_mail.py`

Reprend le Job 11 et envoie un mail à l'administrateur si un seuil est dépassé. Les seuils sont des variables en haut du script, faciles à modifier (consigne : CPU 70 %, disque 90 %, RAM 80 %) :

```python
threshCPU = 70
threshDisk = 90
threshRAM = 80
```

Les alertes de tous les serveurs sont regroupées dans la liste `listAlert`, et un seul mail est envoyé à la fin. La variable `send` est déclarée `global` dans la fonction, car elle y est réaffectée. Planifié toutes les 5 minutes avec cron.

```bash
python3 ssh_system_mail.py IP_SERVEUR_1 IP_SERVEUR_2 IP_SERVEUR_3
```

### Job 13 : limite d'un mail par heure

Dans `ssh_system_mail.py`, la fonction `IsMoreThanOneHour()` empêche d'envoyer plus d'un mail par heure, alors que le script tourne toutes les 5 minutes.

L'heure du dernier envoi est enregistrée dans le fichier `lastSent.txt`, au format `jj/mm/aaaa hh:mm:ss`. Une variable d'environnement ne convient pas : chaque exécution lancée par cron est un nouveau programme, et une variable définie par le script disparaît à la fin de son exécution.

À chaque exécution, la fonction :

1. lit la date du fichier et la convertit en date avec `datetime.strptime` ;
2. calcule l'écart avec `datetime.now()` grâce à `total_seconds()` ;
3. si plus de 3600 secondes se sont écoulées, enregistre l'heure actuelle dans le fichier et autorise l'envoi.

Si le fichier n'existe pas encore (`FileNotFoundError`), l'envoi est autorisé.

### Job 14 : `ssh_update.py`

Met à jour chaque serveur et prévient l'administrateur par mail si un redémarrage est nécessaire.

```bash
python3 ssh_update.py IP_SERVEUR_1 IP_SERVEUR_2 IP_SERVEUR_3
```

Déroulement pour chaque serveur :

1. connexion à ALCASAR pour obtenir l'accès à Internet (*à compléter*) ;
2. `sudo apt update` pour rafraîchir la liste des paquets ;
3. si des paquets peuvent être mis à jour, `sudo apt-get upgrade -y`. Le script attend la fin de l'installation avec `_stdout.channel.recv_exit_status()`, sinon la fermeture de la connexion SSH interromprait apt ;
4. vérification, **sur le serveur** via SSH, de la présence du fichier `/var/run/reboot-required`, que Debian crée quand une mise à jour nécessite un redémarrage. Il disparaît de lui-même au redémarrage, car `/run` est vidé à chaque démarrage ;
5. si un redémarrage est nécessaire, envoi d'un mail à l'administrateur (le script ne redémarre pas le serveur lui-même) ;
6. déconnexion d'ALCASAR (*à compléter*).

Pour vérifier l'accès à Internet, on peut interroger une adresse témoin qui renvoie toujours le code 204 :

```bash
curl -s -o /dev/null -w "%{http_code}" http://connectivitycheck.gstatic.com/generate_204
```

`204` signifie que la machine a accès à Internet. `302` ou `200` signifie que le portail captif intercepte la requête, et `000` qu'il n'y a aucune réponse.

### Job 15 : `ssh_chatgoogle_alerte.py`

Reprend la surveillance des ressources et publie les alertes dans un **Space Google Chat** regroupant les membres du groupe et l'accompagnateur pédagogique.

```bash
python3 ssh_chatgoogle_alerte.py IP_SERVEUR_1 IP_SERVEUR_2 IP_SERVEUR_3
```

Mise en place du webhook :

1. Dans Google Chat, ouvrir le Space, cliquer sur son nom, puis **Applications et intégrations** et **Webhooks**.
2. Ajouter un webhook (par exemple « Supervision PSMM ») et copier l'adresse générée.
3. Enregistrer cette adresse dans la variable d'environnement `PSMM_WEBHOOK`.

Le message est envoyé avec `urllib.request`, au format JSON attendu par Google Chat (champ `text`) :

```python
payload = {'text': "\n".join(listAlert)}
```

Test rapide depuis la VM cliente :

```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"text": "Test depuis la VM de supervision"}' \
     "$PSMM_WEBHOOK"
```

---

## Base de données

Base `PSMM`, sur le serveur MariaDB.

### Table `logsTable` (Jobs 06 à 10)

| Colonne | Type | Contenu |
|---|---|---|
| `id` | `INT AUTO_INCREMENT PRIMARY KEY` | Identifiant |
| `application` | `VARCHAR(100)` | `mariadb`, `ftp` ou `web` |
| `date_hour` | `VARCHAR(100)` | Date et heure de la tentative (`AAAA-MM-JJ HH:MM:SS`) |
| `name_account` | `VARCHAR(100)` | Compte utilisé |
| `IP_adress` | `VARCHAR(20)` | Adresse IP du poste |

### Table `ResSys` (Jobs 11 à 15)

| Colonne | Type | Contenu |
|---|---|---|
| `id` | `INT AUTO_INCREMENT PRIMARY KEY` | Identifiant |
| `Ip_Adress` | `VARCHAR(100)` | Serveur mesuré |
| `date_hour` | `VARCHAR(100)` | Date et heure de la mesure |
| `Memory` | `VARCHAR(10)` | Utilisation RAM en % |
| `CPU` | `VARCHAR(10)` | Utilisation CPU en % |
| `Disk` | `VARCHAR(10)` | Utilisation disque en % |

Les dates sont toujours au format `AAAA-MM-JJ HH:MM:SS`. Ce format se trie correctement comme du texte et est compris par les fonctions de date de MariaDB (`DATE()`, `NOW()`, `INTERVAL`), même si les colonnes sont en `VARCHAR`.

---

## Planification avec cron

Édition de la crontab de l'utilisateur `client` (pas celle de root, pour que les fichiers créés lui appartiennent) :

```bash
crontab -e
```

```
MAILTO=""
PSSWD_PSMM="mot_de_passe_sudo"
PSMM_WEBHOOK="https://chat.googleapis.com/v1/spaces/..."

# m  h    dom mon dow  commande
# Job 09 : récapitulatif des tentatives de la veille, chaque jour à 7h
0   7    *   *   *    /usr/bin/python3 /home/client/PSSM/scriptsPSMM/ssh_serveur_mail.py 192.168.112.111 >> /home/client/PSSM/scriptsPSMM/cron.log 2>&1
# Job 10 : sauvegarde toutes les 3 heures
0   */3  *   *   *    /usr/bin/python3 /home/client/PSSM/scriptsPSMM/ssh_cron_backup.py 192.168.112.111 >> /home/client/PSSM/scriptsPSMM/cron.log 2>&1
# Jobs 11 à 13 : mesures et alertes mail toutes les 5 minutes
*/5 *    *   *   *    /usr/bin/python3 /home/client/PSSM/scriptsPSMM/ssh_system_mail.py 192.168.112.111 192.168.112.112 192.168.112.113 >> /home/client/PSSM/scriptsPSMM/cron.log 2>&1
# Job 14 : mises à jour chaque dimanche à 3h
0   3    *   *   0    /usr/bin/python3 /home/client/PSSM/scriptsPSMM/ssh_update.py 192.168.112.111 192.168.112.112 192.168.112.113 >> /home/client/PSSM/scriptsPSMM/cron.log 2>&1
# Job 15 : état des serveurs sur Google Chat toutes les heures
0   *    *   *   *    /usr/bin/python3 /home/client/PSSM/scriptsPSMM/ssh_chatgoogle_alerte.py 192.168.112.111 192.168.112.112 192.168.112.113 >> /home/client/PSSM/scriptsPSMM/cron.log 2>&1
```

Adapter les adresses IP à celles des serveurs.

- `MAILTO=""` empêche cron d'essayer d'envoyer la sortie des tâches par mail à l'utilisateur local, adresse que Gmail refuse.
- `>> cron.log 2>&1` enregistre la sortie et les erreurs de chaque exécution dans un fichier de log.
- Les chemins sont absolus (`/usr/bin/python3`, chemin complet des scripts), car l'environnement de cron est minimal : il ne lit pas `~/.bashrc` et ne démarre pas dans le dossier des scripts.
- Le caractère `%` ne doit pas apparaître dans une ligne de crontab : cron l'interprète comme un retour à la ligne.

### Vérifier que cron fonctionne

```bash
systemctl status cron                    # le service doit être "active (running)"
systemctl is-enabled cron                # doit répondre "enabled"
crontab -l                               # liste des tâches enregistrées
journalctl -u cron --since today         # une ligne "CMD (...)" par exécution
cat /home/client/PSSM/scriptsPSMM/cron.log
```

Le service cron tourne en permanence, alors que chaque tâche ne s'exécute que quelques secondes, aux heures prévues. Quand la VM est éteinte ou en pause, les exécutions manquées ne sont pas rattrapées.

---

## Sécurité

- Connexion SSH par clé uniquement, root interdit, compte `monitor` dédié.
- Requêtes SQL paramétrées (`%s`) pour toutes les données venant des logs, contre les injections SQL.
- Utilisateurs FTP sans shell (`/bin/false`) et limités à leur répertoire (`DefaultRoot`).
- Site web protégé par une authentification basic, avec mots de passe hachés.
- Mots de passe et adresse du webhook stockés dans des variables d'environnement, et non dans les scripts.
- **Aucun secret dans le dépôt GitHub** : mot de passe d'application Gmail, mots de passe MariaDB, mot de passe sudo et adresse du webhook ne doivent jamais être commités. Un secret poussé une fois reste visible dans l'historique Git, même après sa suppression : il faut alors le changer.

---