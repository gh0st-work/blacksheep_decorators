from enum import Enum
from typing import Optional, Dict, Any, Tuple

from blacksheep import Headers
from blacksheep.messages import Request, Response
from blacksheep.server import Application
from blacksheep.testing import MockReceive, MockSend
from blacksheep.testing.helpers import get_example_scope
from rodi import Services
from schema import SchemaError, Schema

from src.injections import with_deps_injection
from src.helpers import extract_raw_data, RawData, SchemaDict, failure_response, success_response
import json


class FakeApplication(Application):
	def __init__(self, *args, **kwargs):
		super().__init__(show_error_details=True, *args, **kwargs)
		self.request: Optional[Request] = None
		self.response: Optional[Response] = None

	def normalize_handlers(self):
		if self._service_provider is None:
			self.build_services()
		super().normalize_handlers()

	def setup_controllers(self):
		self.use_controllers()
		self.build_services()
		self.normalize_handlers()

	async def handle(self, request):
		response = await super().handle(request)
		self.request = request
		self.response = response
		return response

	def prepare(self):
		self.normalize_handlers()
		self.configure_middlewares()


async def test_decorators(app):
	class Rights(Enum):
		default = 'default'
		admin = 'admin'

	def check_auth(minimal_rights: Optional[Rights] = None):
		def real_decorator(original_function):
			# NO @functools.wraps, need core changes
			async def wrapper(
				request: Request,
				services: Services,
			) -> Response:
				headers: Headers = request.headers
				rights = Rights.default
				rights_raw = headers.get_single(b'Rights').decode()
				if rights_raw == Rights.admin.value:
					rights = Rights.admin

				allowed = False
				rights_ordered = [r for r in Rights]
				for i, right_in_order in enumerate(rights_ordered):
					if minimal_rights == right_in_order:
						if rights in rights_ordered[i:]:
							allowed = True
							break

				if not allowed:
					return failure_response(
						your_rights=rights.value,
						rights_required=minimal_rights,
					)

				return await with_deps_injection(
					orig_handler=original_function,
					request=request,
					services=services,
					rights=rights
				)

			return wrapper

		return real_decorator

	def check_schema(schema: Optional[Schema] = None, **kwargs):
		def real_decorator(original_function):
			# NO @functools.wraps, need core changes
			async def wrapper(
				request: Request,
				services: Services,
			) -> Response:
				raw_data: RawData = await extract_raw_data(request)
				try:
					data: SchemaDict = SchemaDict(
						data=raw_data,
						schema=schema,
						**kwargs
					)
				except SchemaError as ex:
					return failure_response()

				return await with_deps_injection(
					orig_handler=original_function,
					request=request,
					services=services,
					data=data
				)

			return wrapper

		return real_decorator

	@app.router.get('/{home_id}/')
	@check_auth(Rights.admin)
	@check_schema(
		some_checkbox_info=bool
	)
	async def home(
		home_id: int,  # from Route
		rights: Rights,
		data: SchemaDict,
	):
		return success_response(
			rights=rights.value,
			some_checkbox_info=data.some_checkbox_info,
			home_id=home_id,
		)

	await app.start()

	async def send(
		client_rights: Rights,
		data: Dict[str, Any],
		path_id: int,
	) -> Tuple[int, Dict[str, Any]]:
		await app(
			get_example_scope(
				method='GET',
				path=f'/{path_id}/',
				extra_headers=[
					(b'Rights', client_rights.value.encode()),
					(b"content-type", b"application/json"),
				],
			),
			MockReceive([json.dumps(data).encode()]),
			MockSend()
		)
		response = app.response
		response_data = await response.json()
		return response.status, response_data

	async def test_ok():
		client_rights = Rights.admin
		data = {'some_checkbox_info': True}
		path_id = 10
		response_status, response_data = await send(
			client_rights=client_rights,
			data=data,
			path_id=path_id,
		)
		assert response_status == 200
		assert response_data['success'] is True
		assert response_data['rights'] == client_rights.value
		assert response_data['some_checkbox_info'] == data['some_checkbox_info']
		assert response_data['home_id'] == 10

	async def test_no_rights():
		client_rights = Rights.default
		data = {'some_checkbox_info': True}
		path_id = 10
		response_status, response_data = await send(
			client_rights=client_rights,
			data=data,
			path_id=path_id,
		)
		assert response_status == 400
		assert response_data['success'] is False
		assert response_data['your_rights'] == client_rights.value
		assert response_data['rights_required'] == Rights.admin.value

	async def test_schema():
		client_rights = Rights.admin
		data = {'some_checkbox_info': False}
		path_id = 10
		response_status, response_data = await send(
			client_rights=client_rights,
			data=data,
			path_id=path_id,
		)
		assert response_status == 200
		assert response_data['success'] is True
		assert response_data['rights'] == client_rights.value
		assert response_data['some_checkbox_info'] is data['some_checkbox_info']
		assert response_data['home_id'] == 10

	await test_ok()
	await test_no_rights()
	await test_schema()
