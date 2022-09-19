import calendar
import locale
from datetime import datetime
from itertools import chain

locale.setlocale(locale.LC_TIME, 'C')

_MONTH_NAMES = {name: i for i, name in chain(
    enumerate(calendar.day_abbr), enumerate(calendar.day_name)) if name}

_DAY_NAMES = {name: i + 1 for i, name in chain(
    enumerate(calendar.month_abbr), enumerate(calendar.month_name)) if name}

_DAY_NAMES['0'] = 7


class CronItem:
    @classmethod
    def Second(cls, e):
        return cls(e, 0, 59)

    @classmethod
    def Minute(cls, e):
        return cls(e, 0, 59)

    @classmethod
    def Hour(cls, e):
        return cls(e, 0, 23)

    @classmethod
    def Day(cls, e):
        return cls(e, 1, 31)

    @classmethod
    def Month(cls, e):
        return cls(e, 1, 12, _MONTH_NAMES)

    @classmethod
    def DayOfWeek(cls, e):
        return cls(e, 0, 7, _DAY_NAMES)

    ''' Representation of a cron expression element '''
    __slots__ = ('interval', 'any', 'min_value', 'max_value', 'range_from', 'range_to', 'aliases')

    def __init__(self, item_expr, min_value, max_value, aliases={}):
        # Match /x (every x unit within the range)
        self.interval = 1

        # Min and max value allowed. For example hour can only have 0-23
        self.min_value = min_value
        self.max_value = max_value

        # Match range expression. For example, 0-23
        self.range_from = self.min_value
        self.range_to = self.max_value

        # Mapping of string (lower case) to a number
        self.aliases = {name.lower(): number
                        for name, number in aliases.items()}

        self.__parse(item_expr)

    def match(self, now: int):
        '''Test if a certain number matches the cron expression

        A number matches the cron expression if:
          * The number falls within the range
          * The number matches interval.
        '''
        return (self.range_from <= now <= self.range_to
                and (now - self.range_from) % self.interval == 0)

    def __parse(self, expr):
        '''Parse cron expression and assign correct values.'''

        if '/' in expr:
            expr, interval = expr.split('/', 1)

            # Interval should not be non-digits
            if not interval.isdigit():
                raise ValueError('Invalid interval: %s in expression %s' % (interval, expr))

            interval = int(interval)

            # Interval should not be less than 1
            if interval <= 1:
                raise ValueError('Invalid interval: %s in expression %s' % (interval, expr))

            self.interval = interval

        if expr == '*':
            range_from, range_to = None, None
        elif '-' in expr:
            range_from, range_to = expr.split('-', 1)
        else:
            range_from, range_to = expr, expr

        # Check for empty string, if omitted then assume the min/max value
        if range_from:
            self.range_from = self.__check_valid(range_from)
        if range_to:
            self.range_to = self.__check_valid(range_to)

        if self.range_from > self.range_to:
            raise ValueError("Invalid range value: %d-%d in expression %s" % (
                self.range_from, self.range_to, expr))

    def __check_valid(self, value: str):
        '''Convert string value to integer and check for validity.

        For the value to be valid, it must be either a integer or
        can be converted to integer from the aliases map. The integer
        value also need to be within max_value and min_value.
        '''
        value = value.lower()

        # Convert to integer
        if value in self.aliases:
            value = self.aliases[value]
        elif value.isdigit():
            value = int(value)
        else:
            raise ValueError("Invalid integer: %s" % value)

        # Check range
        if value < self.min_value or (self.max_value is not None and value > self.max_value):
            raise ValueError("Value not allowed: %d (in: %d - %d)" % (value, self.min_value, self.max_value))

        return value

    def __str__(self):
        '''Normalize the cron expression.'''
        pattern = []
        if self.range_from == self.min_value and self.range_to == self.max_value:
            pattern = '*'
        elif self.range_from == self.range_to:
            pattern = '%d' % self.range_from
        else:
            pattern = '%d-%d' % (self.range_from, self.range_to)

        if self.interval != 1:
            return pattern + '/' + self.interval

        return pattern


class CronExpression:
    ''' Representation of a cron expression '''
    __slots__ = ('minute', 'hour', 'day', 'month', 'day_of_week')

    def __init__(self, expr):
        minute, hour, day, month, day_of_week = expr.split()[:5]

        # minute hour day month day-of-week
        self.minute = [CronItem.Minute(x) for x in minute.split(',')]
        self.hour = [CronItem.Hour(x) for x in hour.split(',')]
        self.day = [CronItem.Day(x) for x in day.split(',')]
        self.month = [CronItem.Month(x) for x in month.split(',')]
        self.day_of_week = [CronItem.DayOfWeek(x) for x in day_of_week.split(',')]

    def is_now(self, dt=None):
        ''' Check if the cron expression matches current time '''
        if dt is None:
            dt = datetime.now()

        day_of_week = (dt.weekday() + 1) % 7

        return all((
            any(x.match(dt.minute) for x in self.minute),
            any(x.match(dt.hour) for x in self.hour),
            any(x.match(dt.day) for x in self.day),
            any(x.match(dt.month) for x in self.month),
            any(x.match(day_of_week) for x in self.day_of_week),
        ))

    def __str__(self):
        return ' '.join(
            ','.join(str(x) for x in cron_item)
            for cron_item in (self.minute, self.hour, self.day, self.month, self.day_of_week)
        )
