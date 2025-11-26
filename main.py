from fastapi import FastAPI, Request
import requests
from bs4 import BeautifulSoup
import re
from transformers import pipeline

app = FastAPI()

ALLOWED_SITES = {
    "hongkong": [
        "https://www.cybersecurity.hk/en/about.php",
        "https://www.cybersecurity.hk/en/safety-centre.php",
        "https://www.cybersecurity.hk/en/learning-centre.php",
    ],
    "japan": [
        "https://nco.nict.go.jp/en/",
    ],
    "nyc": [
        "https://www.nyc.gov/site/em/ready/cybersecurity.page",
    ],
}

summarizer = None

def load_summarizer():
    global summarizer
    if summarizer is None:
        summarizer = pipeline("summarization", model="philschmid/distilbart-cnn-6-6")

STOPWORDS = {
    "the", "is", "am", "are", "a", "an", "of", "and", "or", "to", "in",
    "on", "for", "with", "this", "that", "it", "as", "by", "from",
    "be", "can", "will", "you", "your", "their", "they", "we", "our"
}

def fetch_visible_text(url: str) -> str:
    try:
        resp = requests.get(url, timeout=18)
        resp.raise_for_status()
    except Exception:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.stripped_strings)

def clean_sentences(text: str):
    raw = re.split(r"(?<=[.!?])\s+", text)
    return [s for s in raw if len(s) > 50]

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    query = data.get("queryResult", {}).get("queryText", "")
    if not query:
        return {"fulfillmentText": "No query text received."}

    load_summarizer()

    combined_text = ""
    for urls in ALLOWED_SITES.values():
        for url in urls:
            combined_text += fetch_visible_text(url) + " "

    if not combined_text:
        return {"fulfillmentText": "No information found from the registered sources."}

    sentences = clean_sentences(combined_text)
    text_block = " ".join(sentences[:20])

    summary = summarizer(text_block, max_length=130, min_length=40, do_sample=False)[0]["summary_text"]

    final_answer = f"{summary}\n\n(Answer generated based on HK CSIP, Japan NICT, and NYC Cyber Command data.)"

    return {"fulfillmentText": final_answer}


@app.on_event("startup")
def preload():
    try:
        load_summarizer()
        print("🔥 Summarizer loaded.")
    except:
        print("⚠️ Summarizer lazy load only.")
