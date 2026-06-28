import threading
import time
import socket
from typing import List

from network import ServerNetwork
from server_utils import *

random.seed(42)  # Pour la reproductibilité des résultats


class Server:

    def __init__(self, host: str, port: int):

        self.adjacent_list = AdjacentList()
        self.adjacent_list._generate_random_users(5)  # Génère 5 utilisateurs aléatoires

        self.server = ServerNetwork(host, port, self.adjacent_list.add_user)
        self.server_thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.server.start()
        self.server_thread.start()
        self._input_loop()

    def _input_loop(self):
        while True:
            command = input()
            if command.lower() == "exit":
                reponse = input("Are you sure you want to exit? (y/n): ")
                if reponse.lower() == "y" or reponse.lower() == "yes":
                    self.server.close()
                    break
                else:
                    print("Exit cancelled.")
            elif command.lower() == "get users":
                self.adjacent_list.display_matrix()
            elif command.lower() == "help":
                print("\nAvailable commands: 'get users', 'exit'")
            else:
                print("\nCommand not recognized. Try help for a list of commands.")

    def update(self):
        state = self.server.update({})

    def run(self):
        while self.server._tcp_thread.is_alive():
            self.update()


if __name__ == "__main__":

    host = socket.gethostbyname(socket.gethostname())
    port = 5555

    try:
        Server(host, port).start()
    except KeyboardInterrupt:
        print("\n[Host] Server shutdown...")
    else:
        print("\n[Host] Server shutdown...")
