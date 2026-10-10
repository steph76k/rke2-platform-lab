"""Authorization-code login for explicitly supplied temporary test identities."""
import secrets
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse
import requests
from afi_platform import CONFIG, kv

class LoginForm(HTMLParser):
    action = None
    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'form' and attributes.get('id') == 'kc-form-login':
            self.action = attributes['action']

def access_token(identity):
    client = kv('oidc/afi-opensearch')
    realm = CONFIG['keycloak'] + '/realms/' + CONFIG['realm'] + '/protocol/openid-connect/'
    redirect = CONFIG['clients']['afi-opensearch']['callback']
    session = requests.Session()
    state = secrets.token_urlsafe(24)
    r = session.get(realm + 'auth', params={'client_id': 'afi-opensearch',
        'redirect_uri': redirect, 'response_type': 'code', 'scope': 'openid profile email',
        'state': state}, timeout=30)
    r.raise_for_status()
    form = LoginForm()
    form.feed(r.text)
    assert form.action
    target, expected = urlparse(form.action), urlparse(CONFIG['keycloak'])
    assert target.scheme == 'https' and target.netloc == expected.netloc
    r = session.post(form.action, data={'username': identity['username'],
        'password': identity['password']}, allow_redirects=False, timeout=30)
    assert r.status_code == 302
    callback, expected_callback = urlparse(r.headers['Location']), urlparse(redirect)
    assert (callback.scheme, callback.netloc, callback.path) == (
        expected_callback.scheme, expected_callback.netloc, expected_callback.path)
    query = parse_qs(callback.query)
    assert query.get('state') == [state] and 'code' in query
    r = session.post(realm + 'token', data={'grant_type': 'authorization_code',
        'code': query['code'][0], 'client_id': 'afi-opensearch',
        'client_secret': client['client_secret'], 'redirect_uri': redirect}, timeout=30)
    r.raise_for_status()
    return r.json()['access_token']
