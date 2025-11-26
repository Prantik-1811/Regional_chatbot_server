from fastapi import FastAPI, Request
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
from typing import List

app = FastAPI()

# ---------- Official Cybersecurity Sources ----------
SOURCES = [
    "https://www.cybersecurity.hk/en/about.php",
    "https://www.cybersecurity.hk/en/safety-centre.php",
    "https://www.cybersecurity.hk/en/learning-centre.php",
    "https://nco.nict.go.jp/en/",
    "https://www.nyc.gov/site/em/ready/cybersecurity.page"
]

STOPWORDS = set("""
the is are was were a an of to in on for with this that from by as be can will and your their you our they we it
""".split())

CYBER_KEYWORDS = [
    "security", "attack", "cyber", "ransomware", "malware", "phishing",
    "threat", "breach", "awareness", "guidance", "incident", "protection",
    "risk", "device", "iot", "network", "encryption", "vulnerability"
]

# ---------- Fetch & Clean Website Text ----------
def fetch_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Remove menus, headers, etc.
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()

        text = " ".join(soup.stripped_strings)

        # Remove UI words
        blacklist = [
            "Skip to Content", "Home", "A A A", "繁", "简", "Eng", "Menu", "Join",
            "Watch", "Event", "Calendar", "Programme", "Video", "Resources"
        ]
        for word in blacklist:
            text = text.replace(word, "")

        return text
    except:
        return ""


# ---------- Sentence Split ----------
def split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 40]


# ---------- Keyword Processing ----------
def keywords(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z]+", text) if w.lower() not in STOPWORDS]


def score(query: str, sentence: str) -> int:
    q = keywords(query)
    s = Counter(keywords(sentence))
    return sum(s[word] for word in q)


# ---------- Build Final Clean Answer ----------
def build_answer(query: str, top_sentences: List[str]) -> str:
    for sentence in top_sentences:
        if any(word in sentence.lower() for word in CYBER_KEYWORDS):
            return f"{sentence}\n\n(Source: HK CSIP, Japan NICT, NYC Cyber Command)"

    # fallback answer if no direct match
    return (
        "Based on official cybersecurity portals of Hong Kong, Japan, and New York City, "
        "best practice includes regular software updates, secure authentication, "
        "awareness training, and compliance with government cybersecurity guidance."
    )


# ---------- Webhook API ----------
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    try:
        query = data["queryResult"]["queryText"]
    except:
        return {"fulfillmentText": "Couldn't understand your request."}

    corpus = ""
    for url in SOURCES:
        corpus += fetch_text(url) + " "

    sentences = split_sentences(corpus)
    scored = sorted(sentences, key=lambda s: score(query, s), reverse=True)

    answer = build_answer(query, scored[:6])
    return {"fulfillmentText": answer}
