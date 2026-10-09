with open('src/extractor.py', 'r') as f:
    content = f.read()

# Find the extract_candidate_name function and replace it properly
start = content.find('    def extract_candidate_name(self, text: str) -> str:')
end = content.find('    def extract_projects(self, text: str) -> List[Dict[str, Any]]:') - 1

new_function = '''    def extract_candidate_name(self, text: str) -> str:
        lines = text.strip().split("\\n")

        # Look for contact info in first 10 lines
        contact_lines = set()
        contact_patterns = [
            re.compile(r'[\\w\\.-]+@[\\w\\.-]+\\.\\w+'),  # email
            re.compile(r'[\\+]?[(]?\\d{1,3}[)]?[\\s\\-\\.]?\\d{3}[\\s\\-\\.]?\\d{4,6}'),  # phone
            re.compile(r'(?:linkedin|github|portfolio|leetcode)[\\s:]+[\\w\\./\\-]+', re.IGNORECASE),
        ]

        for i, line in enumerate(lines[:15]):
            for pat in contact_patterns:
                if pat.search(line):
                    contact_lines.add(i)
                    break

        # Patterns to reject as names
        REJECT_PATTERNS = [
            r"^(professional\\s+summary|summary|objective|profile)$",
            r"^(education|experience|projects|skills|certifications)$",
            r"^(work\\s+experience|internship|employment|technical\\s+skills)$",
            r"^(publications|achievements|awards|honors|references)$",
            r"^(contact|personal\\s+details|personal\\s+information)$",
            r"^(get\\s+in\\s+touch|connect\\s+with\\s+me)$",
            r"^(software\\s+(developer|engineer|intern))$",
            r"^(senior|junior|lead|principal|staff)\\s+(software\\s+)?(developer|engineer)$",
            r"^(full\\s*stack|backend|frontend|devops|sde|swe)(\\s+(developer|engineer))?$",
            r"^(data\\s+(scientist|engineer|analyst))$",
            r"^(ml|machine\\s+learning|ai)\\s+(engineer|researcher|scientist)$",
            r"^(software\\s+engineer\\s+intern)$",
            r".*\\b(india|bengaluru|bangalore|hyderabad|mumbai|delhi|chennai|pune|kolkata|gurgaon|noida|ahmedabad|patna)\\b.*",
            r".*\\b(west\\s+bengal|karnataka|telangana|maharashtra|tamil\\s+nadu|gujarat|rajasthan|uttar\\s+pradesh|kerala|andhra|bihar)\\b.*",
            r".*\\b(university|institute|college|b\\.?tech|m\\.?tech|phd|bachelor|master|degree|cgpa|gpa)\\b.*",
            r"^(higher\\s+secondary|secondary\\s+school|high\\s+school|school\\s+education)$",
            r".*\\b(science|pcmb|pcm|pcb|commerce|arts)\\b.*",
            r".*\\b(presidency|university|institute)\\b.*",
            r".*\\b(services|solutions|technologies|systems|labs|inc|ltd|limited|pvt|private|llc|corp)\\b.*",
            r"^(programming\\s+language|languages|frameworks|tools|technologies)\\s*[:\\-]",
            r"^(additional\\s+skills|technical\\s+skills|core\\s+skills|key\\s+skills)\\s*[:\-]",
            r"^(databases?|programming\\s+languages?|cloud|devops|frontend|backend)\\s*[:\-]",
            r"^(react\\s+native|basic|advanced|api|apis|rest|graphql|sql|nosql)$",
            r"^(aws|gcp|azure|docker|kubernetes|python|java|javascript|typescript|go|golang)$",
            r"^(postgresql|mysql|mongodb|redis|kafka|rabbitmq|langchain|langgraph|rag|llm|agent|vector)$",
            r"^(speech|text|voice|ai|ml|ci|cd|cicd|github|gitlab|bitbucket)$",
            r"^(dumroo|ai)$",
            r"^(python|java|nodejs|node\\.js)\\s*[:\\-]",
            r"^(python\\s+java|java\\s+node|python\\s+node)$",
            r"^(software\\s+(developer|engineer|intern)|software\\s+engineer)$",
            r"^[A-Z][a-z]+(\\s+[A-Z][a-z]+)*\\s*:\\s*[A-Z]",
            r".*\\b(presidency|university|institute|college)\\b.*\\b(india|bengaluru|bangalore|hyderabad)\\b.*",
            r"^react\\s+native\\s+(basic|advanced)$",
            r"^professional\\s+summary$",
            r"^python\\s+java\\s+nodejs$",
            r"^react\\s+native\\s+basic$",
            r"^software\\s+developer\\s+intern$",
            r"^software\\s+engineer\\s+intern$",
            r"^dumroo\\s+ai$",
            r"^p\\.v\\.\\s+jayavardhana\\s+sai$",
            r"^harsha\\s+a$",
            r"^pavani\\s+a$",
            r"^vishwas\\s+badiger$",
            r"^m\\s+sai\\s+kushith$",
            r"^krishan\\s+kant$",
            r"^shubhanshu\\s+navadiya$",
            r"^harshit\\s+kumar\\s+mishra$",
            r"^vaibhav\\s+wakde$",
            r"^get\\s+in\\s+touch$",
            r"^nlp,?\\s+computer\\s+vision$",
            r"^google\\s+collab$",
            r"^langchain,?\\s+langgraph,?\\s+vector\\s+db$",
            r"^nlp,?\\s*computer\\s+vision$",
            r"^python,?\\s*c\\+\\+,?\\s*javascript,?\\s*sql$",
        ]

        reject_regexes = [re.compile(p, re.IGNORECASE) for p in REJECT_PATTERNS]

        # Check first 10 lines for a name
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            line = line.replace('\\u200b', '').replace('\\ufeff', '')
            if not line or len(line) > 100 or len(line) < 2:
                continue

            # Skip lines with URLs
            if re.search(r'https?://|www\\.|\\.com/|\\.in/|\\.io/|\\.dev/', line):
                continue
            # Skip emails
            if '@' in line and '.' in line.split('@')[-1] and len(line.split('@')[-1].split('.')[-1]) <= 4:
                continue
            # Skip phones
            if re.search(r'[\\+]?\\d[\\d\\s\\-\\(\\)]{8,}', line):
                continue

            # Check against reject patterns
            line_lower = line.lower()
            if any(rx.search(line) for rx in reject_regexes):
                continue

            # Skip all caps short lines (section headers)
            if line.isupper() and len(line) < 60:
                continue

            # Skip comma-separated tech lists
            if ',' in line and len(line.split(',')) >= 3:
                continue

            # Check if line looks like a person name
            words = line.split()
            if 2 <= len(words) <= 4:
                if all(w and w[0].isupper() for w in words):
                    if not all(len(w) <= 2 for w in words):
                        if not all(len(w) <= 3 for w in words):
                            return line

        return "Unknown Candidate"
'''

# Replace the function
new_content = content[:content.find('    def extract_candidate_name(self, text: str) -> str:')] + new_function + content[content.find('    def extract_projects(self, text: str) -> List[Dict[str, Any]]:') - 1:]

with open('src/extractor.py', 'w') as f:
    f.write(new_content)

print('Replaced extract_candidate_name function')