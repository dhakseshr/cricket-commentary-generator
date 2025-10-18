import requests

url = "https://api.heygen.com/v2/voices"
headers = {
    "X-Api-Key": "sk_V2_hgu_kbaMGL2ktiq_VWlB1HAOvCDllmQMP04zJUJnrwDf7RXB",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)
voices = response.json().get("data", {}).get("voices", [])

print("Available Voices:")
for voice in voices:
    print(f"Voice ID: {voice['voice_id']}, Name: {voice['name']}, Language: {voice['language']}")
