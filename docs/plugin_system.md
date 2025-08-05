# Plugin System Guide

The proxy server is architected around a **plugin system** that allows you to extend its behaviour without modifying the core code.  Plugins can inspect and modify HTTP requests and responses, implement security filters, persist state or expose command‑line interfaces.  This document describes how the plugin mechanism works and how to develop your own plugins.

## Overview

At runtime the proxy instantiates a **`PluginManager`** which is responsible for discovering and loading plugins.  Built‑in plugins live in the `proxy.plugins` package.  Additional plugins can be placed in a directory and loaded via the `--plugins` command‑line option.  Each plugin module must export a class called `Plugin` that derives from `BasePlugin`.

### Plugin Lifecycle

1. **Discovery** – When the server starts, the manager scans the built‑in plugin package and the external directory (if provided) for modules.  If a module defines a `Plugin` class that subclasses `BasePlugin` it will be loaded.
2. **Instantiation** – The manager constructs an instance of each plugin, passing itself (`PluginManager`) into the constructor.  Plugins can store a reference to the manager to access other plugins or the command registry.
3. **Initialization** – After instantiation, the manager calls `initialize()` on every plugin.  Override this method to perform setup tasks such as loading configuration or registering resources.  Plugins can raise exceptions here to abort loading.
4. **Operation** – For every incoming request the manager calls `handle_request()` on each plugin in the order they were registered.  The first plugin to return `False` will cause the request to be blocked.  If all plugins return `True`, the request is forwarded to the upstream server.  Responses are passed through the plugins via `handle_response()`, allowing plugins to inspect or modify the response body.
5. **Finalization** – When the proxy is shutting down the manager calls `finalize()` on each plugin in reverse order.  Override this method to release resources or flush state to disk.

### Hook Methods

Plugins can implement the following methods to intercept traffic:

* `handle_request(self, request: HTTPRequest) -> bool` – Inspect or modify an incoming request.  Return **`True`** to allow the request to continue or **`False`** to deny it.  The `HTTPRequest` object exposes attributes such as `method`, `path`, `headers` and `client`.
* `handle_response(self, response: bytes, request: HTTPRequest) -> bytes` – Inspect or modify a raw HTTP response body.  Return the response (modified or original).  Exceptions raised here will be logged and the original response will be sent to the client.

If your plugin does not need to handle requests or responses, simply inherit the default implementations which allow all traffic.

### Command‑Line Interface

Plugins can expose commands to the interactive shell by overriding `get_commands()` and returning a dictionary that maps command names to callables.  A command callable accepts a list of arguments (already split on whitespace) and returns an optional string.  If a string is returned it will be printed by the shell.

For example, a plugin might register a `ping` command:

```python
class MyPlugin(BasePlugin):
    name = "MyPlugin"

    def get_commands(self):
        return {
            "ping": self._cmd_ping,
        }

    def _cmd_ping(self, args: list[str]) -> str:
        return "pong"
```

Running `ping` in the shell would then output `pong`.

### Accessing Other Plugins

Each plugin receives a reference to the `PluginManager` at construction time.  To interact with other plugins (for example, to query the firewall state), iterate over `manager.plugins` and check their `name` attribute.  Avoid hard‑coding indices, as plugin order is not guaranteed.

```python
class AuditPlugin(BasePlugin):
    name = "Audit"

    def initialize(self) -> None:
        super().initialize()
        # Find the firewall plugin
        for plugin in self.manager.plugins:
            if plugin.name == "Firewall":
                self.firewall = plugin
                break
```

## Writing a Custom Plugin

To implement your own plugin, follow these steps:

1. **Create a Python module** in your plugins directory (e.g. `plugins/my_filter.py`).  Within it, define a class called `Plugin` that inherits from `BasePlugin`.
2. **Set the `name` attribute** of your class to a unique, human‑readable identifier.  This name must not conflict with existing plugins.
3. **Override hook methods** (`handle_request`, `handle_response`) as needed.  Use the `HTTPRequest` object to inspect the request and decide whether to allow or deny it.  Return `True` to permit or `False` to block.
4. **Register CLI commands** by implementing `get_commands()`.  Each command is associated with a function that accepts a list of arguments.
5. **Perform initialization and cleanup** by overriding `initialize()` and `finalize()` if necessary.

Here is a minimal example of a plugin that blocks requests to a forbidden path and provides a `forbidden` CLI command:

```python
from proxy.plugin_base import BasePlugin, HTTPRequest

class Plugin(BasePlugin):
    name = "PathBlocker"

    def __init__(self, manager):
        super().__init__(manager)
        self.blocked_path = "/secret"

    def handle_request(self, request: HTTPRequest) -> bool:
        return not request.path.startswith(self.blocked_path)

    def get_commands(self):
        return {"forbidden": self._cmd_forbidden}

    def _cmd_forbidden(self, args):
        return f"Blocking access to {self.blocked_path}"
```

Place this module in a directory and launch the server with `--plugins /path/to/plugins`.  The `PathBlocker` will load and apply its logic.  In the shell you can run `forbidden` to display the current blocked path.

## Best Practices

* Keep plugins **stateless** or at least easily resettable.  This reduces the risk of residual state affecting future requests.
* Avoid long‑running or blocking operations in `handle_request` and `handle_response` as these hooks are executed on the proxy’s main event loop.
* When exposing CLI commands, use clear and concise names.  Prefix commands with your plugin name to avoid collisions.
* Validate user input in CLI commands and provide informative error messages.

With this plugin system you can tailor the proxy to your organisation’s needs—implementing audit logging, rate limiting, authentication, content filtering and more without touching the core server.