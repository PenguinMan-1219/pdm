import os
import requests
import threading
from queue import Queue, Empty
from urllib.parse import urlparse
from tqdm import tqdm

MIN_CHUNK_SIZE = 5 * 1024 * 1024  
MAX_THREADS = 16                   
BUFFER_SIZE = 8192                 

def download_chunk(url, start_byte, end_byte, in_progress_path, progress_queue):
    headers = {'Range': f'bytes={start_byte}-{end_byte}'}
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()

        with open(in_progress_path, 'r+b') as f:
            f.seek(start_byte)
            for chunk in response.iter_content(chunk_size=BUFFER_SIZE):
                if chunk:  
                    f.write(chunk)
                    progress_queue.put(len(chunk))
    except Exception as e:
        progress_queue.put(f"ERROR: {str(e)}")
        raise

def calculate_threads(total_size, supports_ranges):
    if not supports_ranges or total_size < MIN_CHUNK_SIZE:
        return 1

    calculated_threads = total_size // MIN_CHUNK_SIZE
    return min(MAX_THREADS, max(2, calculated_threads))

def main():
    url = input("Enter the download URL: ").strip()
    download_dir = input("Enter the download directory: ").strip()

    os.makedirs(download_dir, exist_ok=True)

    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path) or "downloaded_file"
    in_progress_path = os.path.join(download_dir, f"{filename}.pdm")
    final_path = os.path.join(download_dir, filename)

    try:

        response = requests.head(url, allow_redirects=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        supports_ranges = response.headers.get('accept-ranges', 'none') == 'bytes'

        if total_size <= 0:
            raise ValueError("Server didn't provide valid content-length")

        num_threads = calculate_threads(total_size, supports_ranges)
        print(f"Using {num_threads} thread{'s' if num_threads > 1 else ''} for download")

        with open(in_progress_path, 'wb') as f:
            f.truncate(total_size)

        progress_queue = Queue()
        threads = []
        chunk_size = total_size // num_threads

        for i in range(num_threads):
            start = i * chunk_size
            end = (start + chunk_size - 1) if i < (num_threads - 1) else (total_size - 1)

            thread = threading.Thread(
                target=download_chunk,
                args=(url, start, end, in_progress_path, progress_queue)
            )
            thread.start()
            threads.append(thread)

        with tqdm(total=total_size, unit='B', unit_scale=True, 
                 unit_divisor=1024, desc=filename) as pbar:
            while any(t.is_alive() for t in threads):
                try:
                    while True:
                        item = progress_queue.get(timeout=0.1)
                        if isinstance(item, str) and item.startswith("ERROR"):
                            raise RuntimeError(item[6:])
                        pbar.update(item)
                except Empty:
                    continue

        os.rename(in_progress_path, final_path)
        print(f"\nDownload completed successfully: {final_path}")

    except Exception as e:
        print(f"\nDownload failed: {str(e)}")
        try:
            os.remove(in_progress_path)
        except:
            pass
    except KeyboardInterrupt:
        print("\nDownload cancelled by user")
        try:
            os.remove(in_progress_path)
        except:
            pass

if __name__ == "__main__":
    main()
