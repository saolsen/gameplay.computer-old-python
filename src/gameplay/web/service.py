# from sqlalchemy.orm import Session

# from . import models, schemas


# def get_widget(db: Session, widget_id: int):
#     return db.query(models.Widgets).filter(models.Widgets.id == widget_id).first()


# def get_widget_by_name(db: Session, name: str):
#     return db.query(models.Widgets).filter(models.Widgets.name == name).first()


# def get_widgets(db: Session, skip: int = 0, limit: int = 100):
#     return db.query(models.Widgets).offset(skip).limit(limit).all()


# def create_widget(db: Session, widget: schemas.WidgetCreate):
#     db_widget = models.Widgets(**widget.dict())
#     db.add(db_widget)
#     db.commit()
#     db.refresh(db_widget)
#     return db_widget
