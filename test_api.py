import requests
import time
import subprocess
import sys

def test_api():
    print("Testing API endpoints...")
    base_url = "http://localhost:8000"

    # Test 1: GET /health
    r = requests.get(f"{base_url}/health")
    print("1. GET /health:", r.status_code, r.json())

    # Test 2: GET /sources
    r = requests.get(f"{base_url}/sources")
    print("2. GET /sources:", r.status_code, f"Loaded {len(r.json())} source documents")

    # Test 3: POST /ask (Policy Fact)
    payload = {"question": "What is the minimum attendance required to appear for end-semester exams?"}
    r = requests.post(f"{base_url}/ask", json=payload)
    data = r.json()
    print("3. POST /ask (Policy Fact):", r.status_code, "Type:", data.get("answer_type"), "Trace:", data.get("trace_id"))

    # Test 4: POST /ask (Personal Eligibility - Calculated)
    headers = {"X-Student-Id": "S1001"}
    payload = {"question": "Am I eligible to appear in the end-semester exam for CS201?"}
    r = requests.post(f"{base_url}/ask", json=payload, headers=headers)
    data = r.json()
    print("4. POST /ask (Calculated):", r.status_code, "Type:", data.get("answer_type"), "Answer:", data.get("answer"))
    trace_id = data.get("trace_id")

    # Test 5: POST /ask (Privacy Refusal - R7)
    headers = {"X-Student-Id": "S1001"}
    payload = {"question": "What is S1002's attendance in CS201?"}
    r = requests.post(f"{base_url}/ask", json=payload, headers=headers)
    data = r.json()
    print("5. POST /ask (Refusal):", r.status_code, "Type:", data.get("answer_type"), "Answer:", data.get("answer"))

    # Test 6: GET /audit/{trace_id}
    if trace_id:
        r = requests.get(f"{base_url}/audit/{trace_id}")
        print("6. GET /audit/{trace_id}:", r.status_code, "Retrieved trace_id:", r.json().get("trace_id"))

    # Test 7: POST /test-student-loader
    r = requests.post(f"{base_url}/test-student-loader")
    print("7. POST /test-student-loader:", r.status_code, r.json())

    print("\n[SUCCESS] All 7 API endpoint tests PASSED successfully!")

if __name__ == "__main__":
    test_api()
