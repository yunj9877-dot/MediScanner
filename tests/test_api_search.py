import httpx, os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("DATA_GO_KR_API_KEY")
url = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

# 테스트 1: 성분명으로 검색
print("=== 테스트 1: 성분명 '아세트아미노펜' ===")
r = httpx.get(url, params={"serviceKey": key, "type": "json", "numOfRows": "3", "itemName": "아세트아미노펜"})
data = r.json()
items = data.get("body", {}).get("items", [])
print(f"결과: {len(items)}건")
for i in items[:3]:
    print(f"  제품명: {i.get('itemName', '')}")

# 테스트 2: 다른 성분명
print("\n=== 테스트 2: 성분명 '이부프로펜' ===")
r = httpx.get(url, params={"serviceKey": key, "type": "json", "numOfRows": "3", "itemName": "이부프로펜"})
data = r.json()
items = data.get("body", {}).get("items", [])
print(f"결과: {len(items)}건")
for i in items[:3]:
    print(f"  제품명: {i.get('itemName', '')}")

# 테스트 3: 약 이름
print("\n=== 테스트 3: 약 이름 '타이레놀' ===")
r = httpx.get(url, params={"serviceKey": key, "type": "json", "numOfRows": "3", "itemName": "타이레놀"})
data = r.json()
items = data.get("body", {}).get("items", [])
print(f"결과: {len(items)}건")
for i in items[:3]:
    print(f"  제품명: {i.get('itemName', '')}")

print("\n=== 성분명 '루테인' ===")
r = httpx.get(url, params={"serviceKey": key, "type": "json", "numOfRows": "3", "itemName": "루테인"})
items = r.json().get("body", {}).get("items", [])
print(f"결과: {len(items)}건")
for i in items[:3]:
    print(f"  {i.get('itemName', '')}")
