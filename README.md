# AeyeIoT

The Aeye project is an innovative IoT solution designed to manage and process multiple camera streams using a dedicated hardware device. This device operates on an Ubuntu-based operating system, providing a robust and flexible platform for handling real-time video data.
## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)

## Features

- **Multi-Camera Support:** Seamlessly manage multiple camera streams in real time.
- **Real-Time Processing:** Analyze video feeds for motion detection, object recognition, and more.


## Installation

To install and set up the Aeye project, follow these steps:

1. Clone the repository:

   ```bash
   git clone https://github.com/Abhimanyu06/AeyeIoT.git
   ```
2. Navigate to the project directory:

   ```bash 
   cd AeyeIoT
   ```
3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```
## Setup

Open the terminal and create a `.env` file:
   ```bash
   sudo nano .env
   ```

In the .env file, add the following lines:
   ```bash
TOKEN="your_github_token"
ENV_URL="your_env_api_url"
JSON_PATH="/home/rp/AeyeIoT/camera.json"
LOCAL_OUTPUT_PATH="/home/rp/AeyeIoT/stream_output/"
BUCKET_NAME="your_bucket_name"
   ```
Replace the placeholder values with your actual configuration settings.

Open the crontab configuration:

   ```bash
   crontab -e
   ```
Add the following line to the crontab file:
   ```bash
   @reboot chmod +x /home/rp/AeyeIoT/aeye_run.sh && /home/rp/AeyeIoT/aeye_run.sh
   ```

## Usage
To initiate the AeyeIoT application, reboot your system:
```bash
sudo reboot
```
After the system restarts, the AeyeIoT application will start automatically.

After rebooting, the Aeye IoT device will open its Wi-Fi network, which can be connected to a mobile application.
