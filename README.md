# blacksheep_decorators
Example implementation of decorators DI (Dependency injection) in [blacksheep](https://github.com/Neoteroi/BlackSheep) at a non-framework level.

### Install
- clone
- configure venv
- `pip install -r requirements.txt`


### Run tests
- `python main.py`


### Usage
- create your decorator
- without `functools.wraps` (!)
- required to extract `request: Request` and `services: Services`
- calculate your data
- `return await with_deps_injection(...)` with params
- - **original_handler** - original request function
- - **request**
- - **services**
- - **your new classes** with any key
- wrap your handler with your decorator, after decorator @app.router.<method>(...)


### Example
```python
...


class Rights(Enum):
	...


def check_auth(minimal_rights: Optional[Rights] = None):
	def real_decorator(original_function):
		
		async def wrapper(
			request: Request,
			services: Services,
		) -> Response:
			rights, allowed = check_rights_from_headers(  # your logic
				headers=request.headers,
				minimal_rights=minimal_rights,
			)

			if not allowed:
				return failure_response(  # if failure, your logic
					your_rights=rights.value,
					rights_required=minimal_rights,
				)

			return await with_deps_injection( # if ok
				orig_handler=original_function,
				request=request,
				services=services,
				rights=rights
				# your classes, with any key, in example only one class 'Rights' (variable 'rights') with key 'rights'
			)

		return wrapper

	return real_decorator


@app.router.get('/{home_id}/')
@check_auth(Rights.admin)
async def home(
	home_id: int,  # from Route
	rights: Rights,
):
	return success_response(
		rights=rights.value,
		home_id=home_id,
	)


```


### Source
Just for easy paste in your code:


`injections.py`
```python
from blacksheep import Route, Request
from blacksheep.server.normalization import normalize_handler, ensure_response
from rodi import Services, class_name


class TempInject:

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

	def __enter__(self) -> Services:
		return self.services

	def __exit__(self, exc_type, exc_val, exc_tb):
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
	if request.route_values is not None:
		route_like.param_names = list(request.route_values.keys())

	with TempInject(services, *args, **kwargs) as temp_services:
		norm_handler = normalize_handler(
			route=route_like,
			services=temp_services
		)
		response = ensure_response(await norm_handler(request))

	return response

```
