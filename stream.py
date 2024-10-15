import os
from dotenv import load_dotenv
import subprocess
import boto3
import json
from datetime import datetime, timedelta
import time
import threading
import concurrent.futures
import logging
from logging.handlers import RotatingFileHandler

load_dotenv()


s3 = boto3.client('s3')

LOG_PATH = os.getenv('LOG_PATH', 'logs/')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'aeye-stream')

# Local output path
LOCAL_OUTPUT_PATH = os.getenv('LOCAL_OUTPUT_PATH', '/home/rp/AeyeIoT/stream_output/')

# Ensure the output directory exists
os.makedirs(LOCAL_OUTPUT_PATH, exist_ok=True)

# Modify the log format to exclude leading zeros in year, month, day, hour, minutes, and seconds
log_handler = RotatingFileHandler(LOG_PATH+'AeyeIoT.log', maxBytes=1000000, backupCount=5)
logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S'  # Custom date format without leading zeros
)

def log_event(level, message):
    log_entry = {
        'level': level,
        'message': message,
        'timestamp': datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    }
    logging.log(level, json.dumps(log_entry))


def get_latest_file_in_s3_folder(bucket_name, s3_folder):
    """Get the latest file in the specified S3 folder."""
    # List objects in the specified S3 folder
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_folder)
    if 'Contents' in response:
        # Extract filenames
        files = [obj['Key'] for obj in response['Contents']]
        return files
    else:
        files = []
        return files

def upload_to_s3(file_path, s3_folder, all_files_s3):
    """Upload file to the specified S3 folder."""
    s3_key = os.path.join(s3_folder, os.path.basename(file_path))
    try:
        if file_path.endswith(".m3u8"):
            s3.upload_file(file_path, BUCKET_NAME, s3_key)

        elif file_path.endswith(".ts"):
            if s3_key not in all_files_s3:
                s3.upload_file(file_path, BUCKET_NAME, s3_key)
                os.remove(file_path)

    except Exception as e:
        log_event(logging.ERROR, f"Error uploading {file_path}: {str(e)}")

def create_hourly_folder():
    """Create a folder for the current hour in GMT +5:30."""
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    hourly_folder = now.strftime('%-Y/%-m/%-d/%-H')
    return hourly_folder

def upload_files_in_background(cam_path, local_hourly_folder, hourly_folder):
    """Continuously upload new files to S3 in the background."""
    file_m3u8 = ""
    uploaded_files = set()

    s3_folder = os.path.join(cam_path, hourly_folder)
    all_files_s3 = get_latest_file_in_s3_folder(BUCKET_NAME, s3_folder)
    while True:
        # List all files currently in the folder
        current_files = set(os.listdir(local_hourly_folder))
        new_files = current_files - uploaded_files
        if len(new_files) > 1:
            new_files.remove(max(new_files))
            # Upload new files using a ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for file in new_files:
                    if file.endswith(".m3u8"):
                        file_m3u8 = file
                    file_path = os.path.join(local_hourly_folder, file)
                    executor.submit(upload_to_s3, file_path, s3_folder, all_files_s3)
                    executor.submit(upload_to_s3, os.path.join(local_hourly_folder, file_m3u8), s3_folder, all_files_s3)

            # Add new files to the uploaded set
            uploaded_files.update(new_files)

        # Sleep for a short interval to avoid busy-waiting
        time.sleep(1)

def start_stream_capture(cam_path, RTSP_URL):
    """Capture the RTSP stream and split into .m3u8 and .ts segments."""
    while True:
        # Create a new hourly folder
        hourly_folder = create_hourly_folder()
        local_hourly_folder = os.path.join(LOCAL_OUTPUT_PATH, cam_path + "/" + hourly_folder)
        os.makedirs(local_hourly_folder, exist_ok=True)

        current_time = datetime.now().strftime('%-H%M%S')  # Custom format without leading zeros
        m3u8_file = datetime.now().strftime('%-H')
        # File template for segmenting with minute and second in filename
        segment_file = os.path.join(local_hourly_folder, f'{current_time}_%03d.ts')
        m3u8_file = os.path.join(local_hourly_folder, f'{m3u8_file}.m3u8')
        
        # Start the upload process in the background
        upload_thread = threading.Thread(target=upload_files_in_background, args=(cam_path, local_hourly_folder, hourly_folder))
        upload_thread.start()

        # FFmpeg command to split the stream
        command = [
            'ffmpeg',
            '-fflags', '+genpts',  # Generate new presentation timestamps to ensure correct ordering
            '-use_wallclock_as_timestamps', '1',  # Use wall clock time to resync timestamps
            '-i', RTSP_URL,  # Input RTSP stream
            '-c:v', 'copy',  # Copy the video codec (to avoid re-encoding)
            '-c:a', 'aac',   # Encode audio with AAC
            '-r', '25',  # Force constant frame rate (adjust to your stream's native frame rate if needed)
            '-vsync', '1',  # Make FFmpeg adjust for any potential time base mismatch
            '-hls_time', '8',  # Segment duration (in seconds)
            '-hls_list_size', '0',  # Do not remove segments from the .m3u8 file
            '-hls_flags', 'append_list+delete_segments+program_date_time', 
            '-hls_segment_filename', segment_file,  # Template for .ts files
            m3u8_file  # Output .m3u8 file
        ]

        log_event(logging.INFO, f"Starting stream capture for folder {hourly_folder}")

        subprocess.Popen(command)  # Start the FFmpeg process

        # Wait for the next hour to start capturing
        time.sleep(3600)  # Wait until the next hour starts
