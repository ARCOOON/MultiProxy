"""
plugin_base
============= 

Defines the abstract base class and types used by the proxy to load and interact with plugins.  Each plugin must implement a `Plugin` class that derives from
`BasePlugin` and provides a unique name.  Plugins can override hooks to
inspect or modify HTTP requests and responses, and may expose CLI
commands to the interactive shell.

The proxy server invokes plugin hooks in the order in which they are
loaded.  If a plugin returns `False` from `handle_request` the
processing chain is terminated and the request is denied.  Return
`True` to allow the next plugin (and eventually the proxy) to handle
the request.

Plugins can expose a dictionary of CLI commands via `get_commands`.  A
command is a callable taking a list of strings (the arguments) and
returning an optional string to be printed to the user.  See
``firewall_shell.py`` for examples.
"""
from __future__ import annotations

import abc
from typing import Any, Callable, Dict, List, Optional


class BasePlugin(abc.ABC):
    """Abstract base class for all proxy plugins.

    To create a new plugin, subclass `BasePlugin` and implement the
    required methods.  All plugins must provide a unique `name`
    property and may implement the `description` and `version`
    attributes for documentation purposes.
    """

    #: Human‑readable name of the plugin.  Must be unique across all
    #: loaded plugins.
    name: str = "Unnamed"

    #: Optional description of the plugin's purpose.
    description: str = ""

    #: Optional version string for the plugin.
    version: str = "0.0.0"

    def __init__(self, manager: "PluginManager") -> None:
        self.manager = manager
        self.initialized = False

    def initialize(self) -> None:
        """Called once after the plugin is constructed but before any
        requests are processed.  Plugins can perform one‑time setup
        here, such as loading configuration or registering resources.
        """
        self.initialized = True

    def finalize(self) -> None:
        """Called when the proxy server is shutting down.  Override to
        release resources or flush state.
        """
        pass

    def handle_request(self, request: "HTTPRequest") -> bool:
        """Inspect or modify an incoming request.

        Parameters
        ----------
        request: HTTPRequest
            Parsed HTTP request object.  See ``server.py`` for the
            structure.

        Returns
        -------
        bool
            Return ``True`` to continue processing the request or
            ``False`` to stop and deny it.  If ``False`` is returned
            the proxy will respond with a 403 Forbidden by default.
        """
        return True

    def handle_response(self, response: bytes, request: "HTTPRequest") -> bytes:
        """Inspect or modify the raw response from the upstream server.

        Parameters
        ----------
        response: bytes
            The raw HTTP response bytes from the upstream server.

        request: HTTPRequest
            The original request that triggered this response.

        Returns
        -------
        bytes
            Plugins may return the original response, a modified one,
            or raise an exception to signal an error.
        """
        return response

    def get_commands(self) -> Dict[str, Callable[[List[str]], Optional[str]]]:
        """Return a mapping of command names to callables for the CLI.

        Each command should accept a list of argument strings and
        return an optional string result.  The plugin manager will
        dispatch CLI commands to the appropriate plugin based on the
        command prefix.  The default implementation returns an empty
        dict, meaning the plugin exposes no CLI commands.
        """
        return {}


# Type alias used in annotations to avoid circular imports.  The
# HTTPRequest type is defined in server.py.
class HTTPRequest:
    pass