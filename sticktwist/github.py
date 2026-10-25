"""Small GitHub REST client used only inside Actions."""
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


class GitHub:
    def __init__(self):
        self.repo = os.environ['GITHUB_REPOSITORY']
        self.token = os.environ['GH_TOKEN']

    def request(self, path, method='GET', data=None, binary=False):
        url = path if path.startswith('https://') else f'https://api.github.com/repos/{self.repo}/{path}'
        payload = data if binary else (json.dumps(data).encode() if data is not None else None)
        req = urllib.request.Request(url, data=payload, method=method,
            headers={'Authorization':f'Bearer {self.token}', 'Accept':'application/vnd.github+json',
                     'X-GitHub-Api-Version':'2022-11-28',
                     'Content-Type':'application/octet-stream' if binary else 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as response:
            content = response.read()
        return json.loads(content) if content else None

    def releases(self):
        result = []
        for page in range(1,101):
            batch = self.request(f'releases?per_page=100&page={page}')
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise RuntimeError('Too many releases; refusing incomplete ledger lookup')

    def draft(self, tag, title, body=''):
        match = next((r for r in self.releases() if r['tag_name'] == tag),None)
        if match:
            if not match['draft']:
                raise RuntimeError('Expected unpublished draft release')
            return match
        return self.request('releases','POST',{'tag_name':tag, 'name':title, 'body':body,
             'target_commitish':os.environ.get('GITHUB_SHA','main'), 'draft':True, 'prerelease':True})

    def upload(self, release, path):
        path = Path(path)
        url = release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(path.name)
        return self.request(url,'POST',path.read_bytes(),binary=True)

    def download(self, asset, destination):
        url = f'https://api.github.com/repos/{self.repo}/releases/assets/{asset["id"]}'
        req = urllib.request.Request(url,headers={'Authorization':f'Bearer {self.token}',
                    'Accept':'application/octet-stream','X-GitHub-Api-Version':'2022-11-28'})
        # urllib strips no auth on redirect by default. GitHub's signed asset URL does not
        # need our bearer: handle the first redirect explicitly with an unauthenticated request.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            response = urllib.request.build_opener(NoRedirect).open(req,timeout=120)
        except urllib.error.HTTPError as error:
            if error.code not in {301,302,303,307,308}:
                raise
            target = error.headers['Location']
            if not target.startswith('https://'):
                raise RuntimeError('Unsafe asset redirect')
            response = urllib.request.urlopen(target,timeout=120)
        with response, open(destination,'wb') as output:
            while chunk := response.read(1048576):
                output.write(chunk)
