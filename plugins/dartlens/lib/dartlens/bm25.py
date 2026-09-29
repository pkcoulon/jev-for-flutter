import math
import re
from collections import Counter

STOP = set("""
a an and are as at be but by can do does for from has have how i if in into is it its of on or should so than that the
their then there these this to was were what when where which while who why will with would you your not no yes any all
le la les un une des de du d l et ou en dans pour par sur avec sans que qui quoi quel quelle quels quelles est sont
être fait faire ce cet cette ces se sa son ses leur leurs au aux ne pas plus il elle ils elles on nous vous je tu y
comment où quand dont mais donc car si comme
""".split())
WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+")
PART = re.compile(r"[A-Z]+(?=[A-Z][a-zà-ÿ])|[A-ZÀ-Ö]?[a-zà-ÿ]+|[A-ZÀ-Ö]+|\d+")


def _stem(token):
    if len(token) > 3 and token[-1] in "sx" and token[-2] != "s":
        return token[:-1]
    return token


def tokens(text):
    out = []
    for word in WORD.findall(text or ""):
        parts = PART.findall(word) or [word]
        for part in parts:
            part = part.lower()
            if len(part) > 1 and part not in STOP:
                out.append(_stem(part))
        if len(parts) > 1:
            out.append(word.lower())
    return out


class BM25:
    def __init__(self, documents, k1=1.2, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(d) if isinstance(d, str) else d) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.docs else 0.0
        self.df = Counter()
        for doc in self.docs:
            self.df.update(doc.keys())

    def idf(self, term):
        n, df = len(self.docs), self.df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def scores(self, query):
        terms = sorted(set(tokens(query) if isinstance(query, str) else query))
        out = []
        for doc, length in zip(self.docs, self.lengths):
            total = 0.0
            for term in terms:
                tf = doc.get(term)
                if tf:
                    norm = 1 - self.b + self.b * length / (self.avgdl or 1)
                    total += self.idf(term) * tf * (self.k1 + 1) / (tf + self.k1 * norm)
            out.append(total)
        return out


def rank(query, documents):
    scores = BM25(documents).scores(query)
    return sorted(((i, s) for i, s in enumerate(scores)), key=lambda item: item[1], reverse=True)
