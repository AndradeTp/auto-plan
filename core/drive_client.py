import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import os

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service():
    info = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, folder_name, parent_id=None):
    query = (
        f"name='{folder_name}' "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and trashed=false"
    )
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_excel(local_path: str, drive_folder_name: str, file_name: str) -> str:
    """Faz upload do Excel gerado para o Google Drive. Retorna o link."""
    service = get_drive_service()
    folder_id = get_or_create_folder(service, drive_folder_name)

    # Remove versão antiga se existir
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    old = service.files().list(q=query, fields="files(id)").execute().get("files", [])
    for f in old:
        service.files().delete(fileId=f["id"]).execute()

    metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(local_path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", resumable=True)
    file = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return file.get("webViewLink", "")
