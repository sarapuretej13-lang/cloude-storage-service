from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.starred import StarredItem

router = APIRouter(prefix="/starred", tags=["starred"])


@router.get("")
def list_starred(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    items = db.query(StarredItem).filter(StarredItem.user_id == current_user.id).all()
    return [
        {
            "id": item.id,
            "item_path": item.item_path,
            "item_type": item.item_type,
            "item_name": item.item_name,
            "starred_at": item.starred_at.isoformat()
        }
        for item in items
    ]


@router.post("")
def star_item(
    item_path: str = Form(...),
    item_type: str = Form(...),
    item_name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(StarredItem).filter(
        StarredItem.user_id == current_user.id,
        StarredItem.item_path == item_path
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Item already starred")

    star = StarredItem(
        user_id=current_user.id,
        item_path=item_path,
        item_type=item_type,
        item_name=item_name
    )
    db.add(star)
    db.commit()
    db.refresh(star)

    return {"message": "Item starred", "id": star.id}


@router.delete("")
def unstar_item(
    item_path: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    star = db.query(StarredItem).filter(
        StarredItem.user_id == current_user.id,
        StarredItem.item_path == item_path
    ).first()

    if not star:
        raise HTTPException(status_code=404, detail="Starred item not found")

    db.delete(star)
    db.commit()
    return {"message": "Item unstarred"}
