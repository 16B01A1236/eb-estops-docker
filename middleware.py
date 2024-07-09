
from python_amazon_interceptor import amazon_handler
from python_amazon_interceptor.amazon_handler import Config



environment_config = Config(
      auth_path="https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize",
      auth_redirect_path="https://idp-integ.federate.amazon.com/api/oauth2/v1/authorize",
      client_id="estops-ui-beta",
      identity_provider_host="idp-integ.federate.amazon.com",
      jwks_url="https://idp-integ.federate.amazon.com/api/oauth2/v2/certs",
      redirect_uri="",
)

class MidwayMiddleWare:
    def __init__(self, application):
       # self.config = environment_config
        self.app = application
        print('in init')

    def __call__(self, environment, start_response):
        print('in __call__',environment)
        environment["HTTP_HOST"] = "estops.beta-eu.quartz.rme.amazon.dev"
        handler = amazon_handler.AmazonHandlerRequest(environment, environment_config)
        response = handler.authenticate()
        
        # Request is intercepted by the interceptor
        if response:
            start_response(response.status, response.headers)
            return [b"Auth Done!"]
        else:
            return self.app