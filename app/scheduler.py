import schedule
import time
import subprocess
from datetime import datetime

def Salva():
    print(f"[{datetime.now()}] → Exécution de l'algorithme Salva ...")
    result = subprocess.run(
        ["python", "salava.py", "--user", "batmoon19@gmail.com"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"[ERREUR] {result.stderr}")
    else:
        print(f"[OK] Terminé avec succès")

schedule.every(1).day.at("08:00").do(Salva)

print("Scheduler démarré...")
while True :
    schedule.run_pending()
    time.sleep(10)
