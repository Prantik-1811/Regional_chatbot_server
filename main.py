from fastapi import FastAPI, Request
import requests
from bs4 import BeautifulSoup

app = FastAPI()

ALLOWED_SITES = {
    "hongkong": "https://www.cybersecurity.hk/en/about.php",
    "japan": "https://nco.nict.go.jp/en",
    "nyc": "https://www.nyc.gov/site/em/ready/cybersecurity.page"
}

@app.post("/webhook")
async def dialogflow_webhook(req: Request):
    data = await req.json()
    query = data["queryResult"]["queryText"].lower()

    # Identify region automatically
    if any(word in query for word in ["hong", "hk", "hong kong"]):
        url = ALLOWED_SITES["hongkong"]
    elif "japan" in query or "nict" in query or "notice" in query:
        url = ALLOWED_SITES["japan"]
    elif "nyc" in query or "new york" in query:
        url = ALLOWED_SITES["nyc"]
    else:
        return {
            "fulfillmentText": (
                "I can give live cybersecurity info. "
                "Ask about Hong Kong, Japan, or NYC."
            )
        }

    # Scrape website
    page = requests.get(url)
    soup = BeautifulSoup(page.text, "html.parser")
    text = " ".join(soup.stripped_strings)

    # Limit response
    summary = text[:900]

    return {"fulfillmentText": summary}
