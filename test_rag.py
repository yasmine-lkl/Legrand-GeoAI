"""Quick end-to-end RAG test."""
import requests, json, sys

s = requests.Session()

# Login
r = s.post('http://localhost:8000/api/auth/login', json={"email":"admin@legrand-geoai.fr","password":"Admin123!"})
token = r.json()['access_token']
h = {'Authorization': f'Bearer {token}'}

# Get first collection
r = s.get('http://localhost:8000/api/collections/', params={"size":100}, headers=h)
cols = r.json()['items']
print(f"Collections: {[(c['name'], c['id']) for c in cols]}")
col_id = cols[0]['id']

# Chat query (streaming)
print("\n--- Sending RAG query ---")
r = s.post('http://localhost:8000/api/chat/query',
    headers={**h, 'Content-Type': 'application/json'},
    json={'message': 'Quel est le prix au m2?', 'collection_id': col_id},
    stream=True)
print(f"Status: {r.status_code}")

event_type = ""
answer = ""
for line in r.iter_lines(decode_unicode=True):
    if not line:
        continue
    if line.startswith("event:"):
        event_type = line.split(":", 1)[1].strip()
        continue
    if line.startswith("data:"):
        data = json.loads(line[5:].strip())
        if event_type == "sources":
            print(f"[SOURCES] {len(data['sources'])} sources found")
            for src in data['sources']:
                print(f"  - {src['filename']} pages={src['page_numbers']} score={src['score']:.2f}")
        elif event_type == "token":
            answer += data['content']
            sys.stdout.write(data['content'])
            sys.stdout.flush()
        elif event_type == "done":
            print(f"\n[DONE] tokens={data.get('tokens_used',0)}")
        elif event_type == "error":
            print(f"[ERROR] {data}")

print(f"\n--- Full answer ({len(answer)} chars) ---")
