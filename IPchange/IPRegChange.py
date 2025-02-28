import subprocess
import time
import requests
import random

def get_regions():
    """Fetch available PIA regions."""
    result = subprocess.run(["piactl", "get", "regions"], capture_output=True, text=True)
    regions = result.stdout.strip().split("\n")
    return regions if regions else ["auto"]

def change_ip():
    # Disconnect PIA
    subprocess.run(["piactl", "disconnect"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5)

    # Get all available regions
    regions = get_regions()

    # Select a random region
    selected_region = random.choice(regions)
    print(f"Changing region to: {selected_region}")

    # Change region
    subprocess.run(["piactl", "set", "region", selected_region], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Connect to the selected region
    subprocess.run(["piactl", "connect"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5)

    # Get new IP
    new_ip = requests.get("https://ifconfig.me").text.strip()
    print(f"New IP Address: {new_ip}")

if __name__ == "__main__":
    change_ip()
