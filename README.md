# decryp-chrome-passwords-advance
The **Chrome Password Decryption Tool** is a powerful, Python-based utility designed to extract and decrypt saved Chrome passwords from multiple user profiles. It harnesses advanced techniques such as multi-threaded processing to handle multiple profiles concurrently, ensuring a speedy and efficient extraction process.
# Chrome Password Decryption Tool

An advanced Python-based tool for extracting and decrypting saved Chrome passwords with extra functionalities. This program leverages multi-threading to process multiple Chrome profiles concurrently, supports domain filtering, and offers output in CSV, JSON, and Excel formats. It also features detailed logging, automatic file backup, and optional console persistence.

---

## Features

- **Password Decryption:**  
  Retrieve and decrypt saved Chrome passwords using the system’s secret key.

- **Multi-Threaded Processing:**  
  Processes multiple Chrome profiles concurrently for faster data extraction.

- **Domain Filtering:**  
  Optionally filter entries to include only those where the URL contains a specified substring.

- **Multiple Output Formats:**  
  - **CSV (default)**
  - **JSON** (optional; enable with `--json`)
  - **Excel** (optional; enable with `--excel`, requires `openpyxl`)

- **Automatic File Backup:**  
  Existing output files are backed up with a timestamp before new files are created.

- **Verbose Logging:**  
  Detailed logging and debugging information with an optional verbose mode.

- **Console Persistence:**  
  Option to pause the console after processing to review the results.

---

## Requirements

- **Python 3.x**

- **Required Libraries:**
  - [pycryptodome](https://pypi.org/project/pycryptodome/)
  - [pypiwin32](https://pypi.org/project/pywin32/)

- **Optional Libraries:**
  - [openpyxl](https://pypi.org/project/openpyxl/) (for Excel output)

### Installation

Install the required packages via pip:

```bash
pip install pycryptodome pywin32

For Excel support (optional):
pip install openpyxl

Usage
Run the script from the command line with various options:
python decrypt_chrome_passwords.py

Command-Line Options
--open
Automatically open the CSV file after processing.

--json
Output the decrypted data to a JSON file.

--openjson
Automatically open the JSON file after processing (requires --json).

--excel
Output the decrypted data to an Excel file (requires openpyxl).

--openexcel
Automatically open the Excel file after processing (requires --excel).

--pause
Pause the console after processing so it doesn't close immediately.

--domain <substring>
Filter entries: only include those where the URL contains the given domain substring.

--outdir <directory>
Specify the output directory for the result files.

--verbose
Increase logging verbosity for debugging purposes.
Example
Extract passwords filtered by example.com, output data to both CSV and JSON, and keep the console open:

How It Works
Secret Key Retrieval:
The tool reads Chrome's Local State file to obtain the AES secret key used for encryption.

Database Handling:
For each Chrome profile (e.g., Default, Profile 1, etc.), the tool copies the Login Data database to a temporary file to avoid file locks, then connects to it.

Data Decryption:
Encrypted passwords are decrypted using AES-GCM with the retrieved secret key.

Output Generation:
Decrypted data is written to a CSV file by default. Optionally, JSON and Excel files are created. Pre-existing files are backed up with a timestamp.

Logging & Summary:
Detailed logs and a final summary of the extraction process (e.g., total profiles and entries processed) are displayed on the command prompt.

Disclaimer
This tool is provided for educational purposes and personal use only. Ensure that you have the proper permissions to access and decrypt data from any Chrome profile. Use at your own risk.
