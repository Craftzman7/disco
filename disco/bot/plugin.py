import inspect
import functools

from disco.util.logging import LoggingClass
from disco.bot.command import Command, CommandError


class PluginDeco(object):
    """
    A utility mixin which provides various function decorators that a plugin
    author can use to create bound event/command handlers.
    """
    @staticmethod
    def add_meta_deco(meta):
        def deco(f):
            if not hasattr(f, 'meta'):
                f.meta = []

            f.meta.append(meta)

            return f
        return deco

    @classmethod
    def listen(cls, event_name):
        """
        Binds the function to listen for a given event name
        """
        return cls.add_meta_deco({
            'type': 'listener',
            'event_name': event_name,
        })

    @classmethod
    def command(cls, *args, **kwargs):
        """
        Creates a new command attached to the function
        """
        return cls.add_meta_deco({
            'type': 'command',
            'args': args,
            'kwargs': kwargs,
        })

    @classmethod
    def pre_command(cls):
        """
        Runs a function before a command is triggered
        """
        return cls.add_meta_deco({
            'type': 'pre_command',
        })

    @classmethod
    def post_command(cls):
        """
        Runs a function after a command is triggered
        """
        return cls.add_meta_deco({
            'type': 'post_command',
        })

    @classmethod
    def pre_listener(cls):
        """
        Runs a function before a listener is triggered
        """
        return cls.add_meta_deco({
            'type': 'pre_listener',
        })

    @classmethod
    def post_listener(cls):
        """
        Runs a function after a listener is triggered
        """
        return cls.add_meta_deco({
            'type': 'post_listener',
        })


class Plugin(LoggingClass, PluginDeco):
    """
    A plugin is a set of listeners/commands which can be loaded/unloaded by a bot.

    :param disco.bot.Bot bot: the bot this plugin is loaded under
    :param config: a untyped object containing configuration for this plugin

    :ivar disco.client.DiscoClient client: an alias to the client
    :ivar disco.state.State state: an alias to the client state
    :ivar list listeners: all bound listeners for this plugin
    :ivar dict commands: all bound commands for this plugin
    """
    def __init__(self, bot, config):
        super(Plugin, self).__init__()
        self.bot = bot
        self.client = bot.client
        self.state = bot.client.state
        self.config = config

        self.listeners = []
        self.commands = {}

        self._pre = {'command': [], 'listener': []}
        self._post = {'command': [], 'listener': []}

        for name, member in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(member, 'meta'):
                for meta in member.meta:
                    if meta['type'] == 'listener':
                        self.register_listener(member, meta['event_name'])
                    elif meta['type'] == 'command':
                        self.register_command(member, *meta['args'], **meta['kwargs'])
                    elif meta['type'].startswith('pre_') or meta['type'].startswith('post_'):
                        when, typ = meta['type'].split('_', 1)
                        self.register_trigger(typ, when, member)

    def execute(self, event):
        """
        Executes a CommandEvent this plugin owns
        """
        try:
            return event.command.execute(event)
        except CommandError as e:
            event.msg.reply(e.message)
            return False

    def register_trigger(self, typ, when, func):
        """
        Registers a trigger
        """
        getattr(self, '_' + when)[typ].append(func)

    def _dispatch(self, typ, func, event, *args, **kwargs):
        for pre in self._pre[typ]:
            event = pre(event, args, kwargs)

        if event is None:
            return False

        result = func(event, *args, **kwargs)

        for post in self._post[typ]:
            post(event, args, kwargs, result)

        return True

    def register_listener(self, func, name):
        """
        Registers a listener

        :param func: function to be called
        :param name: name of event to listen for
        """
        func = functools.partial(self._dispatch, 'listener', func)
        self.listeners.append(self.bot.client.events.on(name, func))

    def register_command(self, func, *args, **kwargs):
        """
        Registers a command

        :param func: function to be called
        :param args: args to be passed to the :class:`Command` object
        :param kwargs: kwargs to be passed to the :class:`Command` object
        """
        wrapped = functools.partial(self._dispatch, 'command', func)
        self.commands[func.__name__] = Command(self, wrapped, *args, **kwargs)

    def destroy(self):
        """
        Destroys the plugin (removing all listeners)
        """
        map(lambda k: k.remove(), self._events)

    def load(self):
        """
        Called when the plugin is loaded
        """
        pass

    def unload(self):
        """
        Called when the plugin is unloaded
        """
        pass
