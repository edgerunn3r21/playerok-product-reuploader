from dotenv import load_dotenv
import os

load_dotenv()

auth_url = os.getenv("AUTH_URL")
profile_url = os.getenv("PROFILE_URL")
db_url = os.getenv("DB_URL")
token = os.getenv("TOKEN")
admin_list = os.getenv("ADMIN_LIST", "").strip()
site_url = os.getenv("SITE_URL")
