from pydantic import BaseModel

# Users are stored in Clerk.
# Clerk lets people update their emails and usernames and other things,
# so we don't store those as references in our database.
# In other tables we only reference users by their Clerk user ID.


class EmailAddress(BaseModel):
    id: str
    email_address: str


class User(BaseModel):
    id: str
    username: str
    first_name: str | None
    last_name: str | None
    profile_image_url: str | None
    email_addresses: list[EmailAddress]
    primary_email_address_id: str
