from jira import JIRA
import requests

options = {"server": "https://jira.atlassian.com"}
j = JIRA(options=options)
issue = j.issue('JRA-9')
print(dir(issue.fields.status))
print(issue.fields.status.name)
