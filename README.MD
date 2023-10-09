# httpx-ratelimit

Simple wrapper around
[PyrateLimiter](https://pyratelimiter.readthedocs.io/en/latest/)
that adds integration with
[httpx](https://www.python-httpx.org/) library

### Usage

#### Using transport

Example:

```py
from time import time

from httpx import Client

from httpx_ratelimiter import LimiterTransport

# Apply a rate limit of 2 requests per second to all requests
with Client(transport=LimiterTransport(per_second=5, max_delay=600)) as c:
    start = time()
    for _i in range(100):
        print(
            f'[t + {time() - start: .2f}] got response: {c.get("https://httpbin.org/status/200,429")}'
        )
```


### Thanks
Thank to original [Requests-ratelimiter](https://github.com/JWCook/requests-ratelimiter/tree/main) author for idea and backbone of a project.
