import cv2
import os
import concurrent.futures
import threading
import requests
import json
import time
import asyncio
import aiohttp  # For async HTTP requests
from datetime import datetime

env_url = "https://6to69015t0.execute-api.us-east-1.amazonaws.com/test/"
json_path = "/home/rp/Aeye_iot/camera.json"
record_time = 180

# Define the codec and create VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'XVID')

def run_async(func, *args):
    """ Helper function to run async functions in a thread """
    asyncio.run(func(*args))


async def update_camera_status(device_id, cam_name, cam_status):
    test_url = f"{env_url}/device-camera-list/{device_id}?cam_name={cam_name}&status={cam_status}"
    async with aiohttp.ClientSession() as session:
        async with session.put(test_url) as response:
            if response.status == 200:
                print("Camera status updated successfully.")
            else:
                print(f"Failed to update camera status. Status code: {response.status}")



# Function to send POST request in a separate thread
def send_image(device_id, cam_name, image_bytes):
    while True:
        try:
            upload_image_api_url = f"{env_url}upload-image?device_id={device_id}&cam_name={cam_name}"

            headers = {'Content-Type': 'application/octet-stream'}
            requests.post(upload_image_api_url, headers=headers, data=image_bytes)
            print(f"Image uploaded successfully for {cam_name}")
            break
        except Exception as e:
            print(f"Error uploading file: {e}")
            continue

# Asynchronous function to send POST request
async def send_video(device_id, cam_name, file_name):
    upload_video_api_url = f"{env_url}upload-video?device_id={device_id}&cam_name={cam_name}"

    while True:
        try:
            async def fetch_presigned_url(session, url):
                while True:
                    async with session.get(url) as response:
                        if response.status == 503:
                            continue
                        else:
                            response_text = await response.text()
                            return json.loads(response_text).get("s3_sign_url")

            async def upload_file(session, url, file_path):
                headers = {'Content-Type': 'video/mp4'}
                with open(file_path, 'rb') as file_data:
                    async with session.put(url, headers=headers, data=file_data) as response:
                        if response.status == 200:
                            print(f"{file_path} uploaded successfully")
                            os.remove(file_path)
                        else:
                            print(f"Failed to upload file. HTTP Status Code: {response.status}")

            async with aiohttp.ClientSession() as session:
                presigned_url = await fetch_presigned_url(session, upload_video_api_url)
                await upload_file(session, presigned_url, file_name)

            break
        except Exception as e:
            print(f"Error uploading file: {e}")
            await asyncio.sleep(1)  # Optional: delay before retrying


# Function to record video
def record_video(device_id, cam_key, stream, fps):
    cap = None

    while True:
        if cap is None:
            cap = cv2.VideoCapture(stream)
            if not cap.isOpened():
                print(f"Error opening stream: {stream}. Retrying...")
                time.sleep(2)
                continue  # Retry initialization

        start_time = time.time()
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"/home/rp/Aeye_iot/videos/recording_{current_time}.mp4"

        out = cv2.VideoWriter(output_file, cv2.VideoWriter_fourcc(*'XVID'), fps, (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ))

        print(f"Recording started: {output_file}")

        while int(time.time() - start_time) < record_time:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame. Pausing recording.")
                out.release()
                cap.release()
                cap = None
                time.sleep(2)
                break

            out.write(frame)

        out.release()

        if ret:
            print(f"Recording saved: {output_file}")
            # Use threading for video upload to avoid blocking
            thread = threading.Thread(target=run_async, args=(send_video, device_id, cam_key, output_file))
            thread.daemon = True
            thread.start()
        time.sleep(2)  # Pause before restarting recording
    

# Function to process video streams
def process_stream(stream_data, cam_key, cam_details):
    device_id = stream_data['device_id']
    stream = cam_details["url"]
    cap = None
    max_retries = 10
    retry_count = 0
    stream_image_data = []

    asyncio.run(update_camera_status(device_id, cam_key, "Inactive"))
    stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Inactive"
    with open(json_path, 'w') as json_file:
        json.dump(stream_data, json_file, indent=4)

    # Retry loop for opening the stream
    while True:
        cap = cv2.VideoCapture(stream)
        if cap.isOpened():
            break
        else:
            print(f"Error opening stream: {stream}. Retrying... ({retry_count + 1}/{max_retries})")
            retry_count += 1
            time.sleep(1)
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # Start video recording in a separate thread
    thread = threading.Thread(target=record_video, args=(device_id, cam_key, stream, fps))
    thread.daemon = True
    thread.start()

    # Update stream status
    stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Active"
    asyncio.run(update_camera_status(device_id, cam_key, "Active"))
    with open(json_path, 'w') as json_file:
        json.dump(stream_data, json_file, indent=4)

    prev_gray = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print(f"Error reading frame from stream: {stream}. Retrying...")
            asyncio.run(update_camera_status(device_id, cam_key, "Inactive"))
            cap.release()
            retry_count = 0
            while True:
                cap = cv2.VideoCapture(stream)
                if cap.isOpened():
                    print(f"Reconnected to stream: {stream}")
                    break
                else:
                    retry_count += 1
                    print(f"Retrying to open stream... ({retry_count}/{max_retries})")
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
            print(f"Significant change detected from {cam_key}!")

            # If we have 5 frames, choose the most stable one and send it
            if len(stream_image_data) >= 5:
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
    # with open(json_path, 'w') as f:
    #     stream_data["camera_dict"] = {}
    #     stream_data["camera_dict"]["camera_details"] = response_data['camera_dict'].get("camera_details")
    #     stream_data["frame_change_count"] = response_data["camera_dict"].get('frame_change_count',7000)	
    #     json.dump(stream_data, f)

    print(stream_data)
    
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
                print(f"Error occurred in stream processing: {e}")


if __name__ == "__main__":
    asyncio.run(main())
