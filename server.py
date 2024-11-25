import random
import threading
import sys
from time import sleep

import Pyro5.api
import Pyro5.server
import Pyro5.core

@Pyro5.api.expose
class Server:
    def __init__(self, id):
        self.id = id  # Identificador do Servidor
        self.state = "follower"  # Inicialização do Servidor como Seguidor
        self.election_timer = None  # Timer de Eleição
        self.peers = [f"PYRO:server{n}@localhost:1234{n-1}" for n in range(1, 5) if n != id]  # URI dos outros servidores
        self.term = 0  # Termo atual
        self.voted_for = None  # Voto do Servidor
        self.vote_count = 0  # Quantidade de votos que o Servidor recebeu
        self.leader = None  # Líder atual
        self.logs = []  # Logs do Servidor
        self.commit_index = 0  # Índice do Commit
        self.confirmation_count = 0  # Quantidade de confirmações dos logs
        self.commited = False  # Flag para commit

        self.first_election_timer()  # Chamada para inicializar o timer de Eleição

    # Método para inicializar o Timer de Eleição
    def first_election_timer(self):
        print(f"[SERVER {self.id}] Iniciando o servidor...")
        sleep(5)
        self.reset_election_timer(False)

    # Método para reiniciar o Timer de Eleição
    def reset_election_timer(self, heartbeat):
        if self.election_timer:
            self.election_timer.cancel()
        timeout = random.uniform(3.0, 10.0)
        if heartbeat:
            # print(f"[SERVER {self.id}] Novo timeout (heartbeat): {timeout}s")
            pass
        else:
            print(f"\n[SERVER {self.id}] Novo timeout: {timeout}s")
        self.election_timer = threading.Timer(timeout, self.start_election)
        self.election_timer.start()

    # Método para iniciar a Eleição
    def start_election(self):
        if self.state == "follower":
            self.state = "candidate"
            self.term += 1
            self.voted_for = self.id
            self.vote_count = 1
            print(f"\n[SERVER {self.id}] Virei Candidato para o termo {self.term}")
            print(f"\n[SERVER {self.id}] Eleição iniciada para o termo {self.term}")
            for peer in self.peers:
                threading.Thread(target=self.request_vote_from_others(peer), args=(peer,)).start()

        elif self.state == "candidate":
            print(f"\n[SERVER {self.id}] Virei Seguidor")
            self.state = "follower"
            self.voted_for = None
            self.vote_count = 0
            print(f"\n[SERVER {self.id}] Falha na eleição do termo {self.term}")
            self.reset_election_timer(False)

    # Método para requisitar votos de outros Servidores
    def request_vote_from_others(self, uri):
        try:
            proxy = Pyro5.api.Proxy(uri)
            proxy._pyroTimeout = 5
            print(f"\n[SERVER {self.id}] Requisitando voto para {uri[5:]}")
            voted = proxy.send_vote(self.term, self.id)
            if voted:
                print(f"\n[SERVER {self.id}] Voto recebido de {uri[5:]}")
                self.vote_count += 1

                if self.vote_count > (len(self.peers) + 1) // 2 and self.state == "candidate":
                    self.start_leader()
        except Exception as e:
            print(f"\n[SERVER {self.id}] Erro no voto de {uri[5:]}")
            pass

    # Método para o Servidor tornar-se Líder
    def start_leader(self):
        if self.state == "candidate":
            self.state = "leader"
            self.leader = self.id
            self.voted_for = None
            self.vote_count = 0
            self.election_timer.cancel()
            print(f"\n[SERVER {self.id}] Virei Líder do termo {self.term}")
            self.send_heartbeat()

    # Método para enviar "heartbeats" periodicamente
    def send_heartbeat(self):
        for peer in self.peers:
                def send_to_peer(peer):
                    try:
                        proxy = Pyro5.api.Proxy(peer)
                        proxy._pyroTimeout=5
                        proxy.append_entries(self.term, self.id, None, self.commit_index)
                    except Exception as e:
                        pass
                threading.Thread(target=send_to_peer, args=(peer,)).start()
        threading.Timer(0.5, self.send_heartbeat).start()

    # Método para "receber" entradas de logs
    def append_entries(self, term, leader_id, log_entries, commit_index):
        self.reset_election_timer(True)
        if commit_index > self.commit_index:
            self.commit_index = commit_index
            print(f"[SERVER {self.id}] Log com índice {self.commit_index} commitado")
        if term >= self.term:
            self.term = term
            self.state = "follower"
            self.leader = leader_id
            self.voted_for = None
            self.vote_count = 0
            # print(f"[SERVER {self.id}] O Líder do termo {self.term} é {self.leader}")
            for log in log_entries:
                if len(self.logs) < log['index'] or self.logs[log['index'] - 1]['term'] != log['term']:
                    self.logs = self.logs[:log['index'] - 1] + [log]
                    print(
                        f"[SERVER {self.id}] Atualização dos Logs no índice {log['index']} com termo {log['term']}: {log['command']}")
            print(f"[SERVER {self.id}] Logs: {self.logs}")
            return True
        return False

    # Método para enviar voto
    def send_vote(self, term, candidate_id):
        self.reset_election_timer(False)

        if term > self.term:
            self.term = term
            self.leader = None
            self.voted_for = None

        if self.voted_for is None or self.voted_for == candidate_id:
            self.term = term
            self.voted_for = candidate_id
            print(f"\n[SERVER {self.id}] Votei para o Servidor {self.voted_for} no termo {self.term}")
            return True
        print(f"\n[SERVER {self.id}] Votei para o Servidor {self.voted_for} no termo {self.term}")

        return False

    # Método para processamento do comando enviado pelo Cliente
    def process_command(self, log_entries):
        if self.state == "leader":
            if log_entries:
                self.commited = False
                log_entries[0]['term'] = self.term
                self.logs.extend(log_entries)
                self.confirmation_count = 1
                for peer in self.peers:
                    threading.Thread(target=self.propagate_logs_to_others, args=(self.logs, peer)).start()

                return f"[SERVER {self.id}] Comando '{log_entries[0]['command']}' processado"
        else:
            return f"Redirecionando para o Líder {self.leader}"

    # Método para replicação dos logs em outros Servidores
    def propagate_logs_to_others(self, log_entries, peer):
        try:
            proxy = Pyro5.api.Proxy(peer)
            proxy._pyroTimeout = 5
            print(f"[SERVER {self.id}] Enviando logs para {peer}")
            confirmation = proxy.append_entries(self.term, self.leader, log_entries, self.commit_index)
            if confirmation:
                print(f"[SERVER {self.id}] Recebi a confirmação de {peer}")
                self.confirmation_count += 1

                if self.confirmation_count > (len(self.peers) + 1) // 2 and not self.commited:
                    self.commit_index = log_entries[len(log_entries) - 1]['index']
                    print(f"[SERVER {self.id}] Log com índice {self.commit_index} commitado")
                    print(f"[SERVER {self.id}] Logs: {self.logs}")
                    self.commited = True

        except Exception as e:
            # print(f"ERRO {e}")
            print(f"[SERVER {self.id}] Falha no envio de logs para {peer}")

id = int(sys.argv[1])
porta = int(sys.argv[2])
daemon = Pyro5.server.Daemon(host="localhost", port=porta)
ns = Pyro5.core.locate_ns()
server = Server(id=id)
uri = daemon.register(server, objectId=f"server{id}")
ns.register(f"server{id}", uri)
print(f"[SERVER {id}] Estou disponível na URI: {uri}")
daemon.requestLoop()