with open('src/extractor.py', 'rb') as f:
    content = f.read()
idx = content.find(b'return "Unknown Candidate"')
if idx >= 0:
    print(content[idx-100:idx+100].decode('utf-8', errors='replace'))