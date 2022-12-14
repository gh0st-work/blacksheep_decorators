import json
from typing import Optional, Dict, Any, Tuple

from blacksheep.messages import Request, Response
from blacksheep.server import Application
from blacksheep.testing import MockReceive, MockSend
from blacksheep.testing.helpers import get_example_scope
from rodi import Services
from schema import SchemaError, Schema

from src.helpers import extract_raw_data, RawData, SchemaDict, failure_response, success_response, LocationInfo, headers_from_dict, check_rights_from_headers, Rights
from src.injections import with_deps_injection


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

	def add_location_info():
		def real_decorator(original_function):
			# NO @functools.wraps, need core changes
			async def wrapper(
				request: Request,
				services: Services,
			) -> Response:
				# ip = request.client_ip  # localhost limit
				ip = '178.62.144.174'
				loc_info: LocationInfo = await LocationInfo.from_ip(ip)

				return await with_deps_injection(
					orig_handler=original_function,
					request=request,
					services=services,
					loc_info=loc_info,
				)

			return wrapper

		return real_decorator

	def check_auth(minimal_rights: Optional[Rights] = None):
		def real_decorator(original_function):
			# NO @functools.wraps, need core changes
			async def wrapper(
				request: Request,
				services: Services,
			) -> Response:

				rights, allowed = check_rights_from_headers(
					headers=request.headers,
					minimal_rights=minimal_rights,
				)

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
	@add_location_info()
	async def home(
		home_id: int,  # from Route
		rights: Rights,
		data: SchemaDict,
		loc_info: LocationInfo,
	):
		return success_response(
			rights=rights.value,
			some_checkbox_info=data.some_checkbox_info,
			home_id=home_id,
			city=loc_info.city,
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
				extra_headers=headers_from_dict(
					{
						'Rights': client_rights.value,
						'content-type': 'application/json'
					}
				),
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
		assert response_data['home_id'] == path_id
		assert response_data['city'] == 'Amsterdam'

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
		assert response_data['home_id'] == path_id
		assert response_data['city'] == 'Amsterdam'

	await test_ok()
	await test_no_rights()
	await test_schema()
