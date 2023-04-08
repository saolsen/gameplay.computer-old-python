from pydantic import BaseModel


class WidgetBase(BaseModel):
    name: str
    is_active: bool = True


class WidgetCreate(WidgetBase):
    pass


class Widget(WidgetBase):
    id: int
