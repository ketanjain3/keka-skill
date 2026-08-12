#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Script directory for credential files
SCRIPT_DIR = Path(__file__).parent.resolve()
TOKEN_FILE = SCRIPT_DIR / 'token.json'
CLIENT_SECRET_FILE = SCRIPT_DIR / 'client_secret.json'

# Default folder ID for timesheet uploads
DEFAULT_FOLDER_ID = '1gQD1-7a8fv6zA0OBy65gQz7N_UE6x6x0'

def get_credentials():
    """Get valid credentials, refreshing or authenticating as needed."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds

def upload_file(file_path: str, folder_id: str = None) -> dict:
    """Upload a file to Google Drive.

    Args:
        file_path: Path to the file to upload
        folder_id: Google Drive folder ID (uses default if not specified)

    Returns:
        Dict with 'id' and 'name' of uploaded file, or None on error
    """
    folder_id = folder_id or DEFAULT_FOLDER_ID

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        return None

    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }

        # Determine mimetype
        ext = os.path.splitext(file_path)[1].lower()
        mimetypes = {
            '.pdf': 'application/pdf',
            '.json': 'application/json',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
        }
        mimetype = mimetypes.get(ext, 'application/octet-stream')

        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,webViewLink'
        ).execute()

        return {
            'id': file.get('id'),
            'name': file.get('name'),
            'link': file.get('webViewLink')
        }

    except HttpError as error:
        print(f'Google Drive API error: {error}', file=sys.stderr)
        return None
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Make sure client_secret.json exists in the google_drive directory.", file=sys.stderr)
        return None

def main():
    """CLI entry point for uploading files to Google Drive."""
    if len(sys.argv) < 2:
        print("Usage: python drive.py <file_path> [folder_id]")
        print(f"  file_path: Path to file to upload")
        print(f"  folder_id: Google Drive folder ID (default: {DEFAULT_FOLDER_ID})")
        sys.exit(1)

    file_path = sys.argv[1]
    folder_id = sys.argv[2] if len(sys.argv) > 2 else None

    result = upload_file(file_path, folder_id)

    if result:
        print(f"File uploaded successfully!")
        print(f"  File ID: {result['id']}")
        print(f"  Name: {result['name']}")
        if result.get('link'):
            print(f"  Link: {result['link']}")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
