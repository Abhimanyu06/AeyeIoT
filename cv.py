import cv2
import uuid
import os
from dotenv import load_dotenv
import concurrent.futures
import threading
import requests
import json
import time
import asyncio
import aiohttp  # For async HTTP requests
from datetime import datetime
from stream import start_stream_capture
import logging
from logging.handlers import RotatingFileHandler

load_dotenv()

LOG_PATH = os.getenv('LOG_PATH', "logs/")
env_url = os.getenv('env_url', "https://6to69015t0.execute-api.us-east-1.amazonaws.com/test/")
json_path = os.getenv('json_path', "/home/rp/AeyeIoT/camera.json")
BUCKET_NAME = os.getenv('BUCKET_NAME', 'aeye-stream')

log_handler = RotatingFileHandler(LOG_PATH+'AeyeIoT.log', maxBytes=1000000, backupCount=5)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_event(level, message):
    log_entry = {
        'level': level,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    logging.log(level, json.dumps(log_entry))


# Define the codec and create VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'XVID')

def run_async(func, *args):
    """ Helper function to run async functions in a thread """
    asyncio.run(func(*args))


# Function to send POST request in a separate thread
def send_image(device_id, cam_name, image_bytes):
    while True:
        try:
            upload_image_api_url = f"{env_url}upload-image?device_id={device_id}&cam_name={cam_name}"

            headers = {'Content-Type': 'application/octet-stream'}
            requests.post(upload_image_api_url, headers=headers, data=image_bytes)
            log_event(logging.INFO, f"Image of {device_id}, uploaded successfully for {cam_name}")
            break
        except Exception as e:
            log_event(logging.ERROR, f"Error uploading file: {str(e)}")
            continue

# Function to process video streams
def process_stream(stream_data, cam_key, cam_details):
    device_id = stream_data['device_id']
    stream = cam_details["url"]
    cap = None
    retry_count = 0
    stream_image_data = []

    # Retry loop for opening the stream
    while True:
        cap = cv2.VideoCapture(stream)
        if cap.isOpened():
            break
        else:
            log_event(logging.WARNING, f"Error opening stream for {cam_key}: with {stream}. Retrying...")
            retry_count += 1
            stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Inactive"
            # with open(json_path, 'w') as json_file:
            #     json.dump(stream_data, json_file, indent=4)
            time.sleep(5)
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # Start video recording in a separate thread
    cam_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, cam_key))
    cam_path = device_id+"/"+cam_id
    thread = threading.Thread(target=start_stream_capture, args=(cam_path, stream))
    thread.daemon = True
    thread.start()

    # Update stream status
    # stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Active"
    # stream_data["camera_dict"]["camera_details"][cam_key]["cam_id"] = cam_id
    # stream_data["camera_dict"]["camera_details"][cam_key]["public_url"] = f"https://{BUCKET_NAME}.s3.amazonaws.com/{device_id}/{cam_id}/"
    
    # with open(json_path, 'w') as json_file:     
    #     json.dump(stream_data, json_file, indent=4)

    prev_gray = None

    while True:
        ret, frame = cap.read()
        if not ret:
            log_event(logging.WARNING, f"Error reading frame for {cam_key}: with {stream}. Retrying...")
            cap.release()
            retry_count = 0
            while True:
                cap = cv2.VideoCapture(stream)
                if cap.isOpened():
                    log_event(logging.INFO, f"Reconnected to stream: {stream}")
                    break
                else:
                    retry_count += 1
                    time.sleep(1)
            continue

        # Process frame differences to detect significant changes
        if prev_gray is None:
            prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(frame_diff, 30, 255, cv2.THRESH_BINARY)
        change_count = cv2.countNonZero(thresh)

        # If significant change is detected, store the frame for analysis
        if change_count > stream_data.get('frame_change_count', 8000):
            stream_image_data.append((frame, change_count))
            # If we have 5 frames, choose the most stable one and send it
            if len(stream_image_data) >= 5:
                log_event(logging.INFO, f"Significant change detected from {cam_key}!")
                most_stable_frame = min(stream_image_data, key=lambda x: x[1])[0]

                # Encode the most stable frame to JPEG
                _, buffer = cv2.imencode('.jpg', most_stable_frame)
                image_bytes = buffer.tobytes()

                # Clear the frame buffer after sending the image
                stream_image_data.clear()

                # Send the image in a separate thread to avoid blocking
                thread = threading.Thread(target=send_image, args=(device_id, cam_key, image_bytes))
                thread.daemon = True
                thread.start()

        prev_gray = gray

    cap.release()


# Main async function to process streams
async def main():
    with open(json_path) as json_file:
        stream_data = json.load(json_file)

    device_id = stream_data.get("device_id", "")

    camera_list_url = f"{env_url}device-camera-list/{device_id}"

    response = requests.request("GET", camera_list_url)
    response_data = response.json()

    # store json in file
    with open(json_path, 'w') as f:
        stream_data["camera_dict"] = {}
        stream_data["camera_dict"]["camera_details"] = response_data['camera_dict'].get("camera_details")
        stream_data["frame_change_count"] = response_data["camera_dict"].get('frame_change_count',7000)	
        json.dump(stream_data, f)

    # Determine the number of workers based on the number of cameras
    max_worker_count = len(stream_data["camera_dict"]["camera_details"].keys())

    # Start processing streams using a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_worker_count) as executor:
        futures = []

        # Introduce a delay between thread starts
        for cam_key, cam_details in stream_data["camera_dict"]["camera_details"].items():
            # Submit each thread for processing with a delay between submissions
            futures.append(executor.submit(process_stream, stream_data, cam_key, cam_details))
            
            # Add a delay between starting threads, e.g., 2 seconds
            time.sleep(1)

        # Collect results from completed threads
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log_event(logging.ERROR, f"Error occurred in stream processing: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
