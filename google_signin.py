"""Sign in with Google (v0.29.0, F26, DEC-031): the OpenID Connect "authorization code" flow with PKCE.

    start(purpose)   ->  the Google address to send the browser to (state, nonce and PKCE secret kept in the session)
    finish(args)     ->  (claims, purpose, extra) after every check below, or GoogleProblem with a plain message

Google's answer is never trusted as it comes: the state must match, the ID token's signature must be Google's, and
its issuer, audience, expiry, nonce and email_verified are checked here (plan §2.3). Only exchange_code() and
fetch_keys() talk to Google; the tests replace those two and keep every check (rule T3).
The scopes are "openid email profile" only: no access to anyone's Gmail inbox.
"""
import secrets
import time
from flask import current_app, request, session, url_for
from common import same_secret

AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
KEYS_URL = 'https://www.googleapis.com/oauth2/v3/certs'
ISSUERS = ['https://accounts.google.com', 'accounts.google.com']
SCOPES = 'openid email profile'
TIMEOUT_SECONDS = 10
STARTED_MINUTES = 10      # the trip to Google and back must finish within 10 minutes
LEEWAY_SECONDS = 60       # a computer clock a little off still accepts a fresh token


class GoogleProblem(Exception):
    """Google sign-in didn't work; the message says why in plain words (rule C6)."""


# ---------------- Is it set up, and can it work on this address? ----------------
def settings():
    """{'client_id', 'client_secret'} from [google] in config.toml (or the environment), or None if not set up."""
    values = current_app.config.get('GOOGLE') or {}
    return values if values.get('client_id') and values.get('client_secret') else None


def works_here():
    """Google accepts only http://localhost or an https address as the return address (plan §2.3)."""
    return request.host.split(':')[0] == 'localhost' or request.scheme == 'https'


def where_it_works():
    """For the login page: the address on which Google sign-in works on this computer."""
    port = request.host.split(':')[1] if ':' in request.host else ''
    return f'http://localhost{":" + port if port else ""}'


def callback_url():
    return url_for('accounts.google_callback', _external=True)


def check_settings(values):
    """Check Google settings typed into setup_shop.py. Returns (settings, None) or (None, a plain message)."""
    client_id = str(values.get('client_id') or '').strip()
    secret = str(values.get('client_secret') or '').strip()
    if not client_id.endswith('.apps.googleusercontent.com') or len(client_id) > 200 or ' ' in client_id:
        return None, 'The Google client ID ends with ".apps.googleusercontent.com" (copy it from Google Cloud).'
    if not secret or len(secret) > 200 or ' ' in secret:
        return None, 'The Google client secret is required (copy it from Google Cloud, no spaces).'
    return {'client_id': client_id, 'client_secret': secret}, None


# ---------------- The trip to Google and back ----------------
def _client(values, verifier=None):
    from authlib.integrations.requests_client import OAuth2Session
    return OAuth2Session(values['client_id'], values['client_secret'], scope=SCOPES, redirect_uri=callback_url(),
                         code_challenge_method='S256', default_timeout=TIMEOUT_SECONDS)


def start(purpose, extra=None):
    """Remember why we go to Google ('login', 'link' or 'signup') and three random secrets, then return Google's
    address. state: the answer belongs to this browser; nonce: the token was made for this trip; PKCE verifier: only
    this server can exchange the code."""
    values = settings()
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    session['google'] = {'state': state, 'nonce': nonce, 'verifier': verifier, 'purpose': purpose,
                         'extra': extra, 'at': time.time()}
    url, _ = _client(values).create_authorization_url(AUTHORIZE_URL, state=state, code_verifier=verifier,
                                                      nonce=nonce, prompt='select_account')
    return url


def exchange_code(values, code, verifier):
    """Network: Google's token address turns the one-time code into tokens. Replaced in the tests."""
    return _client(values).fetch_token(TOKEN_URL, code=code, code_verifier=verifier)


def fetch_keys():
    """Network: Google's current public keys, to check the token's signature. Replaced in the tests."""
    import requests
    response = requests.get(KEYS_URL, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def check_id_token(id_token, keys, client_id, nonce, now=None):
    """Check the ID token completely and return its claims, or raise GoogleProblem (plan §2.3)."""
    from joserfc import jwt, errors
    from joserfc.jwk import KeySet
    try:
        token = jwt.decode(id_token, KeySet.import_key_set(keys), algorithms=['RS256'])   # Google's signature
        jwt.JWTClaimsRegistry(now=int(now if now is not None else time.time()), leeway=LEEWAY_SECONDS,
                              iss={'essential': True, 'values': ISSUERS}, aud={'essential': True, 'value': client_id},
                              exp={'essential': True}, sub={'essential': True},
                              nonce={'essential': True, 'value': nonce}).validate(token.claims)
    except errors.ExpiredTokenError:
        raise GoogleProblem('Google\'s answer was too old. Please try again.')
    except (errors.JoseError, ValueError, KeyError, TypeError) as error:
        current_app.logger.warning('Google sign-in refused: %r', error)
        raise GoogleProblem('Google\'s answer could not be checked, so it was refused. Please try again.')
    claims = token.claims
    if claims.get('email_verified') is not True or not claims.get('email'):
        raise GoogleProblem('This Google account\'s email address is not verified by Google, so it can\'t be used.')
    return claims


def finish(args):
    """Back from Google: every check, then (claims, purpose, extra). The started trip is used once."""
    started = session.pop('google', None) or {}
    if args.get('error'):
        raise GoogleProblem('Google sign-in was cancelled. Nothing was changed.')
    if (not started or time.time() - started.get('at', 0) > STARTED_MINUTES * 60
            or not same_secret(args.get('state', ''), started.get('state', ''))):
        raise GoogleProblem('That Google sign-in didn\'t start here or took too long. Please start again.')
    values = settings()
    if values is None:
        raise GoogleProblem('Google sign-in is not set up in this shop.')
    import requests
    try:
        tokens = exchange_code(values, args.get('code', ''), started['verifier'])
        keys = fetch_keys()
    except requests.RequestException as error:
        current_app.logger.warning('Google sign-in: could not reach Google (%r)', error)
        raise GoogleProblem('Could not reach Google. Check the internet connection, or log in with your password.')
    except Exception as error:   # Authlib's OAuth errors: a used or wrong code, a wrong client secret
        current_app.logger.warning('Google sign-in: the code was refused (%r)', error)
        raise GoogleProblem('Google refused this sign-in. Please start again.')
    claims = check_id_token((tokens or {}).get('id_token', ''), keys, values['client_id'], started['nonce'])
    return claims, started.get('purpose'), started.get('extra')
