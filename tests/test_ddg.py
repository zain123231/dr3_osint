import urllib.request
from bs4 import BeautifulSoup

url = 'https://html.duckduckgo.com/html/?q=site:instagram.com+zuck'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')

soup = BeautifulSoup(html, 'html.parser')
results = soup.find_all('a', class_='result__url')
snippets = soup.find_all('a', class_='result__snippet')

for r, s in zip(results, snippets):
    print("URL:", r.text.strip())
    print("Snippet:", s.text.strip())
