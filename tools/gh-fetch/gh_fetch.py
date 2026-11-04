"""Fetch a file from the records repo via the platform GitHub tool.

Usage: gh_fetch.py <path> [owner] [repo]
Owner/repo default to RECORDS_OWNER / RECORDS_REPO from the environment.
"""
import json, os, subprocess, sys
def fetch(path, owner=None, repo=None):
    owner = owner or os.environ.get("RECORDS_OWNER")
    repo = repo or os.environ.get("RECORDS_REPO")
    if not owner or not repo:
        return None, "set RECORDS_OWNER and RECORDS_REPO, or pass owner and repo as argv[2]/argv[3]"
    args = json.dumps({"owner": owner, "repo": repo, "path": path})
    out = subprocess.run([os.environ.get("GITHUB_CLI", "github"),"call-read-tool","--name","get_file_contents","--arguments-json",args], capture_output=True, text=True)
    try:
        d = json.loads(out.stdout)
    except Exception:
        return None, out.stdout[:500] + out.stderr[:500]
    for c in d.get('result',{}).get('content',[]):
        if 'resource' in c and 'text' in c['resource']:
            return c['resource']['text'], None
        if c.get('type')=='text' and not c['text'].startswith('successfully'):
            try:
                return json.loads(c['text']), None
            except Exception:
                return c['text'], None
    return None, 'no content: '+out.stdout[:300]
if __name__ == '__main__':
    res, err = fetch(sys.argv[1], *(sys.argv[2:4]))
    if err: print('ERR', err, file=sys.stderr)
    elif isinstance(res, list):
        for it in res: print(it['type'], it['name'], it.get('size',''))
    else:
        print(res)
