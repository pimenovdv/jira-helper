import gitlab
from datetime import datetime, timezone
import dateutil.parser

gl = gitlab.Gitlab("https://gitlab.com")
project = gl.projects.get('gitlab-org/gitlab-foss')
branches = project.branches.list(per_page=1)
if branches:
    b = branches[0]
    print(b.attributes['commit']['committed_date'])
    dt = dateutil.parser.isoparse(b.attributes['commit']['committed_date'])
    now = datetime.now(timezone.utc)
    print(dt)
    print((now - dt).days)
