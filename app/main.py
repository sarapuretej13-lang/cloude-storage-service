import os
import re
import shutil
import secrets

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.config import UPLOAD_DIR
from app.core.database import engine, get_db, Base
from app.core.security import get_current_user

# ── import all models so Base.metadata knows about them ──
from app.models.user import User
from app.models.share import Share, PublicLink
from app.models.starred import StarredItem
from app.models.trash_item import TrashItem

# ── import routers early so any import errors are visible ──
from app.routes.auth import router as auth_router
from app.routes.starred import router as starred_router

# Create all tables — runs in background, won't block server startup
import threading

def create_tables():
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ Database tables ready")
    except Exception as e:
        print(f"⚠️  Could not create tables: {e}")

threading.Thread(target=create_tables, daemon=True).start()

# =========================================================
# APP
# =========================================================

app = FastAPI(title="Cloud Storage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(starred_router)


# Global error handler — always returns CORS headers so browser can read the error
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"}
    )

# =========================================================
# CONSTANTS
# =========================================================

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".pdf", ".txt", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".mp4", ".mp3"
}

MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",  ".gif": "image/gif",
    ".webp": "image/webp", ".pdf": "application/pdf",
    ".txt": "text/plain",  ".mp4": "video/mp4",
    ".webm": "video/webm", ".mp3": "audio/mpeg",
    ".wav": "audio/wav"
}

# =========================================================
# HELPERS
# =========================================================

def validate_filename(filename: str) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    filename = os.path.basename(filename)
    if filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not re.match(r"^[a-zA-Z0-9_\- .()]+$", filename):
        raise HTTPException(status_code=400, detail="Filename contains invalid characters")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' is not allowed")
    return filename


def user_upload_dir(user_id) -> str:
    path = os.path.join(UPLOAD_DIR, str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


def user_safe_path(user_id, relative_path: str) -> str:
    relative_path = relative_path.replace("\\", "/").strip("/")
    base = os.path.abspath(user_upload_dir(user_id))
    full_path = os.path.abspath(os.path.join(base, relative_path)) if relative_path else base
    if not (full_path == base or full_path.startswith(base + os.sep)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return full_path


def format_storage_size(size: int) -> str:
    if size == 0:
        return "0 Bytes"
    units = ["Bytes", "KB", "MB", "GB"]
    index, value = 0, float(size)
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    return f"{value:.2f} {units[index]}"


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return {"message": "Cloud Storage API is running"}


# =========================================================
# STATS
# =========================================================

@app.get("/stats")
def storage_stats(current_user: User = Depends(get_current_user)):
    base = user_upload_dir(current_user.id)
    total_files = total_folders = total_size = 0

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.endswith(".trash")]
        files = [f for f in files if not f.endswith(".trash")]
        total_folders += len(dirs)
        for filename in files:
            total_files += 1
            try:
                total_size += os.path.getsize(os.path.join(root, filename))
            except OSError:
                pass

    return {
        "files": total_files,
        "folders": total_folders,
        "storage_bytes": total_size,
        "storage": format_storage_size(total_size)
    }


# =========================================================
# LIST ROOT
# =========================================================

@app.get("/files")
def list_files(current_user: User = Depends(get_current_user)):
    base = user_upload_dir(current_user.id)
    items = []
    for item in os.listdir(base):
        if item.endswith(".trash"):
            continue
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path):
            items.append({"name": item, "type": "folder"})
        elif os.path.isfile(item_path):
            items.append({
                "name": item, "type": "file",
                "size": os.path.getsize(item_path),
                "extension": os.path.splitext(item)[1].lower()
            })
    return {"items": items}


# =========================================================
# UPLOAD TO ROOT
# =========================================================

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    filename = validate_filename(file.filename)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty files are not allowed")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Max file size is {MAX_FILE_SIZE // (1024*1024)} MB")
    with open(user_safe_path(current_user.id, filename), "wb") as f:
        f.write(content)
    return {"message": "Uploaded successfully", "filename": filename, "size": len(content)}


# =========================================================
# UPLOAD TO FOLDER
# =========================================================

@app.post("/upload/{folder_path:path}")
async def upload_file_to_folder(
    folder_path: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    filename = validate_filename(file.filename)
    folder_full = user_safe_path(current_user.id, folder_path)
    if not os.path.exists(folder_full):
        raise HTTPException(status_code=404, detail="Folder not found")
    if not os.path.isdir(folder_full):
        raise HTTPException(status_code=400, detail="Target is not a folder")
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty files are not allowed")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Max file size is {MAX_FILE_SIZE // (1024*1024)} MB")
    with open(user_safe_path(current_user.id, folder_path + "/" + filename), "wb") as f:
        f.write(content)
    return {"message": "Uploaded successfully", "filename": filename, "folder": folder_path, "size": len(content)}


# =========================================================
# PREVIEW
# =========================================================

@app.get("/preview/{filename:path}")
def preview_file(filename: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Cannot preview a folder")
    ext = os.path.splitext(filename)[1].lower()
    return FileResponse(fp, media_type=MEDIA_TYPES.get(ext, "application/octet-stream"),
                        headers={"Content-Disposition": "inline"})


@app.get("/folders/{folder_path:path}/preview/{filename:path}")
def preview_from_folder(folder_path: str, filename: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, folder_path + "/" + filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Cannot preview a folder")
    ext = os.path.splitext(filename)[1].lower()
    return FileResponse(fp, media_type=MEDIA_TYPES.get(ext, "application/octet-stream"),
                        headers={"Content-Disposition": "inline"})


# =========================================================
# DOWNLOAD
# =========================================================

@app.get("/download/{filename:path}")
def download_file(filename: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Cannot download a folder")
    return FileResponse(fp, filename=os.path.basename(fp), media_type="application/octet-stream")


@app.get("/folders/{folder_path:path}/download/{filename:path}")
def download_from_folder(folder_path: str, filename: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, folder_path + "/" + filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Cannot download a folder")
    return FileResponse(fp, filename=os.path.basename(fp), media_type="application/octet-stream")


# =========================================================
# DELETE FILE
# =========================================================

@app.delete("/delete/{filename:path}")
def delete_file(filename: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Use folder delete endpoint")
    os.remove(fp)
    return {"message": "File deleted", "filename": filename}


@app.delete("/folders/{folder_path:path}/delete/{filename:path}")
def delete_from_folder(folder_path: str, filename: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, folder_path + "/" + filename)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File not found")
    if os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Target is a folder")
    os.remove(fp)
    return {"message": "File deleted", "filename": filename, "folder": folder_path}


# =========================================================
# FOLDERS
# =========================================================

@app.post("/folders/{folder_path:path}")
def create_folder(folder_path: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, folder_path)
    if os.path.exists(fp):
        raise HTTPException(status_code=400, detail="Folder already exists")
    os.makedirs(fp)
    return {"message": "Folder created", "folder": folder_path}


@app.delete("/folders/{folder_path:path}")
def delete_folder(folder_path: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, folder_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="Folder not found")
    if not os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Not a folder")
    if os.listdir(fp):
        raise HTTPException(status_code=400, detail="Folder is not empty")
    os.rmdir(fp)
    return {"message": "Folder deleted", "folder": folder_path}


@app.get("/folders/{folder_path:path}")
def list_folder(folder_path: str, current_user: User = Depends(get_current_user)):
    fp = user_safe_path(current_user.id, folder_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="Folder not found")
    if not os.path.isdir(fp):
        raise HTTPException(status_code=400, detail="Not a folder")
    items = []
    for item in os.listdir(fp):
        if item.endswith(".trash"):
            continue
        ip = os.path.join(fp, item)
        if os.path.isdir(ip):
            items.append({"name": item, "type": "folder"})
        elif os.path.isfile(ip):
            items.append({
                "name": item, "type": "file",
                "size": os.path.getsize(ip),
                "extension": os.path.splitext(item)[1].lower()
            })
    return {"folder": folder_path, "items": items}


# =========================================================
# RENAME
# =========================================================

@app.put("/rename/{old_path:path}")
async def rename_item(
    old_path: str,
    new_name: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    old_full = user_safe_path(current_user.id, old_path)
    if not os.path.exists(old_full):
        raise HTTPException(status_code=404, detail="Not found")
    new_name = new_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    base = os.path.abspath(user_upload_dir(current_user.id))
    new_full = os.path.abspath(os.path.join(os.path.dirname(old_full), new_name))
    if not new_full.startswith(base + os.sep):
        raise HTTPException(status_code=400, detail="Invalid name")
    if os.path.exists(new_full):
        raise HTTPException(status_code=400, detail="Name already exists")
    os.rename(old_full, new_full)
    return {"message": "Renamed successfully", "old_name": old_path, "new_name": new_name}


# =========================================================
# MOVE
# =========================================================

@app.post("/move")
async def move_item(
    item_name: str = Form(...),
    destination: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    src = user_safe_path(current_user.id, item_name)
    dst = user_safe_path(current_user.id, destination)
    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="Source not found")
    if not os.path.isdir(dst):
        raise HTTPException(status_code=400, detail="Destination is not a folder")
    new_path = os.path.join(dst, os.path.basename(src))
    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="Item already exists at destination")
    shutil.move(src, new_path)
    return {"message": "Moved successfully", "item": item_name, "destination": destination}


# =========================================================
# SEARCH
# =========================================================

@app.get("/search")
async def search_files(q: str = "", current_user: User = Depends(get_current_user)):
    q = q.strip().lower()
    if not q:
        return []
    base = user_upload_dir(current_user.id)
    results = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.endswith(".trash")]
        files = [f for f in files if not f.endswith(".trash")]
        for folder in dirs:
            if q in folder.lower():
                results.append({
                    "name": folder, "type": "folder",
                    "path": os.path.relpath(os.path.join(root, folder), base).replace("\\", "/")
                })
        for filename in files:
            if q in filename.lower():
                fp = os.path.join(root, filename)
                results.append({
                    "name": filename, "type": "file",
                    "path": os.path.relpath(fp, base).replace("\\", "/"),
                    "size": os.path.getsize(fp),
                    "extension": os.path.splitext(filename)[1].lower()
                })
    return results


# =========================================================
# SHARING (DB-backed)
# =========================================================

@app.post("/share")
async def share_item(
    item_path: str = Form(...),
    shared_with: str = Form(...),
    permission: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    permission = permission.lower().strip()
    if permission not in {"owner", "editor", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid permission")
    fp = user_safe_path(current_user.id, item_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File or folder not found")
    item_type = "folder" if os.path.isdir(fp) else "file"
    share = Share(
        owner_id=current_user.id,
        item_path=item_path,
        item_type=item_type,
        shared_with_email=shared_with.strip(),
        permission=permission
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return {"message": "Shared successfully", "share": {
        "id": share.id, "item_path": share.item_path,
        "shared_with": share.shared_with_email, "permission": share.permission
    }}


@app.get("/shares")
async def list_all_shares(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    shares = db.query(Share).filter(Share.owner_id == current_user.id).all()
    return [{"id": s.id, "item_path": s.item_path, "shared_with": s.shared_with_email, "permission": s.permission} for s in shares]



async def list_shared_users(
    item_path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    shares = db.query(Share).filter(
        Share.owner_id == current_user.id,
        Share.item_path == item_path
    ).all()
    return [{"id": s.id, "item_path": s.item_path, "shared_with": s.shared_with_email, "permission": s.permission} for s in shares]


@app.put("/share/permission")
async def change_permission(
    item_path: str = Form(...),
    shared_with: str = Form(...),
    permission: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    permission = permission.strip().lower()
    if permission not in {"owner", "editor", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid permission")
    share = db.query(Share).filter(
        Share.owner_id == current_user.id,
        Share.item_path == item_path,
        Share.shared_with_email == shared_with
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    share.permission = permission
    db.commit()
    return {"message": "Permission updated"}


@app.delete("/share")
async def remove_share(
    item_path: str,
    shared_with: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    share = db.query(Share).filter(
        Share.owner_id == current_user.id,
        Share.item_path == item_path,
        Share.shared_with_email == shared_with
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    db.delete(share)
    db.commit()
    return {"message": "Access removed"}


# =========================================================
# PUBLIC LINKS (DB-backed)
# =========================================================

@app.post("/public-link")
async def create_public_link(
    item_path: str = Form(...),
    expires_in_days: int = Form(7),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fp = user_safe_path(current_user.id, item_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File or folder not found")
    token = secrets.token_urlsafe(16)
    link = PublicLink(
        user_id=current_user.id,
        token=token,
        item_path=item_path,
        expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
    )
    db.add(link)
    db.commit()
    return {"message": "Public link created", "token": token, "link": f"/public/{token}"}


@app.get("/public-links")
async def list_public_links(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    links = db.query(PublicLink).filter(PublicLink.user_id == current_user.id).all()
    return [{"token": l.token, "item_path": l.item_path,
             "expires_at": l.expires_at.isoformat() if l.expires_at else None} for l in links]


@app.get("/public/{token}")
async def access_public_link(token: str, db: Session = Depends(get_db)):
    link = db.query(PublicLink).filter(PublicLink.token == token).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise HTTPException(status_code=410, detail="Link has expired")
    fp = user_safe_path(link.user_id, link.item_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File no longer exists")
    if os.path.isfile(fp):
        return FileResponse(fp)

    # Build HTML page listing folder contents
    folder_name = os.path.basename(fp)
    items = []
    for item in os.listdir(fp):
        item_path = os.path.join(fp, item)
        if item.endswith(".trash"):
            continue
        if os.path.isdir(item_path):
            items.append({"name": item, "type": "folder", "size": None})
        else:
            size = os.path.getsize(item_path)
            ext = os.path.splitext(item)[1].lower()
            items.append({"name": item, "type": "file", "size": size, "ext": ext})

    items.sort(key=lambda x: (0 if x["type"] == "folder" else 1, x["name"].lower()))

    def fmt_size(b):
        if b is None: return ""
        if b == 0: return "0 B"
        for unit in ["B","KB","MB","GB"]:
            if b < 1024: return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    rows = ""
    for it in items:
        icon = "📁" if it["type"] == "folder" else {
            ".pdf":"📄",".jpg":"🖼️",".jpeg":"🖼️",".png":"🖼️",".gif":"🖼️",
            ".mp4":"🎬",".mp3":"🎵",".zip":"🗜️",".doc":"📝",".docx":"📝",
            ".xls":"📊",".xlsx":"📊",".txt":"📃"
        }.get(it.get("ext",""), "📄")
        size_str = fmt_size(it["size"]) if it["type"] == "file" else "—"
        rows += f"""
        <tr>
            <td>{icon} {it['name']}</td>
            <td>{it['type'].capitalize()}</td>
            <td>{size_str}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>📁 {folder_name}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;color:#1e293b;padding:32px 16px}}
  .card{{max-width:720px;margin:0 auto;background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.08);overflow:hidden}}
  .header{{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;padding:28px 32px}}
  .header h1{{font-size:22px;font-weight:700}}
  .header p{{font-size:13px;opacity:.8;margin-top:4px}}
  table{{width:100%;border-collapse:collapse}}
  th{{text-align:left;padding:12px 24px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#64748b;border-bottom:1px solid #e2e8f0}}
  td{{padding:12px 24px;font-size:14px;border-bottom:1px solid #f1f5f9}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#f8fafc}}
  .empty{{padding:32px;text-align:center;color:#94a3b8;font-size:14px}}
  .footer{{padding:16px 24px;text-align:center;font-size:12px;color:#94a3b8;border-top:1px solid #f1f5f9}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>📁 {folder_name}</h1>
    <p>Shared folder · {len(items)} item(s)</p>
  </div>
  {"<table><thead><tr><th>Name</th><th>Type</th><th>Size</th></tr></thead><tbody>" + rows + "</tbody></table>" if items else '<div class="empty">This folder is empty.</div>'}
  <div class="footer">☁️ Cloud Storage — Shared Link</div>
</div>
</body>
</html>"""

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@app.delete("/public-link/{token}")
async def revoke_public_link(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    link = db.query(PublicLink).filter(
        PublicLink.token == token, PublicLink.user_id == current_user.id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()
    return {"message": "Link revoked"}


# =========================================================
# TRASH (DB-backed)
# =========================================================

@app.get("/trash")
async def get_trash(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(TrashItem).filter(TrashItem.user_id == current_user.id).all()
    return [{"id": i.id, "name": i.item_name, "path": i.item_path,
             "type": i.item_type, "trashed_at": i.trashed_at.isoformat()} for i in items]


@app.post("/trash")
async def move_to_trash(
    item_path: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    fp = user_safe_path(current_user.id, item_path)
    if not os.path.exists(fp):
        raise HTTPException(status_code=404, detail="File or folder not found")
    item_type = "folder" if os.path.isdir(fp) else "file"
    item_name = os.path.basename(fp)
    os.rename(fp, fp + ".trash")
    ti = TrashItem(user_id=current_user.id, item_path=item_path, item_name=item_name, item_type=item_type)
    db.add(ti)
    db.commit()
    return {"message": "Moved to trash", "item": {"name": item_name, "path": item_path, "type": item_type}}


@app.post("/trash/restore")
async def restore_from_trash(
    item_path: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    trash_fp = user_safe_path(current_user.id, item_path + ".trash")
    if not os.path.exists(trash_fp):
        raise HTTPException(status_code=404, detail="Item not found in trash")
    orig_fp = user_safe_path(current_user.id, item_path)
    if os.path.exists(orig_fp):
        raise HTTPException(status_code=409, detail="An item with this name already exists")
    os.rename(trash_fp, orig_fp)
    db.query(TrashItem).filter(
        TrashItem.user_id == current_user.id, TrashItem.item_path == item_path
    ).delete()
    db.commit()
    return {"message": "Item restored"}


@app.delete("/trash/empty")
async def empty_trash(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(TrashItem).filter(TrashItem.user_id == current_user.id).all()
    for item in items:
        tp = user_safe_path(current_user.id, item.item_path + ".trash")
        if os.path.exists(tp):
            shutil.rmtree(tp) if os.path.isdir(tp) else os.remove(tp)
    db.query(TrashItem).filter(TrashItem.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Trash emptied"}


@app.delete("/trash")
async def permanently_delete(
    item_path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tp = user_safe_path(current_user.id, item_path + ".trash")
    if not os.path.exists(tp):
        raise HTTPException(status_code=404, detail="Item not found in trash")
    shutil.rmtree(tp) if os.path.isdir(tp) else os.remove(tp)
    db.query(TrashItem).filter(
        TrashItem.user_id == current_user.id, TrashItem.item_path == item_path
    ).delete()
    db.commit()
    return {"message": "Permanently deleted"}
