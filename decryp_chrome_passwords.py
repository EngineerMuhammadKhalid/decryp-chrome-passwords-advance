import os
import re
import sys
import json
import base64
import sqlite3
import logging
import shutil
import csv
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from Cryptodome.Cipher import AES
import win32crypt

# Try to import openpyxl for Excel output
try:
    from openpyxl import Workbook
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global constants for Chrome paths
CHROME_PATH_LOCAL_STATE = os.path.normpath(
    os.path.join(os.environ['USERPROFILE'], r"AppData\Local\Google\Chrome\User Data\Local State")
)
CHROME_PATH = os.path.normpath(
    os.path.join(os.environ['USERPROFILE'], r"AppData\Local\Google\Chrome\User Data")
)

def backup_file(filepath):
    """If the file exists, rename it with a timestamp before creating a new one."""
    if os.path.exists(filepath):
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = f"{filepath}.{timestamp}.bak"
        shutil.move(filepath, backup_path)
        logging.info(f"Existing file {filepath} backed up as {backup_path}")

def get_secret_key():
    """Retrieve the AES secret key from Chrome's Local State file."""
    try:
        with open(CHROME_PATH_LOCAL_STATE, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        # Remove DPAPI prefix
        encrypted_key = encrypted_key[5:]
        secret_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        logging.info("Secret key retrieved successfully.")
        return secret_key
    except Exception as e:
        logging.error(f"Error retrieving secret key: {e}")
        return None

def decrypt_password(ciphertext, secret_key):
    """Decrypt the given ciphertext using AES-GCM with the secret key."""
    try:
        iv = ciphertext[3:15]  # Initialization vector
        encrypted_password = ciphertext[15:-16]  # Actual encrypted password
        cipher = AES.new(secret_key, AES.MODE_GCM, iv)
        decrypted_pass = cipher.decrypt(encrypted_password)
        return decrypted_pass.decode()
    except Exception as e:
        logging.error(f"Error decrypting password: {e}")
        return ""

def get_db_connection(login_db_path):
    """
    Copy the Chrome login database to a temporary location and return a connection.
    Also returns the temp file name for later deletion.
    """
    try:
        temp_db = "Loginvault.db"
        shutil.copy2(login_db_path, temp_db)
        conn = sqlite3.connect(temp_db)
        return conn, temp_db
    except Exception as e:
        logging.error(f"Error connecting to database at {login_db_path}: {e}")
        return None, None

def process_profile_folder(folder, secret_key, domain_filter=None):
    """
    Process a given Chrome profile folder:
      - Opens the login DB.
      - Checks if the 'date_created' column is present.
      - Optionally filters by domain.
      - Returns a list of result dictionaries.
    """
    results = []
    login_db_path = os.path.join(CHROME_PATH, folder, "Login Data")
    if not os.path.exists(login_db_path):
        logging.warning(f"Login database not found in folder: {folder}")
        return results

    conn, temp_db = get_db_connection(login_db_path)
    if not conn:
        return results

    try:
        cursor = conn.cursor()
        # Check available columns in the logins table
        cursor.execute("PRAGMA table_info(logins)")
        columns_info = cursor.fetchall()
        columns = [col[1] for col in columns_info]
        # Build the SELECT query based on available columns
        select_cols = ["action_url", "username_value", "password_value"]
        include_date = "date_created" in columns
        if include_date:
            select_cols.append("date_created")
        query = f"SELECT {', '.join(select_cols)} FROM logins"
        cursor.execute(query)
        rows = cursor.fetchall()
        logging.info(f"Processing {len(rows)} entries in profile: {folder}")

        for index, row in enumerate(rows, start=1):
            url = row[0]
            username = row[1]
            ciphertext = row[2]
            date_created = None
            if include_date and len(row) == 4:
                # Convert Chrome's timestamp to human-readable date if possible
                # Chrome stores time in microseconds since Jan 1, 1601
                try:
                    timestamp = int(row[3])
                    if timestamp > 0:
                        epoch_start = datetime.datetime(1601, 1, 1)
                        date_created = epoch_start + datetime.timedelta(microseconds=timestamp)
                        date_created = date_created.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logging.debug(f"Error converting date for entry {index} in {folder}: {e}")

            # Apply domain filtering if needed
            if domain_filter and domain_filter.lower() not in url.lower():
                continue

            if url and username and ciphertext:
                decrypted_password = decrypt_password(ciphertext, secret_key)
                entry = {
                    "profile": folder,
                    "entry_index": index,
                    "url": url,
                    "username": username,
                    "password": decrypted_password
                }
                if date_created:
                    entry["date_created"] = date_created
                results.append(entry)
        cursor.close()
    except Exception as e:
        logging.error(f"Error processing profile {folder}: {e}")
    finally:
        conn.close()
        if os.path.exists(temp_db):
            os.remove(temp_db)
    return results

def write_csv(results, csv_filename):
    """Write results to a CSV file."""
    if not results:
        logging.warning("No data to write to CSV.")
        return
    backup_file(csv_filename)
    fieldnames = list(results[0].keys())
    try:
        with open(csv_filename, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for entry in results:
                writer.writerow(entry)
        logging.info(f"CSV output written to {csv_filename}")
    except Exception as e:
        logging.error(f"Error writing CSV file: {e}")

def write_json(results, json_filename):
    """Write results to a JSON file."""
    if not results:
        logging.warning("No data to write to JSON.")
        return
    backup_file(json_filename)
    try:
        with open(json_filename, "w", encoding="utf-8") as jf:
            json.dump(results, jf, indent=4)
        logging.info(f"JSON output written to {json_filename}")
    except Exception as e:
        logging.error(f"Error writing JSON file: {e}")

def write_excel(results, excel_filename):
    """Write results to an Excel file (requires openpyxl)."""
    if not HAS_OPENPYXL:
        logging.error("openpyxl is not installed. Excel output is disabled.")
        return
    if not results:
        logging.warning("No data to write to Excel.")
        return
    backup_file(excel_filename)
    wb = Workbook()
    ws = wb.active
    ws.title = "Decrypted Passwords"
    # Write header row
    headers = list(results[0].keys())
    ws.append(headers)
    # Write data rows
    for entry in results:
        ws.append([entry.get(col, "") for col in headers])
    try:
        wb.save(excel_filename)
        logging.info(f"Excel output written to {excel_filename}")
    except Exception as e:
        logging.error(f"Error writing Excel file: {e}")

def main(args):
    start_time = datetime.datetime.now()

    # Determine output directory
    outdir = args.outdir if args.outdir else os.getcwd()
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    csv_file = os.path.join(outdir, "decrypted_password.csv")
    json_file = os.path.join(outdir, "decrypted_password.json")
    excel_file = os.path.join(outdir, "decrypted_password.xlsx")

    secret_key = get_secret_key()
    if not secret_key:
        logging.error("Secret key not found, exiting.")
        sys.exit(1)

    # Regex to match "Default" and "Profile" folders
    profile_regex = re.compile(r"^(Default|Profile\s?\d+)$", re.IGNORECASE)
    profiles = [f for f in os.listdir(CHROME_PATH) if profile_regex.match(f)]
    if not profiles:
        logging.error("No valid Chrome profile folders found.")
        sys.exit(1)

    all_results = []
    total_profiles = len(profiles)
    logging.info(f"Found {total_profiles} profiles to process.")

    # Use multi-threading to process profiles concurrently
    with ThreadPoolExecutor(max_workers=min(total_profiles, 4)) as executor:
        future_to_profile = {
            executor.submit(process_profile_folder, profile, secret_key, args.domain): profile 
            for profile in profiles
        }
        for future in as_completed(future_to_profile):
            profile = future_to_profile[future]
            try:
                results = future.result()
                all_results.extend(results)
                logging.info(f"Profile {profile}: {len(results)} entries processed.")
            except Exception as e:
                logging.error(f"Error processing profile {profile}: {e}")

    total_entries = len(all_results)
    logging.info(f"Total entries processed after filtering: {total_entries}")

    # Write outputs
    write_csv(all_results, csv_file)
    if args.json:
        write_json(all_results, json_file)
    if args.excel:
        write_excel(all_results, excel_file)

    # Optionally open output files
    if args.open:
        try:
            os.startfile(os.path.abspath(csv_file))
        except Exception as e:
            logging.error(f"Failed to open CSV file automatically: {e}")
    if args.openjson and args.json:
        try:
            os.startfile(os.path.abspath(json_file))
        except Exception as e:
            logging.error(f"Failed to open JSON file automatically: {e}")
    if args.openexcel and args.excel:
        try:
            os.startfile(os.path.abspath(excel_file))
        except Exception as e:
            logging.error(f"Failed to open Excel file automatically: {e}")

    end_time = datetime.datetime.now()
    elapsed = end_time - start_time
    logging.info(f"Process completed in {elapsed}")

    # Optionally pause the console so it doesn't close immediately
    if args.pause:
        input("Process complete. Press Enter to exit...")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Advanced Chrome Password Decryption Tool with Extra Functionalities")
    parser.add_argument("--open", action="store_true", help="Automatically open the CSV file after processing")
    parser.add_argument("--json", action="store_true", help="Output the decrypted data to a JSON file")
    parser.add_argument("--openjson", action="store_true", help="Automatically open the JSON file after processing (requires --json)")
    parser.add_argument("--excel", action="store_true", help="Output the decrypted data to an Excel file (requires openpyxl)")
    parser.add_argument("--openexcel", action="store_true", help="Automatically open the Excel file after processing (requires --excel)")
    parser.add_argument("--pause", action="store_true", help="Pause the console after processing so it doesn't close immediately")
    parser.add_argument("--domain", type=str, help="Filter entries: only include those where the URL contains the given domain substring")
    parser.add_argument("--outdir", type=str, help="Output directory for the result files")
    parser.add_argument("--verbose", action="store_true", help="Increase logging verbosity")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    main(args)
