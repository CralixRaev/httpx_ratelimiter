# httpx-ratelimit
[![PyPI version](https://badge.fury.io/py/httpx_ratelimiter.svg)](https://badge.fury.io/py/httpx_ratelimiter)


Simple wrapper around
[PyrateLimiter](https://pyratelimiter.readthedocs.io/en/latest/)
that adds integration with
[httpx](https://www.python-httpx.org/) library

### Usage
##### Using per_* kwargs:
```py
from time import time

from httpx import Client

from httpx_ratelimiter import LimiterTransport

# Apply a rate limit of 5 requests per second to all requests
# if wait time between request will be more than 600ms, raise an BucketFullException
with Client(transport=LimiterTransport(per_second=5, max_delay=600)) as c:
    start = time()
    for _i in range(100):
        print(
            f'[t + {time() - start: .2f}] got response: {c.get("https://httpbin.org/status/200,429")}'
        )
```
##### Using custom list of rates
```py
from time import time

from httpx import Client

from httpx_ratelimiter import LimiterTransport
from pyrate_limiter import Limiter, Rate, Duration

# limit 5 requests over 2 seconds and 10 requests over 1 minute
rates = [Rate(5, Duration.SECOND * 2), Rate(10, Duration.MINUTE)]
# if wait time between request will be more than 600ms, silently fail
with Client(transport=LimiterTransport(rates=rates, max_delay=600, raise_when_fail=False)) as c:
    start = time()
    for _i in range(100):
        print(
            f'[t + {time() - start: .2f}] got response: {c.get("https://httpbin.org/status/200,429")}'
        )
```


### Thanks
Thank to original [Requests-ratelimiter](https://github.com/JWCook/requests-ratelimiter/tree/main) author for idea and backbone of a project.
