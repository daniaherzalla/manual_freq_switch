import os
import re
import subprocess
import sys
import threading
import time
import socket

import msgpack
import numpy as np
from netstring import decode

from options import Options, VALID_CHANNELS
from util import get_mesh_freq, run_command, read_file, write_file, is_process_running, get_ipv6_addr, map_freq_to_channel


action_to_id = {
    "jamming_alert": 0,
    "estimation_request": 1,
    "estimation_report": 2,
    "target_frequency": 3,
    "switch_frequency": 4
}
id_to_action = {v: k for k, v in action_to_id.items()}


class JammingDetectionClient:
    def __init__(self, node_id: str, host: str, port: int) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port

        # Initialize server objects
        self.args = Options()

        # Internal variables
        self.current_frequency: int = get_mesh_freq()
        self.valid_scan_data: bool = False
        self.target_frequency: int = np.nan
        self.freq_quality: dict = {}
        self.best_freq: int = np.nan
        self.healing_process_id: str = ''

        # Time for periodic events' variables (in seconds)
        self.time_last_scan: float = 0
        self.time_last_switch: float = 0

        # Create listen and client run FSM threads
        self.running = False
        self.listen_thread = threading.Thread(target=self.receive_messages)
        self.switching_event = threading.Event()

        self.socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)

    def run(self) -> None:
        """
        Connect to the orchestrator node and start the client's operation in separate threads for running the FSM and receiving messages.
        """
        self.running = True
        self.connect_to_orchestrator()
        self.listen_thread.start()

    def connect_to_orchestrator(self) -> None:
        """
        Connect to orchestrator via OSF.
        """
        max_retries: int = 3
        number_retries: int = 0
        while number_retries < max_retries:
            try:
                self.socket.connect((self.host, self.port))
                break
            except ConnectionRefusedError:
                number_retries += 1
                print(f"OSF server connection failed... retry #{number_retries}") if self.args.debug else None

            if number_retries == max_retries:
                sys.exit("OSF Server unreachable")

            time.sleep(3)

    def receive_messages(self) -> None:
        """
        Receive incoming messages from the orchestrator.
        """
        while self.running:
            try:
                # Receive incoming messages and decode the netstring encoded data
                try:
                    data = decode(self.socket.recv(1024))
                    if not data:
                        print("No data... break") if self.args.debug else None
                        break
                except Exception as e:
                    # Handle netstring decoding errors
                    print(f"Failed to decode netstring: {e}") if self.args.debug else None
                    break

                # Deserialize the MessagePack message
                try:
                    unpacked_data = msgpack.unpackb(data, raw=False)
                    action_id: int = unpacked_data.get("a_id")
                    action_str: str = id_to_action.get(action_id)
                    print(f"Received message: {unpacked_data}") if self.args.debug else None

                    # Handle frequency switch request
                    if action_str == "switch_frequency":
                        received_target_freq = unpacked_data.get("freq")
                        self.update_target_freq(received_target_freq)
                        if self.current_frequency != self.target_frequency and not self.switching_event.is_set():
                            self.switching_event.set()
                            self.switch_frequency()
                            self.switching_event.clear()

                except msgpack.UnpackException as e:
                    print(f"Failed to decode MessagePack: {e}") if self.args.debug else None
                    continue

                except Exception as e:
                    print(f"Error in received message: {e}") if self.args.debug else None
                    continue

            except ConnectionResetError:
                print("Connection forcibly closed by the remote host") if self.args.debug else None
                break

    def switch_frequency(self) -> None:
        """
        Change the mesh frequency to the target frequency.
        """
        # Initialize switch frequency variables

        print(f"Switching to {self.target_frequency} MHz ...\n") if self.args.debug else None
        try:
            # Run commands
            cmd_rmv_ip = "ifconfig " + self.args.mesh_interface + " 0"
            cmd_interface_down = "ifconfig " + self.args.mesh_interface + " down"
            run_command(cmd_rmv_ip, 'Failed to set ifconfig wlp1s0 0')
            run_command(cmd_interface_down, 'Failed to set ifconfig wlp1s0 down')

            # If wpa_supplicant is running, kill it before restarting
            if is_process_running('wpa_supplicant'):
                run_command('killall wpa_supplicant', 'Failed to kill wpa_supplicant')
                time.sleep(10)

            # Remove mesh interface file to avoid errors when reinitialize interface
            interface_file = '/var/run/wpa_supplicant/' + self.args.mesh_interface
            if os.path.exists(interface_file):
                os.remove(interface_file)

            # Read and check wpa supplicant config
            conf = read_file('/var/run/wpa_supplicant-11s.conf', 'Failed to read wpa supplicant config')
            if conf is None:
                print("Error: wpa supplicant config is None. Aborting.") if self.args.debug else None
                return

            # Edit wpa supplicant config with new mesh freq
            conf = re.sub(r'frequency=\d*', f'frequency={self.target_frequency}', conf)

            # Write edited config back to file
            write_file('/var/run/wpa_supplicant-11s.conf', conf, 'Failed to write wpa supplicant config')

            # Restart wpa supplicant
            cmd_restart_supplicant = 'wpa_supplicant -Dnl80211 -i' + self.args.mesh_interface + ' -c /var/run/wpa_supplicant-11s.conf -B'
            run_command(cmd_restart_supplicant, 'Failed to restart wpa supplicant')
            time.sleep(4)
            subprocess.call('iw dev', shell=True)

            # Validate outcome of switch frequency process
            self.current_frequency = get_mesh_freq()
            if self.current_frequency != self.target_frequency:
                print("Switch Unsuccessful") if self.args.debug else None
                self.recovering_switch_error()
            else:
                self.reset()
        except Exception as e:
            print(f"Switching frequency error occurred: {str(e)}") if self.args.debug else None

    def recovering_switch_error(self) -> None:
        """
        Handle recovering from a switch error by periodically attempting frequency switching.
        """
        self.time_last_scan = time.time()
        while self.running:
            current_time = time.time()
            # If periodic switch timer ended, switch frequency again
            if current_time - self.time_last_scan >= self.args.periodic_recovery_switch:
                self.switch_frequency()
                self.time_last_scan = current_time
                break

            time.sleep(0.01)

    def reset(self) -> None:
        """
        Reset Client FSM related attributes.
        """
        self.time_last_switch = 0

    def update_target_freq(self, received_target_freq):
        """
        Update the target mesh frequency.

        :param received_target_freq: The new target frequency to be set.
        """
        channel = map_freq_to_channel(received_target_freq)
        if channel in VALID_CHANNELS:
            self.target_frequency = received_target_freq

    def stop(self) -> None:
        """
        Stops all threads and closes the socket connection.
        """
        self.running = False
        # Close socket
        if self.socket:
            self.socket.close()
        # Join listen thread
        if self.listen_thread.is_alive():
            self.listen_thread.join()


def main():
    args = Options()

    host: str = args.jamming_osf_orchestrator
    port: int = args.port
    node_id: str = get_ipv6_addr('tun0')

    client = JammingDetectionClient(node_id, host, port)
    client.run()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Attempting to stop the clients.") if args.debug else None
        client.stop()
        print("Clients successfully stopped.") if args.debug else None


if __name__ == '__main__':
    main()
