import subprocess
import time

def disconnect_and_forget():
    try:
        # Run the disconnect script in the background
        subprocess.Popen(['sudo', 'bash', '/home/rp/AeyeIoT/wifi-connect-headless-rpi/scripts/run.sh', '-d'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for 2 seconds before rebooting
        time.sleep(4)
        
        # Reboot the system
        subprocess.run(['sudo', 'reboot'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
       
    except subprocess.CalledProcessError as e:
        print(f"Error disconnecting or forgetting the network: {e}")

if __name__ == "__main__":
    disconnect_and_forget()
