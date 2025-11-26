from fastapi import FastAPI, Request
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
from typing import List

app = FastAPI()

# ---------- Data Sources ----------
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


# ---------- 1. Fetch text ----------
def fetch_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for bad in soup(["script", "style", "noscript"]):
            bad.decompose()
        text = " ".join(soup.stripped_strings)
        return text
    except:
        return ""


# ---------- 2. Sentence Split ----------
def split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 40]


# ---------- 3. Keyword Score ----------
def keywords(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z]+", text) if w.lower() not in STOPWORDS]


def score(query: str, sentence: str) -> int:
    q = keywords(query)
    s = Counter(keywords(sentence))
    return sum(s[word] for word in q)


# ---------- 4. Generate Answer ----------
def build_answer(query: str, top_sentences: List[str]) -> str:
    if not top_sentences:
        return ("Based on the official cybersecurity information from Hong Kong, "
                "Japan and New York City, organisations are advised to maintain "
                "strong cyber hygiene, update systems, use strong authentication "
                "and follow official government security guidance.")

    joined = " ".join(top_sentences[:3])
    return f"{joined} \n\n(Information derived from HK CSIP, Japan NICT and NYC Cyber Command official sites.)"


# ---------- 5. Webhook ----------
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    query = data.get("queryResult", {}).get("queryText", "")
    if not query:
        return {"fulfillmentText": "No query provided."}

    corpus = ""
    for url in SOURCES:
        corpus += fetch_text(url) + " "

    sentences = split_sentences(corpus)
    scored = sorted(sentences, key=lambda s: score(query, s), reverse=True)

    answer = build_answer(query, scored[:5])
    return {"fulfillmentText": answer}
