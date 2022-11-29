from typing import Dict, Any, Optional, List

from blacksheep import Request, Headers, pretty_json, Response
from schema import Schema
from addict import Dict as Addict

RawData = Dict[str, Any]


async def extract_raw_data(request: Request) -> RawData:
	def get_ip(data: RawData) -> Optional[str]:
		ip = None
		headers: Headers = data['headers']
		x_forwarded_for = (
			None
			if not headers.contains(b'HTTP_X_FORWARDED_FOR')
			else headers.get_single(b'HTTP_X_FORWARDED_FOR').decode()
		)
		remote_addr = (
			None
			if not headers.contains(b'REMOTE_ADDR')
			else headers.get_single(b'REMOTE_ADDR').decode()
		)
		if x_forwarded_for:
			ip = x_forwarded_for.split(',')[-1].strip()
		elif remote_addr:
			ip = remote_addr
		return ip

	data: RawData = {}
	try:
		json_data = await request.json()
	except BaseException as ex:
		json_data = None
	try:
		form_data = await request.form()
	except BaseException as ex:
		form_data = None
	query_data = {k: v for k, v in request.query.items()}
	if json_data:
		data = json_data
	elif form_data:
		data = form_data
	elif query_data:
		data = query_data

	data['headers']: Dict[str, List[str]] = request.headers
	data['ip']: Optional[str] = get_ip(data)
	data['route_values']: Optional[Dict[str, str]] = request.route_values
	return data


class SchemaDict:

	def __init__(self, data: Any = None, schema: Optional[Schema] = None, **kwargs):
		real_schema = schema
		if not schema and len(kwargs.keys()):
			real_schema = kwargs
		valid_data: Dict[str, Any] = Schema(
			schema=real_schema,
			error=None,
			ignore_extra_keys=True,
			name=None,
			description=None,
			as_reference=False
		).validate(data)
		self._dict: Dict[str, Any] = valid_data
		self._addict: Addict = Addict(valid_data)

	def __getattr__(self, key: str):
		return self._addict[key]


def failure_response(status: int = 400, **kwargs) -> Response:
	return pretty_json(
		{
			**kwargs,
			'success': False,
		}, status
	)


def success_response(status: int = 200, **kwargs) -> Response:
	return pretty_json(
		{
			**kwargs,
			'success': True,
		}, status
	)
