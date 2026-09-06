from fastapi import APIRouter

router = APIRouter()

@router.get("/files")
def get_files():
    return {
        "message": "Files endpoint is working"
    }