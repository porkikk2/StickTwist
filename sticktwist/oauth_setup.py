"""One-time desktop OAuth only; does not process or upload video."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--client',required=True,help='Google Desktop app OAuth JSON')
    p.add_argument('--output',default='token.youtube.json')
    args = p.parse_args()
    from google_auth_oauthlib.flow import InstalledAppFlow
    scopes = ['https://www.googleapis.com/auth/youtube.upload',
              'https://www.googleapis.com/auth/youtube.readonly']
    flow = InstalledAppFlow.from_client_secrets_file(args.client,scopes)
    creds = flow.run_local_server(port=0,access_type='offline',prompt='consent')
    if not creds.refresh_token:
        raise RuntimeError('No refresh token; repeat consent before configuring Actions')
    Path(args.output).write_text(creds.to_json(),encoding='utf-8')
    print('OAuth token saved locally. Add its contents as YOUTUBE_TOKEN_JSON in repository secrets; never commit it.')


if __name__ == '__main__':
    main()
