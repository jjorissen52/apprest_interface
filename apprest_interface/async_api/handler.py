import os, configparser, requests, json, http, ast, subprocess


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
        if response.status_code == 200:
            return json.loads(response.text)
        elif response.status_code == 201:
            return json.loads(response.text)
        elif response.status_code == 204:
            return {f"Success {response.status_code}": "Record deleted successfully."}
        elif str(response.status_code).startswith('2'):
            return {f"Success {response.status_code}": http.client.resonses[response.status_code]}
        elif str(response.status_code).startswith('3'):
            return {f"Redirection {response.status_code}": http.client.resonses[response.status_code]}
        elif response.status_code == 403:
            return {f"Error {response.status_code}": "Malformed request."}
        elif response.status_code == 404:
            return {f"Error {response.status_code}": "Record did not exist or non-existent endpoint."}
        elif response.status_code == 500:
            return {f"Error {response.status_code}": "Unspecified Error"}
        else:
            return {f"Error {response.status_code}": response.text}

    def _format_entity(self, entity):
        if entity is not None and not entity.endswith('s'):
            entity += 's'
        if issubclass(entity.__class__, str):
            entity = entity.lower()
        return entity

    def all(self, entities):
        all_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'all.py')
        call_string = f"python {all_file} {' '.join(entities)}"
        proc = subprocess.Popen(call_string, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        response = ast.literal_eval(proc.communicate()[0].decode('utf-8'))
        for i, item in enumerate(response):
            response[i] = ast.literal_eval(item)
        return response

    def search(self, entity, term):
        if not term:
            raise APICallError('Search term must be specified.')
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "params": {"search": term}}
        response = requests.get(f'{self.endpoint}/{entity}?', **request_kwargs)
        # response_dict = json.loads(response.text)
        response = self._handle_status_code(response)
        return response

    def query(self, entity, **kwargs):
        if not kwargs:
            raise APICallError('Query terms must be specified.')
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "params": kwargs}
        response = requests.get(f'{self.endpoint}/{entity}?', **request_kwargs)
        response = self._handle_status_code(response)
        return response

    def add(self, entity, data):
        add_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'add.py')
        entity = self._format_entity(entity)
        request_kwargs_list = [json.dumps({'headers': self.headers, 'data': json.dumps(datum)}) for datum in data]
        # print(request_kwargs_list)
        call_string = f"python {add_file} {entity} -k '{','.join(request_kwargs_list)}'"
        if len(call_string) > 32767:
            raise APICallError('Could not pass so many characters. Please break into smaller requests. '
                               f'{len(call_string)/32767} times the character limit')
        proc = subprocess.Popen(call_string, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        responses = ast.literal_eval(proc.communicate()[0].decode('utf-8'))
        for i, response in enumerate(responses):
            responses[i] = json.loads(response)
        return responses

    def get_or_error(self, entity, **kwargs):
        response = self.query(entity, **kwargs)
        if len(response) != 1:
            query_summary = '\n'.join([f'"{key}": "{value}"' for key, value in kwargs.items()])
            query_summary = f'({entity}={{{query_summary}}})'
            raise APICallError(f'{len(response)} records match {query_summary}. Exactly 1 required for get request.')
        return response[0]

    def get_or_create(self, entity, **kwargs):
        response = self.query(entity, **kwargs)
        if len(response) > 1:
            raise APICallError(f'{len(response)} records match the provided query. Exactly 1 required for get request.')
        elif len(response) == 0:
            response, created = self.add('doctor', **kwargs), True
        else:
            response, created = response[0], False

        return response, created

    def add_file(self, entity="files", file=None, **kwargs):
        entity = self._format_entity(entity)
        with open(file, 'rb') as f:
            files = {"file": f}
            headers = {**self.headers}
            headers.pop('Content-Type')
            request_kwargs = {"headers": headers, "files": files, "data": kwargs}
            response = requests.post(f'{self.endpoint}/{entity}/', **request_kwargs)
        response = self._handle_status_code(response)
        return response

    def edit(self, entity, entity_id, **kwargs):
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "data": json.dumps(kwargs)}
        response = requests.put(f'{self.endpoint}/{entity}/{entity_id}/', **request_kwargs)
        return self._handle_status_code(response)

    def delete(self, entity, entity_id, **kwargs):
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers, "data": json.dumps(kwargs)}
        response = requests.delete(f'{self.endpoint}/{entity}/{entity_id}', **request_kwargs)
        return self._handle_status_code(response)

    def entity_info(self, entity=None, **kwargs):
        entity = self._format_entity(entity)
        request_kwargs = {"headers": self.headers,}
        uri = f'{self.endpoint}/model_info/{entity}/' if entity else f'{self.endpoint}/model_info/'
        response = requests.get(uri, **request_kwargs)
        return self._handle_status_code(response)