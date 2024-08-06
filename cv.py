import cv2
import concurrent.futures
import requests
import json
import time

# Opening json file
with open('camera_list.json') as json_file:
    stream_data = json.load(json_file)

device_id = stream_data["device_id"]

camera_list_url = f"https://kw78036oma.execute-api.us-east-1.amazonaws.com/dev/device-camera-list/{device_id}"

response = requests.request("GET", camera_list_url)

# store json in file
with open('camera_list.json', 'w') as f:
    json.dump(response.json(), f)

response = response.json()


api_url = f"https://kw78036oma.execute-api.us-east-1.amazonaws.com/dev/upload-image?device_id={device_id}"


# Function to send POST request in a separate thread
def send_image(image_bytes):
    headers = {'Content-Type': 'application/octet-stream'}
    response = requests.post(api_url, device_id, headers=headers, data=image_bytes)
    print(response.text)

# Function to process a video stream
def process_stream(cam_key, cam_details):
    frame_count = 0
    stream = cam_details["url"]
    cap = None

    # Retry mechanism for opening the stream
    while cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(stream)
        if not cap.isOpened():
            print(f"Error opening stream: {stream}. Retrying...")
            response["camera_dict"][cam_key]["status"] = "Inactive"
            with open('camera.json', 'w') as json_file:
                json.dump(response, json_file, indent=4)
            time.sleep(1)  # Wait for 5 seconds before retrying

    response["camera_dict"][cam_key]["status"] = "Active"
    with open('camera.json', 'w') as json_file:
        json.dump(response, json_file, indent=4)
    
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
                    response["camera_dict"][cam_key]["status"] = "Inactive"
                    with open('camera.json', 'w') as json_file:
                        json.dump(response, json_file, indent=4)
                    time.sleep(1)  # Wait for 5 seconds before retrying
            response["camera_dict"][cam_key]["status"] = "Inactive"
            with open('camera.json', 'w') as json_file:
                json.dump(response, json_file, indent=4)
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

        cv2.imshow("frame", frame)
        
        # If the number of changed pixels is above a certain threshold, a significant change has occurred
        if change_count > 7000:  # You may need to adjust this threshold
            print(f"Significant change detected from {cam_key} in frame {frame_count}!")
            response["camera_dict"][cam_key]["status"] = "Active"
            with open('camera.json', 'w') as json_file:
                json.dump(response, json_file, indent=4)

            # Encode the image to a byte string
            _, buffer = cv2.imencode('.jpg', frame)
            image_bytes = buffer.tobytes()
            cv2.imshow("diff", frame)

            # Create a ThreadPoolExecutor for the API calls
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Submit the API call to the executor
                executor.submit(send_image, image_bytes)
        
        # Update the previous frame
        prev_gray = gray

        # Exit on pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Release the video capture object and close all OpenCV windows
    cap.release()
    cv2.destroyAllWindows()


# Use ThreadPoolExecutor to process all streams in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(process_stream, cam_key, cam_details) for cam_key, cam_details in response["camera_dict"].items()]

# Wait for all threads to complete
for future in concurrent.futures.as_completed(futures):
    try:
        future.result()
    except Exception as e:
        print(e)
