import inspect
from types import ClassType

from wrapt import decorator


class argtypes(object):
    _converters = {
        int: int, long: long, float: float, str: str, unicode: unicode,
        bool: lambda arg: bool(arg.upper() not in ('FALSE', '')
                               if isinstance(arg, (str, unicode)) else arg)
    }

    def __init__(self, *arg_types, **kwarg_types):
        TypeValidator().validate(*arg_types, **kwarg_types)
        self._arg_handler = ArgumentHandler(arg_types, kwarg_types,
                                            self._converters)

    @classmethod
    def register_converter(cls, arg_type, converter=None):
        TypeValidator(allow_none=False).validate(arg_type)
        old = cls._converters.get(arg_type)
        cls._converters[arg_type] = converter or arg_type
        return old

    @classmethod
    def unregister_converter(cls, arg_type):
        if arg_type in cls._converters:
            return cls._converters.pop(arg_type)

    @decorator
    def __call__(self, wrapped, instance, args, kwargs):
        argspec = inspect.getargspec(wrapped).args
        if instance:
            argspec.pop(0)    # drop self
        args, kwargs = self._arg_handler.handle(args, kwargs, argspec)
        return wrapped(*args, **kwargs)


class TypeValidator(object):

    def __init__(self, allow_none=True):
        self._allow_none = allow_none

    def validate(self, *args, **kwargs):
        for arg in args + tuple(kwargs.values()):
            if not self._is_valid_type(arg, self._allow_none):
                self._raise_invalid(arg)

    def _is_valid_type(self, arg_type, allow_none=True, allow_tuple=True):
        if isinstance(arg_type, tuple) and allow_tuple:
            return all(self._is_valid_type(at, False, False) for at in arg_type)
        return (isinstance(arg_type, (type, ClassType)) or
                arg_type is None and allow_none)

    def _raise_invalid(self, arg):
        allowed = 'class, tuple of classes or None' \
            if self._allow_none else 'class or tuple of classes'
        raise TypeError('Argument type must be %s, got <%s> instance instead.'
                        % (allowed, type(arg).__name__))


class ArgumentHandler(object):

    def __init__(self, arg_types, kwarg_types, converters):
        self._arg_types = arg_types
        self._kwarg_types = kwarg_types
        self._converters = converters

    def handle(self, args, kwargs, argspec):
        args = tuple(self._handle_args(args, argspec))
        kwargs = dict(self._handle_kwargs(kwargs, argspec))
        return args, kwargs

    def _handle_args(self, args, argspec):
        type_count = len(self._arg_types)
        for index, arg in enumerate(args):
            name = argspec[index]
            if name in self._kwarg_types:
                arg = self._handle_arg(arg, self._kwarg_types[name], name)
            elif index < type_count:
                arg = self._handle_arg(arg, self._arg_types[index], name)
            yield arg

    def _handle_kwargs(self, kwargs, argspec):
        type_count = len(self._arg_types)
        for name, arg in kwargs.iteritems():
            if name in self._kwarg_types:
                arg = self._handle_arg(arg, self._kwarg_types[name], name)
            elif name in argspec:
                index = argspec.index(name)
                if index < type_count:
                    arg = self._handle_arg(arg, self._arg_types[index], name)
            yield name, arg

    def _handle_arg(self, argument, expected_type, label):
        if expected_type is None or isinstance(argument, expected_type):
            return argument
        if expected_type in self._converters:
            converter = self._converters[expected_type]
            try:
                return converter(argument)
            except TypeError:
                pass
        raise RuntimeError('Argument %s should have been %s but was <%s>.'
                           % (label, self._format_expected(expected_type),
                              type(argument).__name__))

    def _format_expected(self, expected):
        if not isinstance(expected, tuple):
            expected = (expected,)
        expected = ['<%s>' % exp.__name__ for exp in expected]
        if len(expected) == 1:
            return expected[0]
        return '%s or %s' % (', '.join(expected[:-1]), expected[-1])
