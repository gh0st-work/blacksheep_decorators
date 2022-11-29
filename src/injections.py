from blacksheep import Route, Request
from blacksheep.server.normalization import normalize_handler, ensure_response
from rodi import Services, class_name


class TempInjected:

	def __init__(self, services: Services, *args, **kwargs):
		self.services = services

		self.injections = [*args, *kwargs.values()]
		self.injections_types = []
		self.injections_class_names = []
		for injection in self.injections:
			injection_type = injection.__class__
			self.injections_types.append(injection_type)

			raw_injection_class_name = class_name(injection_type)
			self.injections_class_names.append(raw_injection_class_name)

			self.services.set(injection_type, injection)

	def clean(self):
		for injection_class_name in self.injections_class_names:
			del self.services._map[injection_class_name]
		for injection_type in self.injections_types:
			del self.services._map[injection_type]


async def with_deps_injection(
	orig_handler,
	request: Request,
	services: Services,
	*args,
	**kwargs
):
	route_like = Route('', orig_handler)  # For this (normal typing & beauty) are needed extra changes in core
	route_like.param_names = list(request.route_values.keys())

	temp_injection = TempInjected(services, *args, **kwargs)
	services = temp_injection.services
	norm_handler = normalize_handler(
		route=route_like,
		services=services
	)
	response = ensure_response(await norm_handler(request))
	temp_injection.clean()
	services = temp_injection.services
	return response
