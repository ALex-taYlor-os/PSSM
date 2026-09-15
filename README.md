## VM MariaDB
### Installation de MariaDB 
Dépôt officiel de Maria DB 
````
curl -LsS https://r.mariadb.com/downloads/mariadb_repo_setup | bash
apt update
apt install mariadb-server mariadb-client -y
````

Checker la version
````
mariadb --version
apt policy mariadb-server
````

On paramètre pour lancer au démarrage mariadb
````
systemctl start mariadb
systemctl enable mariadb
````