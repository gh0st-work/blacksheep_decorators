from enum import Enum
from typing import Dict, Any, Optional, List, Tuple

from blacksheep import Request, Headers, pretty_json, Response
from blacksheep.client import ClientSession
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


def headers_from_dict(headers_dict: Dict[str, str]) -> List[Tuple[bytes, bytes]]:
	return [
		(k.encode(), v.encode())
		for k, v in headers_dict.items()
	]


class LocationInfo:

	def __init__(self, dict_data: Dict[str, Any]):
		self.dict_data = dict_data
		self.addict = Addict(**dict_data)
		self.ip: str = self.addict.ip
		self.network: Optional[str] = self.addict.ip
		self.version: str = self.addict.version
		self.city: str = self.addict.city
		self.region: str = self.addict.region
		self.region_code: str = self.addict.region_code
		self.country: str = self.addict.country
		self.country_name: str = self.addict.country_name
		self.country_code: str = self.addict.country_code
		self.country_code_iso3: str = self.addict.country_code_iso3
		self.country_capital: str = self.addict.country_capital
		self.country_tld: str = self.addict.country_tld
		self.continent_code: str = self.addict.continent_code
		self.in_eu: bool = self.addict.in_eu
		self.postal: str = self.addict.postal
		self.latitude: float = self.addict.latitude
		self.longitude: float = self.addict.longitude
		self.timezone: str = self.addict.timezone
		self.utc_offset: str = self.addict.utc_offset
		self.country_calling_code: str = self.addict.country_calling_code
		self.currency: str = self.addict.currency
		self.currency_name: str = self.addict.currency_name
		self.languages: str = self.addict.languages
		self.country_area: float = self.addict.country_area
		self.country_population: int = self.addict.country_population
		self.asn: str = self.addict.asn
		self.org: str = self.addict.org
		self.hostname: Optional[str] = self.addict.hostname

	@classmethod
	async def from_ip(cls, ip: str):
		async with ClientSession() as client:
			response = await client.get(
				url=f'https://ipapi.co/{ip}/json/',
				headers=headers_from_dict(
					{
						'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, '
						              'like Gecko) Chrome/106.0.0.0 YaBrowser/22.11.0.2500 Yowser/2.5 '
						              'Safari/537.36 '
					}
				)
			)
			data = await response.json()
			return cls(dict_data=data)


class Rights(Enum):
	default = 'default'
	admin = 'admin'


def check_rights_from_headers(
	headers: Headers,
	minimal_rights: Optional[Rights] = None,
) -> Tuple[Rights, bool]:
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

	return rights, allowed


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
