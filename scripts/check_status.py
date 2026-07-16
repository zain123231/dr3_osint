import requests

def check(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0 Safari/537.36'}, allow_redirects=False)
        print(f"{url} -> {r.status_code}")
        if r.status_code == 302 or r.status_code == 301:
            print(f"  Redirects to: {r.headers.get('Location')}")
    except Exception as e:
        print(f"{url} -> Error: {e}")

check("https://www.instagram.com/zuck/")
check("https://www.instagram.com/this_user_does_not_exist_123456789/")
check("https://www.facebook.com/zuck")
check("https://www.facebook.com/this_user_does_not_exist_123456789")
