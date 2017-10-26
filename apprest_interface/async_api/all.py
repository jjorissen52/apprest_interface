import treq
from twisted.internet import task, reactor
from twisted.web.client import HTTPConnectionPool

import os, configparser, requests, json, argparse

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


class CallAll:
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

    def all(self, entities):

        self.req_generated, self.req_completed = 0, 0
        for i, entity in enumerate(entities):
            entities[i] = self._format_entity(entity)

        def collect(response):
            responses.append(response.decode("utf-8"))

        def request_done(response, self):
            self.req_completed += 1
            deferred = treq.content(response)
            deferred.addCallback(collect)
            # deferred.addCallback(collect)
            deferred.addErrback(lambda x: print(x))  # ignore errors
            if self.req_completed == len(entities):
                reactor.stop()
            return deferred

        def request(self, entity, request_kwargs):
            deferred = treq.get(f'{self.endpoint}/{entity}/', **request_kwargs)
            deferred.addCallback(request_done, self)
            return deferred

        def requests_generator(self, request_kwargs):
            while self.req_generated < len(entities):
                deferred = request(self, entities[self.req_generated],request_kwargs)
                self.req_generated += 1
                yield None

        request_kwargs = {"headers": self.headers}
        cooperator.cooperate(requests_generator(self, request_kwargs))
        reactor.run()

        # print(responses)
        return responses


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='pass some arguments.')
    parser.add_argument('entity', metavar='N', type=str, nargs='+',
                        help='an entity to be passed to all')
    args = parser.parse_args()
    print(CallAll().all(args.entity))