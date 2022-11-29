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
