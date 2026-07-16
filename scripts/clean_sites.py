import json
import re

with open("dr3/data/sites.json", "r", encoding="utf-8") as f:
    data = json.load(f)

original_count = len(data["sites"])
sites = data["sites"]
engines = data.get("engines", {})
tags_to_remove = {"ru", "porn", "erotic", "dating", "forum", "gaming", "gambling"}
bad_tlds = {".ru", ".su", ".by", ".kz"}

cleaned_sites = {}
for name, info in sites.items():
    # check bad tlds
    url = info.get("urlMain", "").lower()
    if any(tld in url for tld in bad_tlds):
        continue
    if any(tld in name.lower() for tld in bad_tlds):
        continue
        
    # check tags
    site_tags = set([t.lower() for t in info.get("tags", [])])
    if site_tags.intersection(tags_to_remove):
        # Allow steam, xbox, psn even if gaming
        if name.lower() not in {"steam", "xbox", "playstation", "psn"}:
            continue
            
    # keep it
    cleaned_sites[name] = info

print(f"Original sites: {original_count}")
print(f"Cleaned sites: {len(cleaned_sites)}")

# Prioritize the required platforms
priority_order = [
    "Facebook", "Instagram", "Telegram", "Twitter", "X", "GitHub", 
    "LinkedIn", "TikTok", "YouTube", "Reddit", "Discord", "Steam"
]

# We don't need to reorder the dict exactly, but we can assign a priority field or sort them
for name in cleaned_sites:
    n = name.lower()
    rank = 999
    for i, p in enumerate(priority_order):
        if p.lower() in n:
            rank = i
            break
    cleaned_sites[name]["priority"] = rank

# Sort dict by priority, then by alexaRank
sorted_sites = dict(sorted(cleaned_sites.items(), key=lambda item: (item[1].get("priority", 999), item[1].get("alexaRank", 999999) or 999999)))

data["sites"] = sorted_sites

with open("dr3/data/sites.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Saved cleaned sites.json")
