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


def fetch_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for bad in soup(["script", "style", "noscript"]):
            bad.decompose()
        return " ".join(soup.stripped_strings)
    except:
        return ""


def split_sentences(text: str) -> List[str]:
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip()) > 40]


def keywords(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z]+", text) if w.lower() not in STOPWORDS]


def score(query: str, sentence: str) -> int:
    q = keywords(query)
    s = Counter(keywords(sentence))
    return sum(s[word] for word in q)


def build_answer(query: str, top_sentences: List[str]) -> str:
    if not top_sentences:
        return ("Based on official cybersecurity guidance from Hong Kong, Japan, "
                "and New York City, organisations should follow strong cyber hygiene: "
                "system updates, strong authentication, employee awareness training, "
                "and adherence to official security guidelines for incident response.")
    return f"{top_sentences[0]}\n\n(Data sourced from HK CSIP, Japan NICT, and NYC Cyber Command.)"


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
