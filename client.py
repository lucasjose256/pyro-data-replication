import Pyro5.client
import Pyro5.api
import random

def send_command(server_uri, log_entries):
    server = Pyro5.api.Proxy(server_uri)
    response = server.process_command(log_entries)
    if response.startswith("Redirecionando para o Líder"):
        id = response.split()[-1]
        print(f"Redirecionado para o Servidor {id} (Líder)")
        leader_uri = f"PYRONAME:server{id}"
        return send_command(leader_uri, log_entries)
    else:
        leader_uri = server_uri
    return response, leader_uri

command = ""
term = -1
index = 0
leader_uri = ""
while command != ".sair":
    index += 1
    command = str(input("Insira o comando: "))
    if command == ".sair":
        break
    logs_entries = [{"term": term, "index": index, "command": command}]
    try:
        if leader_uri == "":
            id = random.randint(1, 4)
            proxy = Pyro5.client.Proxy(f"PYRONAME:server{id}")
            print(f"Enviando comando para o Servidor {id}")
            response, leader_uri = send_command(f"PYRONAME:server{id}", logs_entries)
        else:
            print(f"Enviando comando para o Servidor {leader_uri[15]}")
            response, leader_uri = send_command(leader_uri, logs_entries)
        print(response)
    except Exception as e:
        if leader_uri == "":
            print(f"Erro ao mandar comando para o servidor {id}")
        else:
            print(f"Erro ao mandar comando para o servidor {leader_uri[15]}")
            leader_uri = ""
        index -= 1