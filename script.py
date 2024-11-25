import subprocess
import time

# Lista de comandos com id e portas diferentes
commands = [
    "python server.py 1 12340",
    "python server.py 2 12341",
    "python server.py 3 12342",
    "python server.py 4 12343"
]

# Abre um novo terminal para cada comando
for command in commands:
    # AppleScript para abrir um novo terminal e rodar o comando
    applescript_command = f'''
    tell application "Terminal"
        do script "{command}"
    end tell
    '''
    subprocess.call(["osascript", "-e", applescript_command])
    time.sleep(1)  # Espera um pouco para evitar sobrecarga de terminais
