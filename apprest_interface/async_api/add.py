import treq
from twisted.internet import task, reactor
from twisted.web.client import HTTPConnectionPool

import os, configparser, requests, json, argparse, ast

os.environ['INTERFACE_CONF_FILE'] = '/home/jjorissen/interface_secrets.conf'
SECRETS_LOCATION = os.environ.get('INTERFACE_CONF_FILE')
SECRETS_LOCATION = os.path.abspath(SECRETS_LOCATION) if SECRETS_LOCATION else 'apprest.conf'

config = configparser.ConfigParser()
config.read(SECRETS_LOCATION)

ENDPOINT = config.get('app_rest', 'endpoint')
USERNAME = config.get('app_rest', 'username')
PASSWORD = config.get('app_rest', 'password')

cooperator = task.Cooperator()
pool = HTTPConnectionPool(reactor)
responses = []

class ConnectionError(BaseException):
    pass


class APICallError(BaseException):
    pass


class CallAdd:
    endpoint = ENDPOINT
    username = USERNAME
    password = PASSWORD

    def __init__(self, *args, **kwargs):
        for key, value in kwargs.items():
            if (key in ['endpoint', 'username', 'password']) and not value:
                kwargs[key] = self.__getattribute__(key)
        params = {"username": self.username, "password": self.password}
        response = requests.post(f'{self.endpoint}/api/auth/login/', auth=requests.auth.HTTPBasicAuth(**params))
        response_dict = json.loads(response.text)
        if 'token' not in response_dict.keys():
            raise ConnectionError('Could not establish a connection to the API. Please check your credentials.')
        self.auth_token = response_dict['token']
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.auth_token}'
        }

    def _format_entity(self, entity):
        if entity is not None and not entity.endswith('s'):
            entity += 's'
        if issubclass(entity.__class__, str):
            entity = entity.lower()
        return entity

    def add(self, entity, requests):
        # print(type(requests[0]))
        # print(requests[0])
        try:
            for i, request in enumerate(requests):
                requests[i] = ast.literal_eval(request)
        except:
            print(f'could not evaluate requests {requests}')
            pass
        requests = requests[0]

        self.req_generated, self.req_completed = 0, 0
        entity = self._format_entity(entity)

        def collect(response):
            responses.append(response.decode("utf-8"))

        def request_done(response, self):
            self.req_completed += 1
            deferred = treq.content(response)
            deferred.addCallback(collect)
            # deferred.addCallback(collect)
            deferred.addErrback(lambda x: print(x))  # ignore errors
            if self.req_completed == len(requests):
                reactor.stop()
            return deferred

        def request(self, entity, request_kwargs):
            headers = request_kwargs['headers']
            data = ast.literal_eval(request_kwargs['data'])
            deferred = treq.post(f'{self.endpoint}/{entity}/', data, headers=headers)
            deferred.addCallback(request_done, self)
            return deferred

        def requests_generator(self, entity, requests):
            while self.req_generated < len(requests):
                deferred = request(self, entity, requests[self.req_generated])
                self.req_generated += 1
                yield None

        cooperator.cooperate(requests_generator(self, entity, requests))
        reactor.run()

        return responses


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='pass some arguments.')
    parser.add_argument('entity', metavar='N', type=str,
                        help='an entity to be passed to all')
    parser.add_argument('-k','--kwargs', type=str, nargs='+')
    # kwargs = parser.parse_args().kwargs
    # print(entity, kwargs)
    print(CallAdd().add(parser.parse_args().entity, parser.parse_args().kwargs))