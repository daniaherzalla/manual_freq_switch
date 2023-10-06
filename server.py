import json
import logging
import msgpack
import signal
import socket
import sys
import threading
import time
from typing import List, Tuple
from netstring import encode

from options import Options
from util import get_mesh_freq

action_to_id = {
    "jamming_alert": 0,
    "estimation_request": 1,
    "estimation_report": 2,
    "target_frequency": 3,
    "switch_frequency": 4
}
id_to_action = {v: k for k, v in action_to_id.items()}


class JammingServer:
    def __init__(self, host: str, port: int):
        """
        Initializes the JammingServer object.

        :param host: The host address to bind the orchestrator/server to.
        :param port: The port number to bind the orchestrator/server to.
        """
        # Initialize server objects and attributes
        self.running = False
        self.host = host
        self.port = port
        self.serversocket = None
        self.clients: List[JammingClientTwin] = []
        self.args = Options()
        logging.info("initialized server") if self.args.debug else None

        # Create threads for server operations
        self.run_server_thread = threading.Thread(target=self.run_server)

        # Time for periodic events' variables (in seconds)
        self.last_requested_spectrum_data: float = time.time()
        self.last_target_freq_broadcast: float = time.time()

        # Internal Attributes
        self.target_frequency: int = get_mesh_freq()

        signal.signal(signal.SIGINT, self.signal_handler)

    def start(self) -> None:
        """
        Starts the server and listens for incoming client connections.
        """
        try:
            self.running = True
            logging.info("started server") if self.args.debug else None
            self.serversocket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            self.serversocket.bind((self.host, self.port))
            self.serversocket.listen(5)
            logging.info("server started and listening") if self.args.debug else None
            self.run_server_thread.start()
            signal.signal(signal.SIGINT, self.signal_handler)

            while self.running:
                c_socket, c_address = self.serversocket.accept()
                client = JammingClientTwin(c_socket, c_address, self.clients, self.host)
                logging.info(f'New connection {client}') if self.args.debug else None
                self.clients.append(client)

        except ConnectionError as e:
            print(f"Connection error: {e}")

    def signal_handler(self, sig: signal.Signals, frame) -> None:
        """
        Handles a signal interrupt (SIGINT) and stops the server gracefully.

        :param sig: The signal received by the handler.
        :param frame: The current execution frame.
        """
        logging.info("Attempting to close threads.") if self.args.debug else None
        if self.clients:
            for client in self.clients:
                logging.info(f"joining {client.address}") if self.args.debug else None
                client.stop()

            logging.info("threads successfully closed") if self.args.debug else None
            sys.exit(0)

        self.stop()

    def stop(self) -> None:
        """
        Stop the server by closing the server socket and server fsm thread.
        """
        self.running = False

        # Close server socket
        if self.serversocket:
            self.serversocket.close()

        # Join Server FSM thread
        if self.run_server_thread.is_alive():
            self.run_server_thread.join()

    def run_server(self) -> None:
        """
        Run the Server Finite State Machine (FSM) continuously to manage its state transitions and periodic tasks.
        """
        while self.running:
            try:
                # check if freq file populated, if so, trigger switch freq
                self.check_frequency()
                time.sleep(1)
            except Exception as e:
                logging.info(f"Exception in run_server: {e}") if self.args.debug else None

    def check_frequency(self) -> None:
        """
        Checks if frequency is populated in the JSON file and trigger switch frequency.
        """
        try:
            # Load json file to check if there is freq update
            with open(self.args.json_file, 'r') as file:
                data = json.load(file)
                if 'freq' in data and data['freq'] is not None:
                    if isinstance(data['freq'], int):
                        # Set target frequency
                        self.target_frequency = data['freq']
                        # Send switch frequency message to clients
                        self.send_switch_frequency_message()

                # Revert freq back to null
                json.dump({"freq": None}, open(self.args.json_file, 'w'))

        # Capture any exceptions with opening and loading json file
        except FileNotFoundError:
            print(f'File not found: {self.args.json_file}')
        except json.JSONDecodeError:
            print(f'Invalid JSON format in file: {self.args.json_file}')
        except Exception as e:
            print(f'An error occurred: {str(e)}')

    def send_data_clients(self, data) -> None:
        """
        Sends the estimated frequency quality data to a remote server.

        :param data: The message to send to the clients.
        """
        for client in self.clients:
            try:
                serialized_data = msgpack.packb(data)
                netstring_data = encode(serialized_data)
                client.socket.sendall(netstring_data)
            except BrokenPipeError:
                logging.info("Broken pipe error, client disconnected:", client.address) if self.args.debug else None
                self.clients.remove(client)

    def send_switch_frequency_message(self) -> None:
        """
        Sends a message to all connected clients to switch to target frequency.
        """
        action_id = action_to_id["switch_frequency"]
        switch_frequency_data = {'a_id': action_id, 'freq': self.target_frequency}
        self.send_data_clients(switch_frequency_data)


class JammingClientTwin:
    def __init__(self, socket: socket.socket, address: Tuple[str, int], clients: List["JammingClientTwin"], host: str) -> None:
        self.socket = socket
        self.address = address
        self.clients = clients
        self.host = host
        self.args = Options()

    def stop(self) -> None:
        """
        Stops all threads and closes the socket connection.
        """
        # Close server socket
        if self.socket:
            self.socket.close()


def main():
    args = Options()

    host: str = args.jamming_osf_orchestrator
    port: int = args.port
    server: JammingServer = JammingServer(host, port)
    server.start()


if __name__ == "__main__":
    main()
