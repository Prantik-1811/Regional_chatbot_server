from fastapi import FastAPI, Request
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter
from typing import List, Optional

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

app = FastAPI()

# ---------- 1. ALLOWED SITES ----------

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

STOPWORDS = {
    "the", "is", "am", "are", "a", "an", "of", "and", "or", "to", "in",
    "on", "for", "with", "this", "that", "it", "as", "by", "from",
    "be", "can", "will", "you", "your", "their", "they", "we", "our"
}

# ---------- 2. LLM LAZY LOAD ----------

tokenizer = None
model = None

def load_llm():
    global tokenizer, model
    if tokenizer is None or model is None:
        MODEL_NAME = "google/flan-t5-small"
        print("📌 Loading FLAN-T5-Small model... (lazy load)")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)


# ---------- 3. TEXT UTILITIES ----------

def fetch_text_from_url(url: str) -> str:
    """Fetch and clean visible text from a given URL."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = " ".join(soup.stripped_strings)
    return text


def split_into_sentences(text: str) -> List[str]:
    """Very simple sentence splitter."""
    raw = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in raw if len(s.strip()) > 40]
    return sentences


def tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-zA-Z]+", text)
    return [t for t in tokens if t not in STOPWORDS]


def score_sentence(query_tokens: List[str], sentence_tokens: List[str]) -> int:
    """Score = overlap count between query and sentence tokens."""
    if not sentence_tokens:
        return 0
    sentence_counts = Counter(sentence_tokens)
    score = 0
    for qt in query_tokens:
        score += sentence_counts.get(qt, 0)
    return score


def detect_region_hint(query: str) -> Optional[str]:
    q = query.lower()
    if any(w in q for w in ["hong kong", "hongkong", "hk", "csip"]):
        return "hongkong"
    if any(w in q for w in ["japan", "nict", "notice"]):
        return "japan"
    if any(w in q for w in ["nyc", "new york", "cyber command"]):
        return "nyc"
    return None


# ---------- 4. RETRIEVE RELEVANT SENTENCES ----------

def retrieve_evidence(query: str, region_hint: Optional[str]) -> List[str]:
    query_tokens = tokenize(query)

    if region_hint == "hongkong":
        regions = ["hongkong"]
    elif region_hint == "japan":
        regions = ["japan"]
    elif region_hint == "nyc":
        regions = ["nyc"]
    else:
        regions = ["hongkong", "japan", "nyc"]

    candidates: List[tuple[int, str]] = []

    for region in regions:
        urls = ALLOWED_SITES.get(region, [])
        for url in urls:
            page_text = fetch_text_from_url(url)
            if not page_text:
                continue
            sentences = split_into_sentences(page_text)
            for sent in sentences:
                sent_tokens = tokenize(sent)
                s = score_sentence(query_tokens, sent_tokens)
                if s > 0:
                    candidates.append((s, sent))

    if not candidates:
        return []

    candidates.sort(key=lambda x: x[0], reverse=True)

    # take up to 8 best sentences
    top_sentences = [c[1] for c in candidates[:8]]
    return top_sentences


# ---------- 5. LLM-LIKE ANSWER GENERATION ----------

def llm_like_response(query: str, evidence_sentences: List[str]) -> str:
    load_llm()  # <-- important lazy load

    if not evidence_sentences:
        # hybrid behaviour: honest + mild guidance
        return (
            "The official Hong Kong, NICT Japan, and NYC Cyber Command portals "
            "do not provide a detailed explanation of this specific topic. "
            "However, they emphasize strong cyber hygiene: updating systems, "
            "using secure authentication, monitoring threats, and following official "
            "government guidance to manage incidents safely."
        )

    context = " ".join(evidence_sentences)
    if len(context) > 2000:
        context = context[:2000]

    prompt = (
        "You are a cybersecurity assistant. Answer using only the information "
        "in the 'Information' section. You may generalize slightly, but do not "
        "invent specific facts that are not implied.\n\n"
        f"Question: {query}\n\n"
        f"Information: {context}\n\n"
        "Answer clearly and concisely:"
    )

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
    outputs = model.generate(
        **inputs,
        max_new_tokens=120,
        num_beams=2
    )
    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return answer


# ---------- 6. DIALOGFLOW WEBHOOK ENDPOINT ----------

@app.post("/webhook")
async def dialogflow_webhook(req: Request):
    data = await req.json()
    query_text = data.get("queryResult", {}).get("queryText", "")

    if not query_text:
        return {"fulfillmentText": "I didn't receive any query text."}

    region_hint = detect_region_hint(query_text)
    evidence = retrieve_evidence(query_text, region_hint)
    answer = llm_like_response(query_text, evidence)

    return {"fulfillmentText": answer}


@app.on_event("startup")
def preload_model():
    # Preload model in background so first user doesn't wait
    try:
        load_llm()
        print("🔥 Model preloaded successfully")
    except Exception as e:
        print("⚠️ Model preload failed (will lazy load on demand)", e)

