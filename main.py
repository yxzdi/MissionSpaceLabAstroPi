# Import necessary libraries
from picamera import PiCamera  # Import PiCamera for Raspberry Pi camera functionality
from time import sleep  # Import sleep to introduce delay
from datetime import datetime, timedelta  # Import datetime for timestamp calculation
from pathlib import Path  # Import Path for file path handling
from PIL import Image  # Import Image from PIL for image processing
import os  # Import os for operating system related functionalities
import csv  # Import csv for CSV file handling
import math  # Import math for mathematical calculations
from orbit import ISS

iss = ISS()

def convert(angle):
    """
    Convert a `skyfield` Angle to an EXIF-appropriate
    representation (rationals)
    e.g. 98° 34' 58.7 to "98/1,34/1,587/10"

    Return a tuple containing a boolean and the converted angle,
    with the boolean indicating if the angle is negative.
    """
    sign, degrees, minutes, seconds = angle.signed_dms()
    exif_angle = f'{degrees:.0f}/1,{minutes:.0f}/1,{seconds*10:.0f}/10'
    return sign < 0, exif_angle



# Function to capture images at regular intervals
def capture_images(image_path, max_storage_size=250, max_images=42, max_capture_duration=480, capture_interval=5):
    try:
        # Initialize the PiCamera object
        camera = PiCamera()
        # Set camera resolution
        camera.resolution = (1280, 720)
        # Set camera framerate
        camera.framerate = 15
        # Set exposure mode to auto
        camera.exposure_mode = 'auto'
        # Set auto white balance mode
        camera.awb_mode = 'auto'
# Calibration required in order for the program to work under the conditions on the ISS

        def custom_capture(image):
            """Use `camera` to capture an `image` file with lat/long EXIF data."""
            location = iss.coordinates()

            # Convert the latitude and longitude to EXIF-appropriate representations
            south, exif_latitude = convert(location.latitude)
            west, exif_longitude = convert(location.longitude)

            # Set the EXIF tags specifying the current location
            camera.exif_tags['GPS.GPSLatitude'] = exif_latitude
            camera.exif_tags['GPS.GPSLatitudeRef'] = "S" if south else "N"
            camera.exif_tags['GPS.GPSLongitude'] = exif_longitude
            camera.exif_tags['GPS.GPSLongitudeRef'] = "W" if west else "E"

            # Capture the image
            camera.capture(image)

        # Initialize lists to store captured images and timestamps
        images = []
        timestamps = []
        # Variable to track total storage size of captured images - to not exceed the 250MB file limit
        total_storage_size = 0
        # Get start time for capturing images
        start_time = datetime.now()

        # Loop until total storage size reaches maximum or maximum images captured or maximum capture duration reached
        while total_storage_size < max_storage_size and len(images) < max_images:
            # Capture timestamp
            timestamp = datetime.now()
            # Generate image name using timestamp
            image_name = f"image_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            # Define image file path
            image_file = f"{image_path}/{image_name}"

            # Capture image and save
            custom_capture(image_file)
            print(f"Image captured: {image_name}")

            # Append image file path and timestamp to lists
            images.append(image_file)
            timestamps.append(timestamp)

            # Calculate total storage size of captured images
            total_storage_size += os.path.getsize(image_file) / (1024 * 1024)  # Convert to MB

            # Check if maximum capture duration reached
            if (timestamp - start_time).total_seconds() > max_capture_duration:
                break

            # Introduce delay between captures
            sleep(capture_interval)

        # Return captured images and timestamps
        return images, timestamps

    except Exception as e:
        # Handle any exceptions and print error message
        print(f"Error: {e}")
        return None, None

    finally:
        # Close the camera connection
        camera.close()

# Function to extract GPS coordinates and timestamp from image EXIF data
def extract_coordinates_and_timestamp(image_path):
    try:
        # Open image file using PIL
        img = Image.open(image_path)
        # Extract EXIF data from image
        exif_data = img._getexif()

        # Check if GPS info and timestamp are available in EXIF data
        if 0x8825 in exif_data and 0x9003 in exif_data:
            # Extract GPS information
            gps_info = exif_data[0x8825]
            latitude = gps_info[2][0] + gps_info[2][1] / 60 + gps_info[2][2] / 3600
            longitude = gps_info[4][0] + gps_info[4][1] / 60 + gps_info[4][2] / 3600

            # Check direction of latitude and longitude
            if gps_info[3] == 'S':
                latitude = -latitude
            if gps_info[1] == 'W':
                longitude = -longitude

            # Extract timestamp from EXIF data
            timestamp_str = exif_data[0x9003]
            # Convert timestamp string to datetime object
            timestamp = datetime.strptime(timestamp_str, '%Y:%m:%d %H:%M:%S')

            # Return latitude, longitude, and timestamp
            return latitude, longitude, timestamp

        else:
            # Print message if GPS info or timestamp not found in image
            print("No GPS information or DateTimeOriginal found in the image.")
            return None

    except Exception as e:
        # Handle any exceptions and print error message
        print(f"Error: {e}")
        return None

# Function to calculate haversine distance between two GPS coordinates
def haversine_distance(lat1, lon1, lat2, lon2):
    # Adjusted what would be the radius of the Earth to account for the ISS's orbit height 
    R = 6779
    # Convert coordinates to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    # Calculate differences in coordinates
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    # Calculate distance
    distance = R * c
    return distance

# Function to calculate speed using distance and time difference
def calculate_speed(distance, time_difference):
    # Convert time difference to seconds
    time_in_seconds = time_difference.total_seconds()
    # Calculate speed
    speed = distance / time_in_seconds
    return abs(speed)

# Function to log data to CSV file - not required as competition only wants numeric output
'''def log_data_to_csv(data, csv_file):
    # Open CSV file for writing
    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        # Write header row
        writer.writerow(["Iteration", "Distance (km)", "Time Difference (seconds)", "Speed (km/s)"])
        # Write data rows
        for i, (distance, time_difference, speed) in enumerate(data, start=1):
            writer.writerow([i, distance, time_difference.total_seconds(), speed])'''

# Function to log average speed to text file
def log_average_speed_to_txt(avg_speed, txt_file):
    # Open text file for writing
    with open(txt_file, 'w') as file:
        # Write average speed in km/s (as per rulebook example) to file (to 5sf)
        file.write(f"{avg_speed:.4f} km/s\n")

# Main function
def main():
    # Get base folder path
    base_folder = Path(__file__).parent.resolve()
    # Define image save path
    image_save_path = base_folder
    # Define text file path
    txt_file = base_folder / "result.txt"

    # Capture images
    images, timestamps = capture_images(image_save_path, capture_interval=5)

    if images and timestamps:
        # Initialize list to store speed data
        speed_data = []

        # Iterate through images to calculate speed
        for i in range(1, len(images)):
            # Extract coordinates and timestamps from consecutive images
            data1 = extract_coordinates_and_timestamp(images[i - 1])
            data2 = extract_coordinates_and_timestamp(images[i])

            # Calculate distance and speed if data is available for both images
            if data1 and data2:
                latitude1, longitude1, timestamp1 = data1
                latitude2, longitude2, timestamp2 = data2

                # Skip calculation if images are identical or coordinates are the same or timestamps are the same (so as to not return zero and lower the average speed)
                if images[i - 1] == images[i] or haversine_distance(latitude1, longitude1, latitude2,
                                                                     longitude2) == 0 or (
                        timestamp2 - timestamp1).total_seconds() == 0:
                    continue

                # Calculate distance between coordinates - - takes into account changes in the ISS speed as a result
                distance = haversine_distance(latitude1, longitude1, latitude2, longitude2)
                # Calculate time difference between timestamps
                time_difference = timestamp2 - timestamp1
                try:
                    # Calculate speed
                    speed = calculate_speed(distance, time_difference)

                    # Append distance, time difference, and speed to speed data list
                    speed_data.append((distance, time_difference, speed))
                except ZeroDivisionError: pass

        # Calculate average speed
        avg_speed = 0
        if len(speed_data) > 0:
            avg_speed = sum(entry[2] for entry in speed_data) / len(speed_data)

        # Print average speed
        print(f"Average Speed: {avg_speed:.4f} km/s")

        # Log average speed to text file
        log_average_speed_to_txt(avg_speed, txt_file)

        # Remove older images if number of images exceeds limit of 42 (as only 42 images can be retained)
        while len(images) > 42:
            os.remove(images.pop(0))

# Execute main function if script is run directly
if __name__ == "__main__":
    main()

