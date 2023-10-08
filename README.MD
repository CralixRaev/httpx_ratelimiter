# httpx-ratelimit

Simple wrapper around
[PyrateLimiter](https://pyratelimiter.readthedocs.io/en/latest/)
based on
[Requests-ratelimiter](https://github.com/JWCook/requests-ratelimiter/tree/main)
that adds integration with
[httpx](https://www.python-httpx.org/) library

Read more full documentation at [Requests-ratelimiter](https://github.com/JWCook/requests-ratelimiter/tree/main)
documentation

### Usage

#### Using transport

Example:

```pycon
from time import time

from httpx import Client

from httpx_ratelimiter import LimiterTransport

# Apply a rate limit of 2 requests per second to all requests
with Client(transport=LimiterTransport(per_second=2)) as c:
    start = time()
    for i in range(7):
        print(f'[t + {time() - start: .2f}] got response: {c.get("https://cataas.com/c")}')
```

### Disclaimer

I just took code from [Requests-ratelimiter](https://github.com/JWCook/requests-ratelimiter/tree/main) and changed it in
order to be compatible with httpx. I didn't really did much, all credits to original author.
