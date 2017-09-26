import os, configparser, requests, json

os.environ['INTERFACE_CONF_FILE'] = '/home/jjorissen/interface_secrets.conf'
SECRETS_LOCATION = os.environ.get('INTERFACE_CONF_FILE')
SECRETS_LOCATION = os.path.abspath(SECRETS_LOCATION) if SECRETS_LOCATION else 'apprest.conf'

config = configparser.ConfigParser()
config.read(SECRETS_LOCATION)

ENDPOINT = config.get('app_rest', 'endpoint')
USERNAME = config.get('app_rest', 'username')
PASSWORD = config.get('app_rest', 'password')


class ConnectionError(BaseException):
    pass


class APICallError(BaseException):
    pass


class APPRestConnection:
    endpoint = ENDPOINT
    username = USERNAME
    password = PASSWORD

    def __init__(self, **kwargs):
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

    def _handle_status_code(self, response):
        if response.status_code == 404:
            return {f"Error {response.status_code}": "Record did not exist."}
        if response.status_code == 403:
            return {f"Error {response.status_code}": "Malformed request."}
        if response.status_code == 204:
            return {f"Success {response.status_code}": "Record deleted successfully."}
        else:
            return {f"Error {response.status_code}": response.text}

    def _format_entity(self, entity):
        if not entity.endswith('s'):
            entity += 's'
        return entity.lower()

    def search(self, entity, term):
        if not term:
            raise APICallError('Search term must be specified.')
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "params": {"search": term}}
        response = requests.get(f'{self.endpoint}/{entity}?', **request_kwargs)
        response_dict = json.loads(response.text)
        return response_dict

    def query(self, entity, **kwargs):
        if not kwargs:
            raise APICallError('Query terms must be specified.')
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "params": kwargs}
        response = requests.get(f'{self.endpoint}/{entity}?', **request_kwargs)
        response_dict = json.loads(response.text)
        return response_dict

    def add(self, entity, **kwargs):
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "data": json.dumps(kwargs)}
        response = requests.post(f'{self.endpoint}/{entity}/', **request_kwargs)
        response_dict = json.loads(response.text)
        return response_dict

    def add_file(self, entity="files", file=None, **kwargs):
        entity = self._format_entity(entity)
        with open(file, 'rb') as f:
            files = {"file": f}
            headers = {**self.headers}
            headers.pop('Content-Type')
            request_kwargs = {"headers": headers, "files": files, "data": kwargs}
            response = requests.post(f'{self.endpoint}/{entity}/', **request_kwargs)
        response_dict = json.loads(response.text)
        return response_dict

    def delete(self, entity, entity_id, **kwargs):
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "data": json.dumps(kwargs)}
        response = requests.delete(f'{self.endpoint}/{entity}/{entity_id}', **request_kwargs)
        return self._handle_status_code(response)