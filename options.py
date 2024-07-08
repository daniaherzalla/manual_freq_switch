import argparse

VALID_CHANNELS = [36, 40, 44, 48, 149, 153, 157, 161]
# Note that DFS channel on the 5 GHz band are removed as they should not be used for communication


class Options:
    def __init__(self):
        self.json_file = 'freq.json'
        self.osf_orchestrator: str = 'fd01::1'
        self.port: int = 8080
        self.starting_channel: int = 36
        self.waiting_time: int = 15
        self.osf_interface: str = 'tun0'
        self.mesh_interface: str = 'wlp1s0'
        self.debug: bool = True
        self.periodic_recovery_switch: float = 20

    def parse_options(self) -> 'Options':
        parser = argparse.ArgumentParser(description='Arguments for training.')
        parser.add_argument('--json_file', type=str, default=self.json_file, help='JSON file from which to load the new frequency.')
        parser.add_argument('--osf_orchestrator', type=str, default=self.osf_orchestrator, help='IPv6 address of the OSF orchestrator.')
        parser.add_argument('--port', type=int, default=self.port, help='Port to connect to for orchestrator and clients communication.')
        parser.add_argument('--starting_channel', type=int, default=self.starting_channel, help='Starting channel to set the mesh to.')
        parser.add_argument('--waiting_time', type=int, default=self.waiting_time, help='Time interval in seconds.')
        parser.add_argument('--osf_interface', type=str, default=self.osf_interface, help='OSF interface name.')
        parser.add_argument('--mesh_interface', type=str, default=self.mesh_interface, help='Mesh interface name.')
        parser.add_argument('--debug', type=bool, default=self.debug, help='Use local random sampling of .csv as scan instead of the actual spectral scan.')
        parser.add_argument('--periodic_recovery_switch', type=float, default=self.periodic_recovery_switch,
                            help='How often to trigger switching channel after channel switch has failed.')
        args = parser.parse_args()

        self.json_file = args.json_file
        self.osf_orchestrator = args.osf_orchestrator
        self.port = args.port
        self.starting_channel = args.starting_channel
        self.waiting_time = args.waiting_time
        self.osf_interface = args.osf_interface
        self.mesh_interface = args.mesh_interface
        self.debug = args.debug
        self.periodic_recovery_switch = args.periodic_recovery_switch

        return self


def main():
    args = Options()
    args.parse_options()


if __name__ == "__main__":
    main()
