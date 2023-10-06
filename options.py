import argparse
import os
import re
from typing import List

VALID_CHANNELS = [36, 40, 44, 48, 149, 153, 157, 161]
# Note that DFS channel on the 5 GHz band are removed as they should not be used for communication


class Options:
    def __init__(self):
        self.jamming_osf_orchestrator: str = 'fd01::1'
        self.port: int = 8080
        self.starting_channel: int = 36
        self.waiting_time: int = 15
        self.channels5: List[int] = [36, 40, 44, 48, 149, 153, 157, 161]
        self.osf_interface: str = 'tun0'
        self.mesh_interface: str = 'wlp1s0'
        self.debug: bool = True
        self.periodic_recovery_switch: float = 20

    def validate_configuration(self) -> bool:
        """
        Validate that device and options file configurations are compatible for jamming detection.

        :return: A boolean to denote whether the device and parameter configurations are valid.
        """
        valid = True

        # Check that mesh is set to 20mhz
        try:
            iw_output = os.popen('iw dev').read()
            iw_output = re.sub('\s+', ' ', iw_output).split(' ')

            # Extract interface sections from iw_output
            idx_list = [idx - 1 for idx, val in enumerate(iw_output) if val == "Interface"]
            if len(idx_list) > 1:
                idx_list.pop(0)

            # Calculate the start and end indices for interface sections
            start_indices = [0] + idx_list
            end_indices = idx_list + ([len(iw_output)] if idx_list[-1] != len(iw_output) else [])

            # Use zip to create pairs of start and end indices, and extract interface sections
            iw_interfaces = [iw_output[start:end] for start, end in zip(start_indices, end_indices)]

            # Get mesh interface channel width
            for interface_list in iw_interfaces:
                if "mesh" in interface_list:
                    channel_width_index = interface_list.index("width:") + 1
                    channel_width = re.sub("[^0-9]", "", interface_list[channel_width_index]).split()[0]
                    if channel_width != "20":
                        print("Mesh interface channel width must be set to 20 MHz.")
                        valid = False
                    break
                else:
                    print("No mesh interface") if self.debug else None
        except Exception as e:
            print(e) if self.debug else None

        # Check that list of channels does not include any DFS channels
        if not all(channel in VALID_CHANNELS for channel in self.channels5):
            print("5 GHz channels must be of the following: (36,40,44,48,149,153,157,161)")
            valid = False

        # Return validity after all checks performed
        return valid

    def parse_options(self) -> 'Options':
        parser = argparse.ArgumentParser(description='Arguments for training.')
        parser.add_argument('--jamming_osf_orchestrator', type=str, default=self.jamming_osf_orchestrator, help='IPv6 address of the jamming OSF orchestrator.')
        parser.add_argument('--port', type=int, default=self.port, help='Port to connect to for orchestrator and clients jamming detection communication.')
        parser.add_argument('--starting_channel', type=int, default=self.starting_channel, help='Starting channel to set the mesh to.')
        parser.add_argument('--waiting_time', type=int, default=self.waiting_time, help='Time interval in seconds.')
        parser.add_argument('--channels5', type=lambda x: [int(i) for i in x.split(',')], default=self.channels5,
                            help='Available channels on the 5GHz. Provide comma-separated values (e.g., 36,40,44,48,149,153,157,161).')
        parser.add_argument('--osf_interface', type=str, default=self.osf_interface, help='OSF interface name.')
        parser.add_argument('--mesh_interface', type=str, default=self.mesh_interface, help='Mesh interface name.')
        parser.add_argument('--debug', type=bool, default=self.debug, help='Use local random sampling of .csv as scan instead of the actual spectral scan.')
        parser.add_argument('--periodic_recovery_switch', type=float, default=self.periodic_recovery_switch,
                            help='How often to trigger switching channel after channel switch has failed.')
        args = parser.parse_args()

        self.jamming_osf_orchestrator = args.jamming_osf_orchestrator
        self.port = args.port
        self.starting_channel = args.starting_channel
        self.waiting_time = args.waiting_time
        self.channels5 = args.channels5
        self.osf_interface = args.osf_interface
        self.mesh_interface = args.mesh_interface
        self.debug = args.debug
        self.periodic_recovery_switch = args.periodic_recovery_switch

        # Validate user input parameter
        if not self.validate_configuration():
            raise Exception("Please adjust the jamming detection configuration according to the above.")

        return self


def main():
    args = Options()
    args.parse_options()


if __name__ == "__main__":
    main()
