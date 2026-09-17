from database.database import SessionLocal
from database.models import Restaurant


db = SessionLocal()

try:

    restaurant = Restaurant(
        name="3Brews",
        instagram_username="3brews.sa",
        email="reachus@3brew.com",
        location="Jeddah",
    )

    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    print("Restaurant added:")
    print("ID:", restaurant.id)
    print("Name:", restaurant.name)
    print("Instagram:", restaurant.instagram_username)

finally:
    db.close()