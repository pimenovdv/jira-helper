from bs4 import BeautifulSoup
html1 = "&lt;!-- AUTO_GENERATED_MISSING_DUE_DATE_WARNING --&gt;"
html2 = "<!-- AUTO_GENERATED_MISSING_DUE_DATE_WARNING -->"
print("Text1:", repr(BeautifulSoup(html1, "html.parser").text))
print("Text2:", repr(BeautifulSoup(html2, "html.parser").text))
