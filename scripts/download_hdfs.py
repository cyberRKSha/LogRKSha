import os
import requests
import zipfile
from tqdm import tqdm

# URL for HDFS Dataset (Loghub)
DATASET_URL = "https://zenodo.org/records/8196385/files/HDFS_v1.zip"
TARGET_DIR = "data/hdfs"
ZIP_FILE = os.path.join(TARGET_DIR, "HDFS_v1.zip")

def download_file(url, filename):
    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024 # 1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
    
    with open(filename, 'wb') as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        print("ERROR, something went wrong")
    else:
        print(f"Downloaded {filename}")

def extract_file(zip_path, extract_to):
    print(f"Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print("Extraction complete.")

def main():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        
    if not os.path.exists(ZIP_FILE):
        print(f"Downloading HDFS dataset from {DATASET_URL}...")
        download_file(DATASET_URL, ZIP_FILE)
    else:
        print("HDFS zip file already exists. Skipping download.")
        
    # Check if extracted files exist
    if not os.path.exists(os.path.join(TARGET_DIR, "HDFS.log")):
        extract_file(ZIP_FILE, TARGET_DIR)
    else:
        print("HDFS.log already exists. Skipping extraction.")

if __name__ == "__main__":
    main()
