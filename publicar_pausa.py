"""Agenda no Buffer os posts de um dia da Pausa para refletir (06h, 11h30, 19h, Brasília).

Uso: python3 publicar_pausa.py 2026-11-03 [--teste]
     python3 publicar_pausa.py amanha
Dia N = data - 01/11/2026 (02/11 = Dia 1, só a noite; 03/11 = Dia 2).
Chave: BUFFER_API_KEY_PAUSA (variável de ambiente, nunca no código). Não usa a chave da café.
Vídeos: <BASE>/videos/dia-NN.[dan].mp4 ; legendas: textos.json (mesma pasta do repo).
"""
import json, os, sys, datetime, urllib.request

API = "https://api.buffer.com"
BASE = os.environ.get("PAUSA_VIDEO_BASE", "https://raw.githubusercontent.com/rogeriosuavinha-arch/pausa-para-refletir-videos/main")
TEXTOS = os.environ.get("PAUSA_TEXTOS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "textos.json"))
SLOTS = [("06:00", "d"), ("11:30", "a"), ("19:00", "n")]
BRT = datetime.timezone(datetime.timedelta(hours=-3))
INICIO = datetime.date(2026, 11, 1)
CANAL_NOME = "pausa.para_refletir"


def gql(query, variables=None):
    req = urllib.request.Request(API, json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 {"Content-Type": "application/json",
                                  "Authorization": f"Bearer {os.environ['BUFFER_API_KEY_PAUSA']}"})
    resp = json.load(urllib.request.urlopen(req, timeout=60))
    if resp.get("errors"):
        raise SystemExit(f"Erro do Buffer: {resp['errors']}")
    return resp["data"]


def canal():
    for org in gql("query { account { organizations { id } } }")["account"]["organizations"]:
        q = "query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id service name } }"
        for c in gql(q, {"o": org["id"]})["channels"]:
            if c["service"].lower() == "tiktok" and c["name"] == CANAL_NOME:
                return org["id"], c["id"]
    raise SystemExit(f"Canal {CANAL_NOME} não encontrado nesse Buffer.")


def ja_agendados(org, cid, data):
    q = "query($i: PostsInput!) { posts(first: 50, input: $i) { edges { node { dueAt } } } }"
    i = {"organizationId": org, "filter": {"channelIds": [cid],
         "dueAt": {"start": f"{data}T00:00:00-03:00", "end": f"{data}T23:59:59-03:00"}}}
    return {f"{datetime.datetime.fromisoformat(e['node']['dueAt'].replace('Z', '+00:00')).astimezone(BRT):%H:%M}"
            for e in gql(q, {"i": i})["posts"]["edges"]}


CRIAR = """mutation($i: CreatePostInput!) { createPost(input: $i) {
  ... on PostActionSuccess { post { id dueAt } } ... on MutationError { message } } }"""


def existe(url):
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30); return True
    except Exception:
        return False


def main():
    hoje = datetime.datetime.now(BRT).date()
    data = hoje + datetime.timedelta(1) if sys.argv[1] == "amanha" else datetime.date.fromisoformat(sys.argv[1])
    teste = "--teste" in sys.argv
    n = (data - INICIO).days
    T = json.load(open(TEXTOS))
    if str(n) not in T:
        raise SystemExit(f"Dia {n} ainda não tem texto/vídeo.")
    org, cid = (None, None) if teste else canal()
    feitos = set() if teste else ja_agendados(org, cid, data)
    agora = datetime.datetime.now(BRT)
    falhas = 0
    for hora, s in SLOTS:
        if n == 1 and s != "n":
            continue  # 02/11: só a noite (combinado com o Rogério)
        due = datetime.datetime.fromisoformat(f"{data}T{hora}:00-03:00")
        if due <= agora + datetime.timedelta(minutes=10):
            print(hora, "horário já passou, pulando"); continue
        if hora in feitos:
            print(hora, "já agendado, pulando"); continue
        url = f"{BASE}/videos/dia-{n:02d}.{s}.mp4"
        entrada = {"channelId": cid, "text": T[str(n)][s]["legenda"], "schedulingType": "automatic",
                   "mode": "customScheduled", "needsApproval": False, "dueAt": due.isoformat(),
                   "assets": [{"video": {"url": url}}]}
        if teste:
            print(json.dumps(entrada, ensure_ascii=False)); continue
        if not existe(url):
            print(hora, "vídeo não encontrado:", url); falhas += 1; continue
        r = gql(CRIAR, {"i": entrada})["createPost"]
        if not r.get("post"):
            falhas += 1
        print(hora, r.get("post") or r.get("message"))
    if falhas:
        raise SystemExit(f"{falhas} post(s) não agendado(s).")


if __name__ == "__main__":
    main()
