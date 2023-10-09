from inspect import signature
from logging import getLogger
from typing import TYPE_CHECKING, Union
from collections.abc import Awaitable
from collections.abc import Callable, Iterable
from uuid import uuid4

from httpx import BaseTransport, Response, Request, HTTPTransport
from pyrate_limiter import (
    AbstractBucket,
    InMemoryBucket,
    Limiter,
    Rate,
    Duration,
    BucketFactory,
    RateItem,
    AbstractClock,
    TimeClock,
)

MIXIN_BASE = BaseTransport if TYPE_CHECKING else object
logger = getLogger(__name__)


class NameBucketFactory(BucketFactory):
    """Bucket factory, that will move items based on their name"""

    DEFAULT_NAME = "httpx_ratelimiter"

    def __init__(  # noqa: PLR0913
        self,
        rates: list[Rate],
        default_name: str,
        clock: type[AbstractClock] = TimeClock,
        bucket_class: type[AbstractBucket] = InMemoryBucket,
        bucket_kwargs: dict | None = None,
        *args,
        **kwargs,
    ):
        self.default_name = default_name
        self.clock = clock()
        self.bucket_class = bucket_class
        self.bucket_kwargs = bucket_kwargs
        if self.bucket_kwargs is None:
            self.bucket_kwargs = {}
        self.rates = rates
        self.buckets = {
            self.default_name: self.create(
                self.clock, self.bucket_class, rates=self.rates, **self.bucket_kwargs
            )
        }
        super().__init__(*args, **kwargs)

    def wrap_item(
        self, name: str, weight: int = 1
    ) -> Union[RateItem, Awaitable[RateItem]]:
        now = self.clock.now()
        return RateItem(name, now, weight)

    def get(self, item: RateItem) -> AbstractBucket:
        name = item.name
        if name not in self.buckets:
            self.buckets[name] = self.create(
                self.clock, self.bucket_class, rates=self.rates, **self.bucket_kwargs
            )
        return self.buckets[name]


class LimiterMixin(MIXIN_BASE):
    """Mixin class that adds rate-limiting behavior to httpx.

    See :py:class:`.LimiterSession` for parameter details.
    """

    def __init__(  # noqa: PLR0913
        self,
        per_second: float = 0,
        per_minute: float = 0,
        per_hour: float = 0,
        per_day: float = 0,
        per_month: float = 0,
        burst: float = 1,
        bucket_class: type[AbstractBucket] = InMemoryBucket,
        bucket_kwargs: dict | None = None,
        bucket_factory: type[BucketFactory] = NameBucketFactory,
        limiter: Limiter | None = None,
        raise_when_fail: bool = True,
        max_delay: Union[int, float, None] = None,
        clock: type[AbstractClock] = TimeClock,
        per_host: bool = True,
        limit_statuses: Iterable[int] = (429,),
        **kwargs,
    ):
        # Translate request rate values into Rate objects
        rates = [
            Rate(limit, interval)
            for interval, limit in [
                (Duration.SECOND * burst, per_second * burst),
                (Duration.MINUTE, per_minute),
                (Duration.HOUR, per_hour),
                (Duration.DAY, per_day),
                (Duration.WEEK * 4, per_month),
            ]
            if limit
        ]
        self.default_name = str(uuid4())
        self.limit_statuses = limit_statuses
        self.max_delay = max_delay
        self.per_host = per_host
        self.bucket_factory = bucket_factory(
            rates, self.default_name, clock, bucket_class, bucket_kwargs
        )
        # create limiter object
        self.limiter = limiter or Limiter(
            self.bucket_factory, raise_when_fail=raise_when_fail, max_delay=max_delay
        )

        # If the superclass is an BaseTransport subclass,
        # pass along any valid keyword arguments
        session_kwargs = get_valid_kwargs(super().__init__, kwargs)
        super().__init__(**session_kwargs)  # type: ignore

    def handle_request(self, request: Request, **kwargs) -> Response:
        """Send a request with rate-limiting.

        Raises:
            :py:exc:`.BucketFullException` if raise_when_fail is ``True`` and this
                request would result in a delay longer than ``max_delay``
        """
        self.limiter.try_acquire(self._name(request))
        response = super().handle_request(request, **kwargs)
        if response.status_code in self.limit_statuses:
            self._fill_bucket(request)
        return response

    def _name(self, request: Request):
        """Get a name for the given request"""
        return request.url.netloc if self.per_host else self.default_name

    def _fill_bucket(self, request: Request):
        """Partially fill the bucket for the given request, requiring an extra delay
        until the next request. This is essentially an attempt to catch up to the actual
        (server-side) limit if we've gotten out of sync.

        If the server tracks multiple limits, there's no way to know which specific
        limit was exceeded, so the smallest rate will be used.

        For example, if the server allows 60 requests per minute, and we've tracked only
        40 requests but received a 429 response, 20 additional "filler" requests will be
        added to the bucket to attempt to catch up to the server-side limit.

        If the server also has an hourly limit, we don't have enough information to know
        if we've exceeded that limit or how long to delay, so we'll keep delaying in
        1-minute intervals.
        """
        logger.info(f"Rate limit exceeded for {request.url}; filling limiter bucket")
        item = self.bucket_factory.wrap_item(self._name(request))
        bucket = self.bucket_factory.get(item)

        # Determine how many filler request we should add to reach a limit
        rate = bucket.rates[0]
        item_count = rate.limit - bucket.count()

        # Add "filler" requests to reach the limit for that interval
        bucket.put(self.bucket_factory.wrap_item(self._name(request), item_count))


class LimiterTransport(LimiterMixin, HTTPTransport):
    """`Transport <https://www.python-httpx.org/advanced/#custom-transports>`_
    that adds rate-limiting behavior to httpx.

    The following parameters also apply to :py:class:`.LimiterMixin`

    .. note::
        The ``per_*`` params are aliases for the most common rate limit
        intervals; for more complex rate limits, you can provide a
        :py:class:`~pyrate_limiter.limiter.Limiter` object instead.

    Args:
        per_second: Max requests per second
        per_minute: Max requests per minute
        per_hour: Max requests per hour
        per_day: Max requests per day
        per_month: Max requests per month
        burst: Max number of consecutive requests allowed before applying per-second
            rate-limiting
        bucket_class: Bucket backend class; may be one of
            :py:class:`~pyrate_limiter.bucket.MemoryQueueBucket` (default),
            :py:class:`~pyrate_limiter.sqlite_bucket.SQLiteBucket`, or
            :py:class:`~pyrate_limiter.bucket.RedisBucket`
        bucket_kwargs: Bucket backend keyword arguments
        bucket_factory: Bucket Factory class
        raise_when_fail: Raise an exception. Read max_delay documentation for more
            information
        limiter: An existing Limiter object to use instead of the above params
        max_delay: The maximum allowed delay time (in seconds); anything over this will
            abort the request and raise a :py:exc:`.BucketFullException` if
            raise_when_fail is `True`
        per_host: Track request rate limits separately for each host
        limit_statuses: Alternative HTTP status codes that indicate a rate limit was
            exceeded
    """


def get_valid_kwargs(func: Callable, kwargs: dict) -> dict:
    """Get the subset of non-None ``kwargs`` that are valid params for ``func``"""
    sig_params = list(signature(func).parameters)
    return {k: v for k, v in kwargs.items() if k in sig_params and v is not None}
