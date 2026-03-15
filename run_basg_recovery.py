from get_basg_token import get_token_info
import subprocess
import sys
import os

def main():
    print("Capturing fresh BASG token...")
    token, url = get_token_info()
    
    if not token:
        print("Failed to capture token. Aborting.")
        sys.exit(1)
        
    print(f"Token captured: {token[:30]}...")
    
    # Ensure clean output file
    output_file = 'recovery_basg_v12.json'
    if os.path.exists(output_file):
        os.remove(output_file)
        
    print("Starting BASG Scrapy Spider...")
    cmd = [
        'scrapy', 'crawl', 'basg',
        '-o', output_file,
        '-a', f'token={token}'
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')
        process.wait()
        
        if process.returncode == 0:
            print(f"\nBASG Recovery Complete. Results saved to {output_file}")
        else:
            print(f"\nBASG Spider failed with exit code {process.returncode}")
            
    except Exception as e:
        print(f"Error running spider: {e}")

if __name__ == "__main__":
    main()
