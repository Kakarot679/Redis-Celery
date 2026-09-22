import time

def get_user(user_id: int):

    print("Fetching from Database...")

    time.sleep(5)

    return {
        "id": user_id,
        "name": "Hardik",
        "city": "Ghaziabad"
    }