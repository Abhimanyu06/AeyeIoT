import os
import json
from dotenv import load_dotenv
import threading
from datetime import datetime, timedelta
import boto3

load_dotenv()

# Initialize S3 client
s3 = boto3.client('s3')
LOG_PATH = os.getenv('LOG_PATH', 'logs/')
json_path = os.getenv('json_path', "/home/rp/AeyeIoT/camera.json")


def get_second_latest_file(directory):
    # List all files in the directory
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    # Create a list of tuples (file, modification_time)
    files_with_times = [(f, os.path.getmtime(os.path.join(directory, f))) for f in files]
    print(files_with_times)
    # Sort the list by modification time in descending order
    sorted_files = sorted(files_with_times, key=lambda x: x[1], reverse=True)

    # Check if there are at least two files
    if len(sorted_files) < 2:
        return None

    # Return the second latest file
    second_latest_file = sorted_files[1][0]
    second_latest_file_path = os.path.join(directory, second_latest_file)
    
    return second_latest_file_path


def upload_logs_to_s3(device_id):
    second_latest = get_second_latest_file(LOG_PATH)
    if not second_latest:
        print("No files found or not enough files to get the second latest.")
        return
    
    print("Second latest file:", second_latest)

    # Get the current time in the desired timezone (UTC +5:30)
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hourly_folder = now.strftime('%Y-%m-%d')

    # Extract just the filename from the path for the S3 key
    filename = os.path.basename(second_latest)
    upload_s3_key = f"hospitals/{device_id}/{hourly_folder}/logs/{filename}"
    Aeye_current_log_upload_s3_key = f"hospitals/{device_id}/{hourly_folder}/logs/AeyeIoT.log"

    # Upload the file to S3
    try:
        s3.upload_file(second_latest, "aeye-test", upload_s3_key)
        s3.upload_file(LOG_PATH+'AeyeIoT.log', "aeye-test", Aeye_current_log_upload_s3_key)
        print("Upload successful!")
    except Exception as e:
        print(f"Failed to upload to S3: {e}")

# Example of how to call the function in a thread
def start_upload_thread(device_id):
    upload_thread = threading.Thread(target=upload_logs_to_s3, args=(device_id,))
    upload_thread.start()
    return upload_thread

# Example usage
if __name__ == "__main__":
    with open(json_path) as json_file:
        stream_data = json.load(json_file)

    device_id = stream_data.get("device_id", "")
    upload_thread = start_upload_thread(device_id)

    # Wait for the upload thread to complete before exiting
    upload_thread.join()  # This ensures the main thread waits for the background thread to finish
    print("Upload completed, main thread exiting.")
