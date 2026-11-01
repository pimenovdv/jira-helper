from bs4 import BeautifulSoup
html = "&lt;!-- AUTO_GENERATED_MISSING_DUE_DATE_WARNING --&gt;"
soup = BeautifulSoup(html, "html.parser")
print(soup.text)
