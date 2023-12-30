
import re

PARAMETER_ROUTE_MODE: str = "__parameter"

# A route is formatted with {parameters}, its linked value will be the "mode" parameter.
# If value is PARAMETER_ROUTE_MODE, the "mode" parameter will be taken from the url.
routes: dict = {
    "/menu/{mode}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/offset/{offset}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/{genre}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/{genre}/offset/{offset}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/{genre}/category/{category_filter}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/{genre}/category/{category_filter}/offset/{offset}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/{genre}/season/{season_filter}": PARAMETER_ROUTE_MODE,
    "/menu/{mode}/{genre}/season/{season_filter}/offset/{offset}": PARAMETER_ROUTE_MODE,
    "/series/{series_id}": "series",
    "/series/{series_id}/{collection_id}": "episodes",
    "/series/{series_id}/{collection_id}/offset/{offset}": "episodes",
    "/video/{series_id}/{episode_id}/{stream_id}": "videoplay"
}

def extract_url_params(url: str) -> dict:
    for pattern, mode in routes.items():
        if pattern[0] == "/":
            pattern = pattern[1:]
        regexp = "^/?" + pattern.replace("{", "(?P<").replace("}", ">[^/]+)") + "$"
        result = re.match(regexp, url)
        if result is not None:
            resp = result.groupdict()
            if mode == PARAMETER_ROUTE_MODE:
                mode = result.group("mode")
            resp["mode"] = mode
            return resp
    
    return None

def build_path(args: dict) -> str:
    # Find routes matching mode
    routes_for_mode = get_matching_routes_with_params_from_mode(args.get("mode"))
    # Filter routes by existing args
    routes_for_params = {route: params for route, params in routes_for_mode.items() if check_args_contains_params(args, params)}
    # Choose the best one
    param_number: int = 0
    selected_route: str = None
    selected_params: list = None
    for route, params in routes_for_params.items():
        if len(params) > param_number:
            param_number = len(params)
            selected_route = route
            selected_params = params
    if not selected_route:
        return None
    # Build URL from selected route
    result = selected_route
    for param in selected_params:
        result = result.replace("{%s}" % param, str(args.get(param)))
    return result

def get_matching_routes_with_params_from_mode(searching_mode: str) -> list:
    routes = get_matching_routes_from_mode(searching_mode)
    return {route: get_params_from_route(route) for route in routes}

def get_matching_routes_from_mode(searching_mode: str) -> list:
    # TODO: Cache it
    routes_by_mode = {}
    for pattern, mode in routes.items():
        if not routes_by_mode.get(mode):
            routes_by_mode[mode] = []
        routes_by_mode.get(mode).append(pattern)

    if not routes_by_mode.get(searching_mode):
        return routes_by_mode.get(PARAMETER_ROUTE_MODE)

    return routes_by_mode.get(searching_mode)

def get_params_from_route(route: str) -> list:
    # TODO: Cache it
    params_by_route = {}
    for pattern, mode in routes.items():
        params_by_route[pattern] = get_params_from_pattern(pattern)

    if not params_by_route.get(route):
        return params_by_route.get(PARAMETER_ROUTE_MODE)

    return params_by_route.get(route)

def get_params_from_pattern(pattern: str) -> list:
    return re.findall(r"\{([^}]+)\}", pattern)

def check_args_contains_params(args: dict, params: list) -> bool:
    for param in params:
        if not args.get(param):
            return False
    return True
