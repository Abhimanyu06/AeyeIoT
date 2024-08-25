import cv2
import os
import concurrent.futures
import threading
import requests
import json
import time
from datetime import datetime


env_url = "https://6to69015t0.execute-api.us-east-1.amazonaws.com/test/"
json_path = "camera.json"
record_time = 300


# Define the codec and create VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'XVID')


# Function to send POST request in a separate thread
def send_image(device_id, cam_name, image_bytes):
    while True:
        try:
            upload_image_api_url = f"{env_url}upload-image?device_id={device_id}&cam_name={cam_name}"

            headers = {'Content-Type': 'application/octet-stream'}
            requests.post(upload_image_api_url, headers=headers, data=image_bytes)
            break
        except Exception as e:
            print(f"Error uploading file: {e}")
            continue


# Function to send POST request in a separate thread
def send_video(device_id, cam_name, file_name):
    upload_video_api_url = f"{env_url}upload-video?device_id={device_id}&cam_name={cam_name}"

    while True:
        try:
            response = requests.get(upload_video_api_url)
            presigned_url = json.loads(response.text)["s3_sign_url"]

            # Upload the file using the presigned URL
            with open(file_name, 'rb') as file_data:
                headers = {
                'Content-Type': 'video/mp4'
                }
                response = requests.put(presigned_url, headers=headers, data=file_data)
                if response.status_code == 200:
                    print(f"{file_name} uploaded successfully ")
                    os.remove(file_name)
                else:
                    print(f"Failed to upload file. HTTP Status Code: {response.status_code}")
            break
        except Exception as e:
            print(f"Error uploading file: {e}")
            continue



def record_video(device_id, cam_key, stream, fps):
    cap = None

    while True:
        # Initialize capture device if not initialized
        if cap is None:
            cap = cv2.VideoCapture(stream)
            if not cap.isOpened():
                print(f"Error opening stream: {stream}. Retrying...")
                time.sleep(2)
                continue  # Retry initialization

        # Get the current time
        start_time = time.time()
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"videos/recording_{current_time}.mp4"

        # Define the VideoWriter object
        out = cv2.VideoWriter(output_file, cv2.VideoWriter_fourcc(*'mp4v'), fps, (
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
                cap = None  # Force reinitialization in the next loop iteration
                time.sleep(2)
                break

            out.write(frame)

        out.release()

        if ret:
            print(f"Recording saved: {output_file}")
            thread = threading.Thread(target=send_video, args=(device_id, cam_key, output_file))
            thread.daemon = True  # This makes the thread a daemon thread
            thread.start()

        else:
            print(f"Recording stopped due to frame capture failure. File saved until failure: {output_file}")
            thread = threading.Thread(target=send_video, args=(device_id, cam_key, output_file))
            thread.daemon = True  # This makes the thread a daemon thread
            thread.start()

        time.sleep(2)  # Wait a moment before restarting recording


# Function to process a video stream
def process_stream(stream_data, cam_key, cam_details):
    device_id = stream_data['device_id']
    frame_change_count = stream_data.get('frame_change_count', 8000)
    frame_count = 0
    stream = cam_details["url"]
    cap = None

    # Retry mechanism for opening the stream
    while cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(stream)
        if not cap.isOpened():
            print(f"Error opening stream: {stream}. Retrying...")
            stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Inactive"
            with open(json_path, 'w') as json_file:
                json.dump(stream_data, json_file, indent=4)
            time.sleep(1)  # Wait for 5 seconds before retrying


    # Frame per second of the stream
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    #     executor.submit(record_video, device_id, cam_key, stream, fps)
    thread = threading.Thread(target=record_video, args=(device_id, cam_key, stream, fps))
    thread.daemon = True  # This makes the thread a daemon thread
    thread.start()

    stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Active"
    with open(json_path, 'w') as json_file:
        json.dump(stream_data, json_file, indent=4)
    
    prev_gray = None

    while True:
        ret, frame = cap.read()
        
        if not ret:
            print(f"Error reading frame from stream: {stream}. Retrying...")
            cap.release()
            cap = None
            while cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(stream)
                if not cap.isOpened():
                    print(f"Error opening stream: {stream}. Retrying...")
                    stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Inactive"
                    with open(json_path, 'w') as json_file:
                        json.dump(stream_data, json_file, indent=4)
                    time.sleep(1)  # Wait for 5 seconds before retrying
            stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Inactive"
            with open(json_path, 'w') as json_file:
                json.dump(stream_data, json_file, indent=4)
            continue

        if prev_gray is None:
            prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            continue
        
        frame_count += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Compute the absolute difference between the current frame and the previous frame
        frame_diff = cv2.absdiff(prev_gray, gray)
        
        # Threshold the difference
        _, thresh = cv2.threshold(frame_diff, 30, 255, cv2.THRESH_BINARY)
        
        # Count the number of non-zero pixels (i.e., the number of changed pixels)
        change_count = cv2.countNonZero(thresh)

        #cv2.imshow("frame", frame)
        # If the number of changed pixels is above a certain threshold, a significant change has occurred
        if change_count > frame_change_count:  # You may need to adjust this threshold
            print(f"Significant change detected from {cam_key} in frame {frame_count}!")
            stream_data["camera_dict"]["camera_details"][cam_key]["status"] = "Active"
            with open(json_path, 'w') as json_file:
                json.dump(stream_data, json_file, indent=4)

            # Encode the image to a byte string
            _, buffer = cv2.imencode('.jpg', frame)
            image_bytes = buffer.tobytes()
            #cv2.imshow("diff", frame)

            # Create a ThreadPoolExecutor for the API calls
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Submit the API call to the executor
                executor.submit(send_image, device_id, cam_key, image_bytes)
        
        # Update the previous frame
        prev_gray = gray

        # Exit on pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release the video capture object and close all OpenCV windows
    cap.release()
    cv2.destroyAllWindows()

stream_data = {}

# Opening json file
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

print(stream_data)

# Use ThreadPoolExecutor to process all streams in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(process_stream, stream_data,  cam_key, cam_details) for cam_key, cam_details in stream_data["camera_dict"]["camera_details"].items()]

# Wait for all threads to complete
for future in concurrent.futures.as_completed(futures):
    try:
        future.result()
    except Exception as e:
        print(e)