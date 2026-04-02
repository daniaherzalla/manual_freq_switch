# Manual Channel Switching
Switch mesh frequency upon manual file change. CSA sent over OSF to connected clients.

1. Set configuration in ```options.py```
2. Run ```setup.py``` on all nodes
3. Edit ```freq.json``` to set new frequency

![manual_freq_switch](https://github.com/user-attachments/assets/f01452df-ef72-407f-b526-340f4852052c)

**Demo setup:**
- **Left terminal**: Client node communication module
- **Right terminals**: Server node communication module
  - *Top*: Client instance running
  - *Bottom*: Server instance tracked via `server.log`

The video demonstrates manual frequency switching propagating to all connected clients.
