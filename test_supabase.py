import os
from supabase import create_client, Client

url: str = "https://pqddatpveszwjsatpvhg.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBxZGRhdHB2ZXN6d2pzYXRwdmhnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0NzA0ODcsImV4cCI6MjA5OTA0NjQ4N30.o6FvheU5owNDUodTfHVj_Y8w53ZfSnRSjUlJMaqhhZo"

supabase: Client = create_client(url, key)

try:
    print("Testing connection...")
    response = supabase.table("portfolios").select("*").limit(1).execute()
    print("Success:", response)
except Exception as e:
    print("Error:", e)
