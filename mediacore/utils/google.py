import logging

from oauth2client.client import OAuth2WebServerFlow, Credentials

from mediacore.model.settings import Settings


logger = logging.getLogger(__name__)


def get_auth_flow():
    settings = Settings.get_settings('google_api')
    if settings.get('client_id') \
            and settings.get('client_secret') \
            and settings.get('oauth_scope') \
            and settings.get('redirect_uri'):
        return OAuth2WebServerFlow(
                client_id=settings['client_id'],
                client_secret=settings['client_secret'],
                scope=settings['oauth_scope'],
                redirect_uri=settings['redirect_uri'],
                access_type='offline',
                approval_prompt='force',
                )

def get_auth_url():
    flow = get_auth_flow()
    return flow.step1_get_authorize_url() if flow else None

def set_credentials(token):
    flow = get_auth_flow()
    if not flow:
        return False
    try:
        credentials = flow.step2_exchange(token)
    except Exception, e:
        logger.error('failed to validate google auth token: %s', str(e))
        return False

    Settings.set_setting('google_api_credentials',
            'credentials', Credentials.to_json(credentials))
    # refresh_token = credentials.refresh_token
    # if refresh_token:
    #     Settings.set_setting('google_api_credentials',
    #             'refresh_token', refresh_token)
    return True
