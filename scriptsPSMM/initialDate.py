from datetime import datetime


with open('lastSent.txt', 'w') as f:
    f.write(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
